import shutil
import os
import tempfile
import discord
from discord.ext import commands
from discord.commands import SlashCommandGroup, Option
from datetime import datetime, timezone
import asyncio

from core import config, database, utils

class CommandsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    stats_group = SlashCommandGroup(name="stats", description="Статистика активності та ігор")
    set_group = SlashCommandGroup(name="set", description="Налаштування системи (Admin)")

    @commands.command(name="sync")
    @commands.has_permissions(administrator=True)
    async def sync_cmd(self, ctx):
        await ctx.send(f"✅ Команди синхронізуються автоматично у Pycord!")

    async def _send_stats(self, ctx: discord.ApplicationContext):
        if not config.GLOBAL_SETTINGS["voice_stats"]:
            return await ctx.respond("❌ Статистика вимкнена", ephemeral=True)
            
        uid = ctx.author.id
        suid = str(uid)
        s = database.load_stats()
        
        total = database.get_total_time(uid)
        daily = database.get_daily_time(uid)
        current = database.get_current_session(uid)
        streak = database.get_streak(suid)
        
        raw_ug = s.get("games", {}).get(suid, {})
        
        embed = discord.Embed(title=f"📊 {ctx.author.display_name}{utils.streak_emoji(suid)}", color=0x2b2d31)
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
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
        await ctx.respond(embed=embed, ephemeral=True)

    @stats_group.command(name="profile", description="Твоя персональна картка статистики")
    async def stats_profile(self, ctx: discord.ApplicationContext):
        await self._send_stats(ctx)

    @stats_group.command(name="top", description="Топ активності сервера")
    async def stats_top(self, ctx: discord.ApplicationContext, 
                        period: Option(str, "За який період показати статистику?", choices=["total", "daily"])):
        if not config.GLOBAL_SETTINGS["voice_stats"]:
            return await ctx.respond("❌ Вимкнено", ephemeral=True)
            
        s = database.load_stats()
        data = dict(s.get(period, {}))
        
        for uid, start in config.voice_start_times.items():
            k = str(uid)
            data[k] = data.get(k, 0) + (datetime.now().timestamp() - start)
            
        top = sorted(data.items(), key=lambda x: x[1], reverse=True)[:10]
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        
        for i, (uid, sec) in enumerate(top):
            name = database.get_display_name(uid, ctx.guild, self.bot)
            medal = medals[i] if i < 3 else f"**{i+1}.**"
            lines.append(f"{medal} {name}{utils.streak_emoji(uid)} — `{utils.format_time(sec)}`")
            
        period_name = "Весь час" if period == "total" else "Сьогодні"
        embed = discord.Embed(
            title=f"🏆 Топ активності | {period_name}",
            description="\n".join(lines) or "Немає даних",
            color=0x2b2d31
        )
        embed.set_footer(text=utils.midnight_footer())
        await ctx.respond(embed=embed)

    @stats_group.command(name="full", description="Повна інформація по категоріях Залу Слави (Модератори)")
    async def stats_full(self, ctx: discord.ApplicationContext, 
                         category: Option(str, "Оберіть категорію для перегляду", choices=["voice", "streak", "games"])):
        if not ctx.guild:
            return await ctx.respond("❌ Цю команду можна використовувати тільки на сервері.", ephemeral=True)
            
        if not any(r.id == config.MODERATOR_ROLE_ID for r in ctx.author.roles):
            return await ctx.respond("❌ У вас немає прав для використання цієї команди.", ephemeral=True)

        s = database.load_stats()
        embed = discord.Embed(color=0xf1c40f, timestamp=datetime.now(timezone.utc))

        if category == "voice":
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
                name = database.get_display_name(uid, ctx.guild, self.bot)
                lines.append(f"**{i+1}.** {name} — `{utils.format_time(sec)}`")
            
            desc = "\n".join(lines)
            if len(desc) > 4000: desc = desc[:4000] + "\n... (список завеликий, обрізано)"
            embed.description = desc if desc else "*Немає даних*"

        elif category == "streak":
            embed.title = "🔥 Повний Топ Серій Войсу"
            streaks_data = {}
            for u in s.get("streaks", {}).keys():
                c = database.get_streak(u)
                if c > 0: streaks_data[u] = c
                
            sorted_s = sorted(streaks_data.items(), key=lambda x: x[1], reverse=True)
            lines = []
            for i, (u, c) in enumerate(sorted_s):
                name = database.get_display_name(u, ctx.guild, self.bot)
                lines.append(f"**{i+1}.** {name} — 🔥 `{c} днів`")
                
            desc = "\n".join(lines)
            if len(desc) > 4000: desc = desc[:4000] + "\n... (список завеликий, обрізано)"
            embed.description = desc if desc else "*Немає даних*"

        elif category == "games":
            embed.title = "🎮 Повний Топ Ігор"
            top_games = database.get_top_games(limit_games=50, limit_players=30)
            
            if not top_games:
                embed.description = "*Немає даних*"
            else:
                lines = []
                for game, data in top_games.items():
                    lines.append(f"\n**🎮 {game}** — `{utils.format_time(data['total'])}`")
                    for j, (uid, sec) in enumerate(data["players"]):
                        name = database.get_display_name(uid, ctx.guild, self.bot)
                        lines.append(f"└ **{j+1}.** {name} — `{utils.format_time(sec)}`")
                        
                desc = "\n".join(lines).strip()
                if len(desc) > 4000: 
                    desc = desc[:4000] + "\n\n... (список завеликий, частину обрізано)"
                embed.description = desc

        embed.set_footer(text=utils.midnight_footer())
        await ctx.respond(embed=embed, ephemeral=True)

    @stats_group.command(name="games", description="Хто грає зараз")
    async def stats_games(self, ctx: discord.ApplicationContext):
        embed = utils.build_live_embed(ctx.guild, self.bot)
        embed.set_footer(text=utils.midnight_footer())
        await ctx.respond(embed=embed)

    @stats_group.command(name="kings", description="Зал Слави")
    async def stats_kings(self, ctx: discord.ApplicationContext):
        embed = utils.build_fame_embed(ctx.guild, self.bot)
        embed.set_footer(text=utils.midnight_footer())
        await ctx.respond(embed=embed)

    @discord.slash_command(name="say", description="Озвучити текст у войсі")
    async def say_cmd(self, ctx: discord.ApplicationContext, text: Option(str, "Що сказати")):
        if len(text) > 200:
            return await ctx.respond("❌ Максимум 200 символів", ephemeral=True)
            
        vc = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        if vc and vc.is_playing():
            return await ctx.respond("❌ Зачекай, я ще не закінчив говорити попередню фразу!", ephemeral=True)
            
        can, remaining, reset_in = utils.check_say_limit(ctx.author.id)
        if not can:
            m, s = reset_in // 60, reset_in % 60
            return await ctx.respond(f"⏳ Ліміт! Скинеться через **{m}хв {s}с**", ephemeral=True)
            
        utils.record_say_usage(ctx.author.id)
        info = f" _(залишилось {remaining-1}/{config.SAY_LIMIT})_" if config.SAY_LIMIT > 0 else ""
        
        await ctx.respond(f"🔊 Озвучую: **{text}**{info}", ephemeral=True)
        asyncio.create_task(utils.play_tts(text, ctx.guild, self.bot))

    @set_group.command(name="say_limit", description="Ліміт /say на годину (0=без ліміту)")
    async def set_say_limit_cmd(self, ctx: discord.ApplicationContext, limit: Option(int, "Кількість на годину")):
        if not ctx.author.guild_permissions.administrator:
            return await ctx.respond("❌ Тільки адміни", ephemeral=True)
        if limit < 0:
            return await ctx.respond("❌ Від'ємне не можна", ephemeral=True)
            
        config.SAY_LIMIT = limit
        msg = "🔊 Ліміт вимкнено" if limit == 0 else f"🔊 Ліміт: **{limit}**/годину"
        await ctx.respond(msg, ephemeral=True)

    @discord.slash_command(name="ping", description="Затримка та аптайм")
    async def ping_cmd(self, ctx: discord.ApplicationContext):
        lat = round(self.bot.latency * 1000)
        up = datetime.now(timezone.utc) - config.GLOBAL_SETTINGS["start_time"]
        h, r = divmod(int(up.total_seconds()), 3600)
        
        color = 0x57F287 if lat < 100 else (0xFEE75C if lat < 200 else 0xED4245)
        embed = discord.Embed(title="🏓 Pong!", color=color)
        embed.add_field(name="📡 Затримка", value=f"`{lat}ms`", inline=True)
        embed.add_field(name="⏱️ Аптайм", value=f"`{h}г {r//60}хв`", inline=True)
        embed.add_field(name="🔢 Версія", value=f"`{config.GLOBAL_SETTINGS['version']}`", inline=True)
        embed.set_footer(text=utils.midnight_footer())
        
        await ctx.respond(embed=embed, ephemeral=True)

    @discord.slash_command(name="info", description="Статус системи")
    async def info_cmd(self, ctx: discord.ApplicationContext):
        embed = discord.Embed(title="🌑 Midnight Bot | Status", color=0x2b2d31)
        for label, key in [("🎮 Моніторинг", "monitoring"), ("🎙️ Войс-гард", "voice_guard"), ("📊 Статистика", "voice_stats")]:
            embed.add_field(name=label, value=f"`{'🟢 ON' if config.GLOBAL_SETTINGS[key] else '🔴 OFF'}`", inline=True)
            
        embed.add_field(name="👥 У войсі", value=f"`{len(config.voice_start_times)}`", inline=True)
        embed.add_field(name="🎮 Ігрових сесій", value=f"`{len(config.game_sessions)}`", inline=True)
        embed.add_field(name="💾 Say ліміт", value=f"`{config.SAY_LIMIT}/год`", inline=True)
        embed.add_field(name="🔢 Версія", value=f"`{config.GLOBAL_SETTINGS['version']}`", inline=False)
        
        embed.set_thumbnail(url=config.GLOBAL_SETTINGS["image_url"])
        embed.set_footer(text=utils.midnight_footer())
        await ctx.respond(embed=embed, ephemeral=True)

    @discord.slash_command(name="backup", description="Створити резервну копію")
    async def backup_cmd(self, ctx: discord.ApplicationContext):
        if not ctx.author.guild_permissions.administrator:
            return await ctx.respond("❌ Тільки адміни", ephemeral=True)
            
        await ctx.defer(ephemeral=True)
        zip_filename = "midnight_backup"
        zip_path = shutil.make_archive(zip_filename, 'zip', config.DATA_DIR)
        
        embed = discord.Embed(
            title="⬛ Резервне копіювання",
            description="▫️ Усі бази даних (статистика, сесії,) успішно запаковані.\n▪️ *Збережи цей архів.*",
            color=0x2b2d31
        )
        embed.set_footer(text=utils.midnight_footer())
        await ctx.respond(embed=embed, file=discord.File(zip_path))
        os.remove(zip_path)

    @discord.slash_command(name="restore", description="Відновити базу з архіву")
    async def restore_cmd(self, ctx: discord.ApplicationContext, archive: Option(discord.Attachment, "ZIP архів від команди /backup")):
        if not ctx.author.guild_permissions.administrator:
            return await ctx.respond("❌ Тільки адміни", ephemeral=True)
            
        if not archive.filename.endswith('.zip'):
            return await ctx.respond("❌ Потрібен .zip!", ephemeral=True)
            
        await ctx.defer(ephemeral=True)
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
            await ctx.respond(embed=embed)
        except Exception as e:
            await ctx.respond(f"❌ Помилка: {e}")
        finally:
            shutil.rmtree(temp_dir)

    @discord.slash_command(name="help", description="Список команд")
    async def help_cmd(self, ctx: discord.ApplicationContext):
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
        await ctx.respond(embed=embed, ephemeral=True)

    @set_group.command(name="monitoring", description="Увімкнути/Вимкнути моніторинг ігор")
    async def set_monitoring_cmd(self, ctx: discord.ApplicationContext, state: Option(str, "Оберіть стан", choices=["on", "off"])):
        if not ctx.author.guild_permissions.administrator:
            return await ctx.respond("❌ Тільки адміни", ephemeral=True)
        config.GLOBAL_SETTINGS["monitoring"] = (state == "on")
        await ctx.respond(f"📡 Моніторинг: **{'Увімкнено' if config.GLOBAL_SETTINGS['monitoring'] else 'Вимкнено'}**", ephemeral=True)

    @set_group.command(name="voice", description="Увімкнути/Вимкнути войс-гард")
    async def set_voice_cmd(self, ctx: discord.ApplicationContext, state: Option(str, "Оберіть стан", choices=["on", "off"])):
        if not ctx.author.guild_permissions.administrator:
            return await ctx.respond("❌ Тільки адміни", ephemeral=True)
            
        config.GLOBAL_SETTINGS["voice_guard"] = (state == "on")
        if not config.GLOBAL_SETTINGS["voice_guard"]:
            for vc in self.bot.voice_clients: 
                await vc.disconnect()
        await ctx.respond(f"🎙️ Войс-гард: **{'Увімкнено' if config.GLOBAL_SETTINGS['voice_guard'] else 'Вимкнено'}**", ephemeral=True)

    @set_group.command(name="stats", description="Увімкнути/Вимкнути збір статистики")
    async def set_stats_cmd(self, ctx: discord.ApplicationContext, state: Option(str, "Оберіть стан", choices=["on", "off"])):
        if not ctx.author.guild_permissions.administrator:
            return await ctx.respond("❌ Тільки адміни", ephemeral=True)
            
        config.GLOBAL_SETTINGS["voice_stats"] = (state == "on")
        await ctx.respond(f"📊 Статистика: **{'Увімкнено' if config.GLOBAL_SETTINGS['voice_stats'] else 'Вимкнено'}**", ephemeral=True)

    @set_group.command(name="voice_ai", description="Увімкнути/Вимкнути голосовий ШІ")
    async def set_voice_ai_cmd(self, ctx: discord.ApplicationContext, state: Option(str, "Оберіть стан", choices=["on", "off"])):
        if not ctx.author.guild_permissions.administrator:
            return await ctx.respond("❌ Тільки адміни", ephemeral=True)
            
        config.GLOBAL_SETTINGS["voice_ai_enabled"] = (state == "on")
        await ctx.respond(f"🤖 Голосовий ШІ: **{'Увімкнено' if config.GLOBAL_SETTINGS['voice_ai_enabled'] else 'Вимкнено'}**", ephemeral=True)

    @set_group.command(name="keyword", description="Змінити ключове слово для голосового ШІ")
    async def set_keyword_cmd(self, ctx: discord.ApplicationContext, keyword: Option(str, "Нове ключове слово")):
        if not ctx.author.guild_permissions.administrator:
            return await ctx.respond("❌ Тільки адміни", ephemeral=True)
        if len(keyword) < 2 or len(keyword) > 20:
            return await ctx.respond("❌ Слово має бути від 2 до 20 символів", ephemeral=True)
            
        config.VOICE_AI_KEYWORD = keyword
        await ctx.respond(f"🔑 Ключове слово: **{keyword}**", ephemeral=True)

    @set_group.command(name="record_duration", description="Тривалість запису для голосового ШІ")
    async def set_record_duration_cmd(self, ctx: discord.ApplicationContext, seconds: Option(int, "Тривалість в секундах (5-60)")):
        if not ctx.author.guild_permissions.administrator:
            return await ctx.respond("❌ Тільки адміни", ephemeral=True)
        if seconds < 5 or seconds > 60:
            return await ctx.respond("❌ Тривалість має бути від 5 до 60 секунд", ephemeral=True)
            
        config.VOICE_AI_RECORD_DURATION = seconds
        await ctx.respond(f"⏱️ Тривалість запису: **{seconds} секунд**", ephemeral=True)

    @discord.slash_command(name="ai", description="Запитати ШІ (Gemini)")
    async def ask_gemini_cmd(self, ctx: discord.ApplicationContext, prompt: Option(str, "Що хочеш запитати?")):
        try:
            await ctx.defer(ephemeral=False)
        except Exception as e:
            print(f"Помилка defer: {e}")
            return

        try:
            import os
            import aiohttp

            tokenGem = os.environ.get("GEMINI_API_KEY")
            if not tokenGem:
                return await ctx.respond("❌ Токен Gemini не знайдено у .env файлі.")

            clean_token = tokenGem.strip()
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={clean_token}"

            systemStyle = "Ти на діскорд сервері з ГТА5 під назвою 'MidNight'. Веди себе добре та відповідай коротко."

            payload = {
                "system_instruction": {
                    "parts": [{"text": systemStyle}]
                },
                "contents": [{
                    "role": "user",
                    "parts": [{"text": prompt}]
                }]
            }

            headers = {
                "Content-Type": "application/json"
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        try:
                            answer = data["candidates"][0]["content"]["parts"][0]["text"]
                        except (KeyError, IndexError):
                            answer = "❌ Помилка обробки: ШІ повернув порожню або нестандартну відповідь."
                    else:
                        try:
                            err_data = await response.json()
                            err_msg = err_data.get("error", {}).get("message", "Невідома помилка")
                        except:
                            err_msg = await response.text()
                        answer = f"❌ Помилка API Gemini: {response.status}\nДеталі: `{err_msg}`"

            if len(answer) > 1900:
                answer = answer[:1900] + "..."

            await ctx.respond(f"**Запит:** {prompt}\n**MidNight AI:** {answer}")

        except Exception as e:
            print(f"Критична помилка в AI: {e}")
            await ctx.respond(f"❌ Сталася внутрішня помилка коду:\n`{e}`")

def setup(bot):
    bot.add_cog(CommandsCog(bot))
