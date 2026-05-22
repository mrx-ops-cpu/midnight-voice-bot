import shutil
import os
import tempfile
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
import asyncio

from core import config, database, utils

class CommandsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="sync")
    @commands.has_permissions(administrator=True)
    async def sync_cmd(self, ctx):
        synced = await ctx.bot.tree.sync()
        await ctx.send(f"✅ Синхронізовано {len(synced)} команд!")

    async def _send_stats(self, interaction: discord.Interaction):
        if not config.GLOBAL_SETTINGS["voice_stats"]:
            return await interaction.response.send_message("❌ Статистика вимкнена", ephemeral=True)
            
        uid = interaction.user.id
        suid = str(uid)
        s = database.load_stats()
        
        total = database.get_total_time(uid)
        daily = database.get_daily_time(uid)
        current = database.get_current_session(uid)
        streak = database.get_streak(suid)
        
        raw_ug = s.get("games", {}).get(suid, {})
        
        embed = discord.Embed(title=f"📊 {interaction.user.display_name}{utils.streak_emoji(suid)}", color=0x2b2d31)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="📅 Сьогодні", value=f"`{utils.format_time(daily)}`", inline=True)
        embed.add_field(name="🏆 Весь час", value=f"`{utils.format_time(total)}`", inline=True)
        
        if current > 0:
            embed.add_field(name="🎙️ Зараз", value=f"`{utils.format_time(current)}`", inline=True)
        if streak >= 3:
            embed.add_field(name="🔥 Стрик", value=f"`{streak} дні поспіль`", inline=True)
            
        if raw_ug:
            grouped_ug = {}
            for g, sec in raw_ug.items():
                norm_g = database.normalize_game_name(g)
                grouped_ug[norm_g] = grouped_ug.get(norm_g, 0) + sec
                
            top = sorted(grouped_ug.items(), key=lambda x: x[1], reverse=True)[:5]
            embed.add_field(
                name="🎮 Час у іграх",
                value="\n".join(f"`{utils.format_time(sec)}` — {g}" for g, sec in top), 
                inline=False
            )
            
        embed.set_footer(text=utils.midnight_footer())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    stats_group = app_commands.Group(name="stats", description="Статистика активності та ігор")
    set_group = app_commands.Group(name="set", description="Налаштування системи (Admin)")

    @stats_group.command(name="profile", description="Твоя персональна картка статистики")
    async def stats_profile(self, interaction: discord.Interaction):
        await self._send_stats(interaction)

    @stats_group.command(name="top", description="Топ активності сервера")
    @app_commands.describe(period="За який період показати статистику?")
    @app_commands.choices(period=[
        app_commands.Choice(name="Весь час", value="total"),
        app_commands.Choice(name="Сьогодні", value="daily")
    ])
    async def stats_top(self, interaction: discord.Interaction, period: app_commands.Choice[str]):
        if not config.GLOBAL_SETTINGS["voice_stats"]:
            return await interaction.response.send_message("❌ Вимкнено", ephemeral=True)
            
        s = database.load_stats()
        data = dict(s.get(period.value, {}))
        
        for uid, start in config.voice_start_times.items():
            k = str(uid)
            data[k] = data.get(k, 0) + (datetime.now().timestamp() - start)
            
        top = sorted(data.items(), key=lambda x: x[1], reverse=True)[:10]
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        
        for i, (uid, sec) in enumerate(top):
            name = database.get_display_name(uid, interaction.guild, self.bot)
            medal = medals[i] if i < 3 else f"**{i+1}.**"
            lines.append(f"{medal} {name}{utils.streak_emoji(uid)} — `{utils.format_time(sec)}`")
            
        embed = discord.Embed(
            title=f"🏆 Топ активності | {period.name}",
            description="\n".join(lines) or "Немає даних",
            color=0x2b2d31
        )
        embed.set_footer(text=utils.midnight_footer())
        await interaction.response.send_message(embed=embed)

    @stats_group.command(name="full", description="Повна інформація по категоріях Залу Слави (Модератори)")
    @app_commands.describe(category="Оберіть категорію для перегляду")
    @app_commands.choices(category=[
        app_commands.Choice(name="Войс", value="voice"),
        app_commands.Choice(name="Стрики", value="streak"),
        app_commands.Choice(name="Ігри", value="games")
    ])
    async def stats_full(self, interaction: discord.Interaction, category: app_commands.Choice[str]):
        if not interaction.guild:
            return await interaction.response.send_message("❌ Тільки на сервері.", ephemeral=True)
            
        if not any(r.id == config.MODERATOR_ROLE_ID for r in interaction.user.roles):
            return await interaction.response.send_message("❌ Немає прав.", ephemeral=True)

        s = database.load_stats()
        embed = discord.Embed(color=0xf1c40f, timestamp=datetime.now(timezone.utc))

        if category.value == "voice":
            embed.title = "🎙️ Повний Топ Войсу"
            total = dict(s.get("total", {}))
            for uid, start in config.voice_start_times.items():
                k = str(uid)
                last_save = config.voice_last_save.get(uid, start)
                try: total[k] = float(total.get(k, 0)) + (datetime.now().timestamp() - float(last_save))
                except: pass
            
            sorted_v = sorted(total.items(), key=lambda x: float(x[1]) if isinstance(x[1], (int, float)) else 0, reverse=True)
            lines = []
            for i, (uid, sec) in enumerate(sorted_v):
                name = database.get_display_name(uid, interaction.guild, self.bot)
                lines.append(f"**{i+1}.** {name} — `{utils.format_time(sec)}`")
            
            desc = "\n".join(lines)
            if len(desc) > 4000: desc = desc[:4000] + "\n..."
            embed.description = desc if desc else "*Немає даних*"

        elif category.value == "streak":
            embed.title = "🔥 Повний Топ Серій Войсу"
            streaks_data = {}
            for u in s.get("streaks", {}).keys():
                c = database.get_streak(u)
                if c > 0: streaks_data[u] = c
                
            sorted_s = sorted(streaks_data.items(), key=lambda x: x[1], reverse=True)
            lines = []
            for i, (u, c) in enumerate(sorted_s):
                name = database.get_display_name(u, interaction.guild, self.bot)
                lines.append(f"**{i+1}.** {name} — 🔥 `{c} днів`")
                
            desc = "\n".join(lines)
            if len(desc) > 4000: desc = desc[:4000] + "\n..."
            embed.description = desc if desc else "*Немає даних*"

        elif category.value == "games":
            embed.title = "🎮 Повний Топ Ігор"
            top_games = database.get_top_games(limit_games=50, limit_players=30)
            
            if not top_games:
                embed.description = "*Немає даних*"
            else:
                lines = []
                for game, data in top_games.items():
                    lines.append(f"\n**🎮 {game}** — `{utils.format_time(data['total'])}`")
                    for j, (uid, sec) in enumerate(data["players"]):
                        name = database.get_display_name(uid, interaction.guild, self.bot)
                        lines.append(f"└ **{j+1}.** {name} — `{utils.format_time(sec)}`")
                        
                desc = "\n".join(lines).strip()
                if len(desc) > 4000: desc = desc[:4000] + "\n..."
                embed.description = desc

        embed.set_footer(text=utils.midnight_footer())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @stats_group.command(name="games", description="Хто грає зараз")
    async def stats_games(self, interaction: discord.Interaction):
        embed = utils.build_live_embed(interaction.guild, self.bot)
        embed.set_footer(text=utils.midnight_footer())
        await interaction.response.send_message(embed=embed)

    @stats_group.command(name="kings", description="Зал Слави")
    async def stats_kings(self, interaction: discord.Interaction):
        embed = utils.build_fame_embed(interaction.guild, self.bot)
        embed.set_footer(text=utils.midnight_footer())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="say", description="Озвучити текст у войсі")
    @app_commands.describe(text="Що сказати")
    async def say_cmd(self, interaction: discord.Interaction, text: str):
        if len(text) > 200:
            return await interaction.response.send_message("❌ Максимум 200 символів", ephemeral=True)
            
        vc = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        if vc and vc.is_playing():
            return await interaction.response.send_message("❌ Зачекай, я ще не закінчив говорити!", ephemeral=True)
            
        can, remaining, reset_in = utils.check_say_limit(interaction.user.id)
        if not can:
            m, s = reset_in // 60, reset_in % 60
            return await interaction.response.send_message(f"⏳ Ліміт! Скинеться через **{m}хв {s}с**", ephemeral=True)
            
        utils.record_say_usage(interaction.user.id)
        info = f" _(залишилось {remaining-1}/{config.SAY_LIMIT})_" if config.SAY_LIMIT > 0 else ""
        
        await interaction.response.send_message(f"🔊 Озвучую: **{text}**{info}", ephemeral=True)
        asyncio.create_task(utils.play_tts(text, interaction.guild, self.bot))

    @set_group.command(name="say_limit", description="Ліміт /say на годину (0=без ліміту)")
    @app_commands.describe(limit="Кількість на годину")
    async def set_say_limit_cmd(self, interaction: discord.Interaction, limit: int):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Тільки адміни", ephemeral=True)
        if limit < 0:
            return await interaction.response.send_message("❌ Від'ємне не можна", ephemeral=True)
            
        config.SAY_LIMIT = limit
        msg = "🔊 Ліміт вимкнено" if limit == 0 else f"🔊 Ліміт: **{limit}**/годину"
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="ping", description="Затримка та аптайм")
    async def ping_cmd(self, interaction: discord.Interaction):
        lat = round(self.bot.latency * 1000)
        up = datetime.now(timezone.utc) - config.GLOBAL_SETTINGS["start_time"]
        h, r = divmod(int(up.total_seconds()), 3600)
        
        color = 0x57F287 if lat < 100 else (0xFEE75C if lat < 200 else 0xED4245)
        embed = discord.Embed(title="🏓 Pong!", color=color)
        embed.add_field(name="📡 Затримка", value=f"`{lat}ms`", inline=True)
        embed.add_field(name="⏱️ Аптайм", value=f"`{h}г {r//60}хв`", inline=True)
        embed.add_field(name="🔢 Версія", value=f"`{config.GLOBAL_SETTINGS['version']}`", inline=True)
        embed.set_footer(text=utils.midnight_footer())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="info", description="Статус системи")
    async def info_cmd(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🌑 Midnight Bot | Status", color=0x2b2d31)
        for label, key in [("🎮 Моніторинг", "monitoring"), ("🎙️ Войс-гард", "voice_guard"), ("📊 Статистика", "voice_stats")]:
            embed.add_field(name=label, value=f"`{'🟢 ON' if config.GLOBAL_SETTINGS[key] else '🔴 OFF'}`", inline=True)
            
        embed.add_field(name="👥 У войсі", value=f"`{len(config.voice_start_times)}`", inline=True)
        embed.add_field(name="🎮 Ігрових сесій", value=f"`{len(config.game_sessions)}`", inline=True)
        embed.add_field(name="💾 Say ліміт", value=f"`{config.SAY_LIMIT}/год`", inline=True)
        embed.add_field(name="🔢 Версія", value=f"`{config.GLOBAL_SETTINGS['version']}`", inline=False)
        embed.set_thumbnail(url=config.GLOBAL_SETTINGS["image_url"])
        embed.set_footer(text=utils.midnight_footer())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="backup", description="Створити резервну копію")
    async def backup_cmd(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Тільки адміни", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        zip_path = shutil.make_archive("midnight_backup", 'zip', config.DATA_DIR)
        
        embed = discord.Embed(
            title="⬛ Резервне копіювання",
            description="▫️ Усі бази даних успішно запаковані.\n▪️ *Збережи цей архів.*",
            color=0x2b2d31
        )
        embed.set_footer(text=utils.midnight_footer())
        await interaction.followup.send(embed=embed, file=discord.File(zip_path))
        os.remove(zip_path)

    @app_commands.command(name="restore", description="Відновити базу з архіву")
    @app_commands.describe(archive="ZIP архів від команди /backup")
    async def restore_cmd(self, interaction: discord.Interaction, archive: discord.Attachment):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Тільки адміни", ephemeral=True)
            
        if not archive.filename.endswith('.zip'):
            return await interaction.response.send_message("❌ Потрібен .zip!", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        temp_dir = tempfile.mkdtemp()
        temp_zip_path = os.path.join(temp_dir, archive.filename)
        await archive.save(temp_zip_path)
        
        try:
            shutil.unpack_archive(temp_zip_path, config.DATA_DIR)
            database.load_stats()
            database.load_voice_sessions()
            database.load_game_sessions()
            database.load_active_rooms()
            embed = discord.Embed(title="⬛ Відновлення даних", description="▫️ Успішно!", color=0x2b2d31)
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"❌ Помилка: {e}")
        finally:
            shutil.rmtree(temp_dir)

    @app_commands.command(name="help", description="Список команд")
    async def help_cmd(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🌑 Midnight Bot | Допомога", color=0x2b2d31)
        embed.add_field(name="📊 Статистика", value="`/stats profile` `/stats top` `/stats full`", inline=False)
        embed.add_field(name="🎮 Геймінг", value="`/stats games` `/stats kings`", inline=False)
        embed.add_field(name="🎙️ Войс та Інше", value="`/say` `/ping` `/info` `/ai`", inline=False)
        embed.add_field(
            name="⚙️ Система (Admin)",
            value="`/set monitoring` `/set voice` `/set stats` `/set say_limit` `/set voice_ai` `/set keyword` `/set record_duration`",
            inline=False
        )
        embed.set_footer(text=utils.midnight_footer())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @set_group.command(name="monitoring", description="Увімкнути/Вимкнути моніторинг ігор")
    @app_commands.describe(state="Оберіть стан")
    @app_commands.choices(state=[app_commands.Choice(name="on", value="on"), app_commands.Choice(name="off", value="off")])
    async def set_monitoring_cmd(self, interaction: discord.Interaction, state: app_commands.Choice[str]):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Тільки адміни", ephemeral=True)
        config.GLOBAL_SETTINGS["monitoring"] = (state.value == "on")
        await interaction.response.send_message(f"📡 Моніторинг: **{'Увімкнено' if config.GLOBAL_SETTINGS['monitoring'] else 'Вимкнено'}**", ephemeral=True)

    @set_group.command(name="voice", description="Увімкнути/Вимкнути войс-гард")
    @app_commands.describe(state="Оберіть стан")
    @app_commands.choices(state=[app_commands.Choice(name="on", value="on"), app_commands.Choice(name="off", value="off")])
    async def set_voice_cmd(self, interaction: discord.Interaction, state: app_commands.Choice[str]):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Тільки адміни", ephemeral=True)
        config.GLOBAL_SETTINGS["voice_guard"] = (state.value == "on")
        if not config.GLOBAL_SETTINGS["voice_guard"]:
            for vc in self.bot.voice_clients:
                await vc.disconnect()
        await interaction.response.send_message(f"🎙️ Войс-гард: **{'Увімкнено' if config.GLOBAL_SETTINGS['voice_guard'] else 'Вимкнено'}**", ephemeral=True)

    @set_group.command(name="stats", description="Увімкнути/Вимкнути збір статистики")
    @app_commands.describe(state="Оберіть стан")
    @app_commands.choices(state=[app_commands.Choice(name="on", value="on"), app_commands.Choice(name="off", value="off")])
    async def set_stats_cmd(self, interaction: discord.Interaction, state: app_commands.Choice[str]):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Тільки адміни", ephemeral=True)
        config.GLOBAL_SETTINGS["voice_stats"] = (state.value == "on")
        await interaction.response.send_message(f"📊 Статистика: **{'Увімкнено' if config.GLOBAL_SETTINGS['voice_stats'] else 'Вимкнено'}**", ephemeral=True)

    @set_group.command(name="voice_ai", description="Увімкнути/Вимкнути голосовий ШІ")
    @app_commands.describe(state="Оберіть стан")
    @app_commands.choices(state=[app_commands.Choice(name="on", value="on"), app_commands.Choice(name="off", value="off")])
    async def set_voice_ai_cmd(self, interaction: discord.Interaction, state: app_commands.Choice[str]):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Тільки адміни", ephemeral=True)
        config.GLOBAL_SETTINGS["voice_ai_enabled"] = (state.value == "on")
        await interaction.response.send_message(f"🤖 Голосовий ШІ: **{'Увімкнено' if config.GLOBAL_SETTINGS['voice_ai_enabled'] else 'Вимкнено'}**", ephemeral=True)

    @set_group.command(name="keyword", description="Змінити ключове слово для голосового ШІ")
    @app_commands.describe(keyword="Нове ключове слово")
    async def set_keyword_cmd(self, interaction: discord.Interaction, keyword: str):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Тільки адміни", ephemeral=True)
        if len(keyword) < 2 or len(keyword) > 20:
            return await interaction.response.send_message("❌ Слово має бути від 2 до 20 символів", ephemeral=True)
        config.VOICE_AI_KEYWORD = keyword
        await interaction.response.send_message(f"🔑 Ключове слово: **{keyword}**", ephemeral=True)

    @set_group.command(name="record_duration", description="Тривалість запису для голосового ШІ")
    @app_commands.describe(seconds="Тривалість в секундах (5-60)")
    async def set_record_duration_cmd(self, interaction: discord.Interaction, seconds: int):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Тільки адміни", ephemeral=True)
        if seconds < 5 or seconds > 60:
            return await interaction.response.send_message("❌ Від 5 до 60 секунд", ephemeral=True)
        config.VOICE_AI_RECORD_DURATION = seconds
        await interaction.response.send_message(f"⏱️ Тривалість запису: **{seconds} секунд**", ephemeral=True)

    @app_commands.command(name="ai", description="Запитати ШІ (Gemini)")
    @app_commands.describe(prompt="Що хочеш запитати?")
    async def ask_gemini_cmd(self, interaction: discord.Interaction, prompt: str):
        await interaction.response.defer(ephemeral=False)
        try:
            import aiohttp
            tokenGem = os.environ.get("GEMINI_API_KEY")
            if not tokenGem:
                return await interaction.followup.send("❌ Токен Gemini не знайдено.")

            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={tokenGem.strip()}"
            payload = {
                "system_instruction": {"parts": [{"text": "Ти на діскорд сервері з ГТА5 під назвою 'MidNight'. Веди себе добре та відповідай коротко."}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}]
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers={"Content-Type": "application/json"}) as response:
                    if response.status == 200:
                        data = await response.json()
                        try:
                            answer = data["candidates"][0]["content"]["parts"][0]["text"]
                        except (KeyError, IndexError):
                            answer = "❌ ШІ повернув порожню відповідь."
                    else:
                        err_data = await response.json()
                        answer = f"❌ Помилка API: {response.status}\n`{err_data.get('error', {}).get('message', '')}`"

            if len(answer) > 1900:
                answer = answer[:1900] + "..."
            await interaction.followup.send(f"**Запит:** {prompt}\n**MidNight AI:** {answer}")

        except Exception as e:
            await interaction.followup.send(f"❌ Внутрішня помилка:\n`{e}`")

async def setup(bot):
    await bot.add_cog(CommandsCog(bot))
