import shutil
import os
import tempfile
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
import asyncio

from core import config, database, utils

class SayModal(discord.ui.Modal, title='Сказати у войс'):
    text_input = discord.ui.TextInput(
        label='Текст для озвучення',
        style=discord.TextStyle.paragraph,
        placeholder='Привіт всім!',
        required=True,
        max_length=200
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        text = self.text_input.value
        can, remaining, reset_in = utils.check_say_limit(interaction.user.id)
        if not can:
            m, s = reset_in // 60, reset_in % 60
            return await interaction.response.send_message(f"⏳ Ліміт! Скинеться через **{m}хв {s}с**", ephemeral=True)
            
        utils.record_say_usage(interaction.user.id)
        info = f" _(залишилось {remaining-1}/{config.SAY_LIMIT})_" if config.SAY_LIMIT > 0 else ""
        
        await interaction.response.send_message(f"🔊 Озвучую: **{text}**{info}", ephemeral=True)
        asyncio.create_task(utils.play_tts(text, interaction.guild, self.bot))

class SayLimitModal(discord.ui.Modal, title='Ліміт /say'):
    limit_input = discord.ui.TextInput(
        label='Кількість на годину (0 = без ліміту)',
        style=discord.TextStyle.short,
        placeholder='Наприклад: 3',
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            limit = int(self.limit_input.value)
            if limit < 0: raise ValueError
            config.SAY_LIMIT = limit
            msg = "🔊 Ліміт вимкнено" if limit == 0 else f"🔊 Ліміт: **{limit}**/годину"
            await interaction.response.send_message(msg, ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Введіть коректне число!", ephemeral=True)

class AdminPanel(discord.ui.View):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.update_buttons()

    def update_buttons(self):
        self.btn_monitoring.style = discord.ButtonStyle.green if config.GLOBAL_SETTINGS["monitoring"] else discord.ButtonStyle.red
        self.btn_monitoring.label = f"🎮 Моніторинг ({'ON' if config.GLOBAL_SETTINGS['monitoring'] else 'OFF'})"
        
        self.btn_voice.style = discord.ButtonStyle.green if config.GLOBAL_SETTINGS["voice_guard"] else discord.ButtonStyle.red
        self.btn_voice.label = f"🎙️ Войс-гард ({'ON' if config.GLOBAL_SETTINGS['voice_guard'] else 'OFF'})"
        
        self.btn_stats.style = discord.ButtonStyle.green if config.GLOBAL_SETTINGS["voice_stats"] else discord.ButtonStyle.red
        self.btn_stats.label = f"📊 Статистика ({'ON' if config.GLOBAL_SETTINGS['voice_stats'] else 'OFF'})"

    @discord.ui.button(custom_id="admin_mon", row=0)
    async def btn_monitoring(self, interaction: discord.Interaction, button: discord.ui.Button):
        config.GLOBAL_SETTINGS["monitoring"] = not config.GLOBAL_SETTINGS["monitoring"]
        self.update_buttons()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(custom_id="admin_voice", row=0)
    async def btn_voice(self, interaction: discord.Interaction, button: discord.ui.Button):
        config.GLOBAL_SETTINGS["voice_guard"] = not config.GLOBAL_SETTINGS["voice_guard"]
        if not config.GLOBAL_SETTINGS["voice_guard"]:
            for vc in self.bot.voice_clients:
                await vc.disconnect()
        self.update_buttons()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(custom_id="admin_stats", row=0)
    async def btn_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        config.GLOBAL_SETTINGS["voice_stats"] = not config.GLOBAL_SETTINGS["voice_stats"]
        self.update_buttons()
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="⚙️ Ліміт /say", style=discord.ButtonStyle.secondary, custom_id="admin_limit", row=1)
    async def btn_limit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SayLimitModal())

    @discord.ui.button(label="💾 Бекап", style=discord.ButtonStyle.primary, custom_id="admin_backup", row=1)
    async def btn_backup(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        zip_path = shutil.make_archive("midnight_backup", 'zip', config.DATA_DIR)
        embed = discord.Embed(title="⬛ Резервне копіювання", description="▫️ Бази запаковані.", color=0x2b2d31)
        await interaction.followup.send(embed=embed, file=discord.File(zip_path))
        os.remove(zip_path)

class UserPanel(discord.ui.View):
    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    @discord.ui.button(label="👤 Моя статистика", style=discord.ButtonStyle.primary, custom_id="user_profile")
    async def btn_profile(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog._send_stats(interaction)

    @discord.ui.button(label="🏆 Топ сервера", style=discord.ButtonStyle.success, custom_id="user_top")
    async def btn_top(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not config.GLOBAL_SETTINGS["voice_stats"]:
            return await interaction.response.send_message("❌ Вимкнено", ephemeral=True)
        s = database.load_stats()
        data = dict(s.get("total", {}))
        for uid, start in config.voice_start_times.items():
            k = str(uid)
            data[k] = data.get(k, 0) + (datetime.now().timestamp() - start)
        top = sorted(data.items(), key=lambda x: x[1], reverse=True)[:10]
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, (uid, sec) in enumerate(top):
            name = database.get_display_name(uid, interaction.guild, self.cog.bot)
            medal = medals[i] if i < 3 else f"**{i+1}.**"
            lines.append(f"{medal} {name}{utils.streak_emoji(uid)} — `{utils.format_time(sec)}`")
        embed = discord.Embed(title=f"🏆 Топ активності | Весь час", description="\n".join(lines) or "Немає даних", color=0x2b2d31)
        embed.set_footer(text=utils.midnight_footer())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🎮 Хто грає", style=discord.ButtonStyle.secondary, custom_id="user_games")
    async def btn_games(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = utils.build_live_embed(interaction.guild, self.cog.bot)
        embed.set_footer(text=utils.midnight_footer())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🗣️ Сказати у войс", style=discord.ButtonStyle.danger, custom_id="user_say")
    async def btn_say(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = discord.utils.get(self.cog.bot.voice_clients, guild=interaction.guild)
        if vc and vc.is_playing():
            return await interaction.response.send_message("❌ Зачекай, я ще не закінчив говорити!", ephemeral=True)
        await interaction.response.send_modal(SayModal(self.cog.bot))

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

    @app_commands.command(name="admin", description="⚙️ Адмін-панель керування ботом")
    async def admin_panel_cmd(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Тільки адміни", ephemeral=True)
        embed = discord.Embed(title="⚙️ Адмін-панель", description="Керування функціями бота", color=0x2b2d31)
        await interaction.response.send_message(embed=embed, view=AdminPanel(self.bot), ephemeral=True)

    @app_commands.command(name="menu", description="🌑 Головне меню гравця")
    async def user_menu_cmd(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🌑 Midnight Menu", description="Оберіть потрібну дію:", color=0x2b2d31)
        await interaction.response.send_message(embed=embed, view=UserPanel(self), ephemeral=True)

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

    @app_commands.command(name="help", description="Список команд бота")
    async def help_cmd(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🌑 Midnight Bot | Список команд", color=0x2b2d31)
        
        player_cmds = (
            "`/menu` — Головне меню\n"
            "`/say` — Сказати у войсі\n"
            "`/ai` — Запитати ШІ\n"
            "`/ping` — Затримка бота\n"
            "`/help` — Цей список"
        )
        
        admin_cmds = (
            "`/admin` — Панель керування\n"
            "`/info` — Статус системи\n"
            "`/updatestats` — Оновити топи\n"
            "`/setmonitorchannel` — Канал топів\n"
            "`/setvoice` — Канал бота\n"
            "`/backup` — Зробити бекап\n"
            "`/restore` — Відновити бекап"
        )
        
        embed.add_field(name="🎮 Для Гравців", value=player_cmds, inline=True)
        embed.add_field(name="⚙️ Для Адміністраторів", value=admin_cmds, inline=True)
        
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=utils.midnight_footer())
        await interaction.response.send_message(embed=embed, ephemeral=True)


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

    @app_commands.command(name="setvoice", description="Обрати голосовий канал, де бот буде завжди сидіти")
    @app_commands.describe(channel="Голосовий канал для бота")
    async def setvoice(self, interaction: discord.Interaction, channel: discord.VoiceChannel):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Тільки адмін може це зробити!", ephemeral=True)
            
        database.save_bot_voice(channel.id)
        
        # Одразу переміщуємо бота
        vc = discord.utils.get(self.bot.voice_clients, guild=interaction.guild)
        if vc:
            await vc.move_to(channel)
        else:
            try: await channel.connect(timeout=20.0, reconnect=True)
            except: pass
            
        await interaction.response.send_message(f"✅ Бот тепер завжди буде сидіти у **{channel.name}**!")

    @app_commands.command(name="setmonitorchannel", description="Обрати канал для Активних каток та Залу Слави")
    @app_commands.describe(channel="Текстовий канал")
    async def setmonitorchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Тільки адмін може це зробити!", ephemeral=True)
            
        database.save_monitor_channel(channel.id)
        
        try:
            await channel.purge(limit=50, check=lambda m: m.author == self.bot.user)
        except:
            pass
            
        config.live_message_id = None
        config.fame_voice_msg_id = None
        config.fame_streaks_msg_id = None
        config.fame_games_msg_id = None
        config.fame_games_2_msg_id = None
        config.fame_games_3_msg_id = None
        
        config.last_live_hash = None
        config.last_fame_voice_hash = None
        config.last_fame_streaks_hash = None
        config.last_fame_games_hash = None
        config.last_fame_games_2_hash = None
        config.last_fame_games_3_hash = None
        
        database.save_message_ids()
        
        await interaction.response.send_message(f"✅ Канал моніторингу встановлено на {channel.mention}! Зараз бот надішле нові панелі у правильному порядку.", ephemeral=True)
        
        async def send_in_order():
            await utils.update_fame_message(interaction.guild, self.bot)
            await utils.update_live_message(interaction.guild, self.bot)
            
            
        asyncio.create_task(send_in_order())

    @app_commands.command(name="updatestats", description="Оновити картинки слави (Топи) прямо зараз")
    async def updatestats(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Тільки адмін може це зробити!", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        
        # Force clear hashes so it definitely updates even if it thinks nothing changed
        config.last_fame_voice_hash = None
        config.last_fame_streaks_hash = None
        config.last_fame_games_hash = None
        config.last_fame_games_2_hash = None
        config.last_fame_games_3_hash = None
        
        await utils.update_fame_message(interaction.guild, self.bot)
        await interaction.followup.send("✅ Картинки успішно оновлено!", ephemeral=True)

    @app_commands.command(name="hidegame", description="Приховати гру з Топів (для адмінів)")
    @app_commands.describe(game="Назва програми чи гри (наприклад: Visual Studio Code)")
    async def hidegame_cmd(self, interaction: discord.Interaction, game: str):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Тільки адмін може це зробити!", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        success = database.hide_game(game)
        if success:
            # Force update hashes so it definitely refreshes
            config.last_fame_games_hash = None
            config.last_fame_games_2_hash = None
            config.last_fame_games_3_hash = None
            await utils.update_fame_message(interaction.guild, self.bot)
            await interaction.followup.send(f"✅ Програма **{game}** прихована з топів! Картинки оновлено.", ephemeral=True)
        else:
            await interaction.followup.send(f"⚠️ Програма **{game}** вже була прихована.", ephemeral=True)

    @app_commands.command(name="unhidegame", description="Повернути приховану гру в Топи (для адмінів)")
    @app_commands.describe(game="Назва програми чи гри")
    async def unhidegame_cmd(self, interaction: discord.Interaction, game: str):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Тільки адмін може це зробити!", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        success = database.unhide_game(game)
        if success:
            config.last_fame_games_hash = None
            config.last_fame_games_2_hash = None
            config.last_fame_games_3_hash = None
            await utils.update_fame_message(interaction.guild, self.bot)
            await interaction.followup.send(f"✅ Програма **{game}** повернена в топи! Картинки оновлено.", ephemeral=True)
        else:
            await interaction.followup.send(f"⚠️ Програма **{game}** не була знайдена у списку прихованих.", ephemeral=True)

    @app_commands.command(name="hiddengames", description="Список усіх прихованих ігор (для адмінів)")
    async def hiddengames_cmd(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Тільки адмін може це зробити!", ephemeral=True)
            
        hidden = database.load_hidden_games()
        if not hidden:
            return await interaction.response.send_message("ℹ️ Список прихованих програм зараз порожній.", ephemeral=True)
            
        desc = "\n".join(f"- `{g}`" for g in hidden)
        embed = discord.Embed(title="🚫 Приховані ігри", description=desc, color=0x2b2d31)
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(CommandsCog(bot))
