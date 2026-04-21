import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone
import asyncio

# Імпортуємо наші модулі
from core import config, database, utils

class CommandsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── Допоміжна функція для статистики (щоб не дублювати код) ──
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
        ug = s.get("games", {}).get(suid, {})
        
        embed = discord.Embed(title=f"📊 {interaction.user.display_name}{utils.streak_emoji(suid)}", color=0x2b2d31)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="📅 Сьогодні", value=f"`{utils.format_time(daily)}`", inline=True)
        embed.add_field(name="🏆 Весь час", value=f"`{utils.format_time(total)}`", inline=True)
        
        if current > 0:
            embed.add_field(name="🎙️ Зараз", value=f"`{utils.format_time(current)}`", inline=True)
        if streak >= 3:
            embed.add_field(name="🔥 Стрик", value=f"`{streak} дні поспіль`", inline=True)
            
        if ug:
            top = sorted(ug.items(), key=lambda x: x[1], reverse=True)[:5]
            embed.add_field(
                name="🎮 Час у іграх",
                value="\n".join(f"`{utils.format_time(sec)}` — {g}" for g, sec in top), 
                inline=False
            )
            
        embed.set_footer(text=utils.midnight_footer())
        await interaction.response.send_message(embed=embed)

    # ── Команди Статистики ──────────────────────────────────────
    @app_commands.command(name="stats", description="Твоя персональна картка статистики")
    async def stats_cmd(self, interaction: discord.Interaction):
        await self._send_stats(interaction)

    @app_commands.command(name="mystats", description="Твоя персональна картка статистики (Аліас)")
    async def mystats_cmd(self, interaction: discord.Interaction):
        await self._send_stats(interaction)

    @app_commands.command(name="leaderboard", description="Топ активності сервера")
    @app_commands.choices(період=[
        app_commands.Choice(name="Весь час", value="total"),
        app_commands.Choice(name="Сьогодні", value="daily")
    ])
    async def leaderboard_cmd(self, interaction: discord.Interaction, період: app_commands.Choice[str]):
        if not config.GLOBAL_SETTINGS["voice_stats"]:
            return await interaction.response.send_message("❌ Вимкнено", ephemeral=True)
            
        s = database.load_stats()
        data = dict(s.get(період.value, {}))
        
        # Додаємо поточні активні сесії з RAM
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
            title=f"🏆 Топ активності | {період.name}",
            description="\n".join(lines) or "Немає даних",
            color=0x2b2d31
        )
        embed.set_footer(text=utils.midnight_footer())
        await interaction.response.send_message(embed=embed)

    # ── Команди Моніторингу Ігор ────────────────────────────────
    @app_commands.command(name="games", description="Хто грає зараз")
    async def games_cmd(self, interaction: discord.Interaction):
        embed = utils.build_live_embed()
        embed.set_footer(text=utils.midnight_footer())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="kings", description="Зал Слави")
    async def kings_cmd(self, interaction: discord.Interaction):
        embed = utils.build_fame_embed(interaction.guild, self.bot)
        embed.set_footer(text=utils.midnight_footer())
        await interaction.response.send_message(embed=embed)

    # ── Команди Озвучення (TTS) ─────────────────────────────────
    @app_commands.command(name="say", description="Озвучити текст у войсі")
    @app_commands.describe(текст="Що сказати")
    async def say_cmd(self, interaction: discord.Interaction, текст: str):
        if len(текст) > 200:
            return await interaction.response.send_message("❌ Максимум 200 символів", ephemeral=True)
            
        can, remaining, reset_in = utils.check_say_limit(interaction.user.id)
        if not can:
            m, s = reset_in // 60, reset_in % 60
            return await interaction.response.send_message(f"⏳ Ліміт! Скинеться через **{m}хв {s}с**", ephemeral=True)
            
        utils.record_say_usage(interaction.user.id)
        info = f" _(залишилось {remaining-1}/{config.SAY_LIMIT})_" if config.SAY_LIMIT > 0 else ""
        
        await interaction.response.send_message(f"🔊 Озвучую: **{текст}**{info}", ephemeral=True)
        # Викликаємо функцію з utils (передаємо bot для доступу до voice_clients)
        asyncio.create_task(utils.play_tts(текст, interaction.guild, self.bot))

    @app_commands.command(name="set_say_limit", description="Ліміт /say на годину (0=без ліміту)")
    @app_commands.describe(ліміт="Кількість на годину")
    async def set_say_limit_cmd(self, interaction: discord.Interaction, ліміт: int):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Тільки адміни", ephemeral=True)
        if ліміт < 0:
            return await interaction.response.send_message("❌ Від'ємне не можна", ephemeral=True)
            
        config.SAY_LIMIT = ліміт
        msg = "🔊 Ліміт вимкнено" if ліміт == 0 else f"🔊 Ліміт: **{ліміт}**/годину"
        await interaction.response.send_message(msg)

    # ── Системні Команди ────────────────────────────────────────
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
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="midnight_info", description="Статус системи")
    async def midnight_info_cmd(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🌑 Midnight Bot | Status", color=0x2b2d31)
        for label, key in [("🎮 Моніторинг", "monitoring"), ("🎙️ Войс-гард", "voice_guard"), ("📊 Статистика", "voice_stats")]:
            embed.add_field(name=label, value=f"`{'🟢 ON' if config.GLOBAL_SETTINGS[key] else '🔴 OFF'}`", inline=True)
            
        embed.add_field(name="👥 У войсі", value=f"`{len(config.voice_start_times)}`", inline=True)
        embed.add_field(name="🎮 Ігор", value=f"`{len(config.active_games)}`", inline=True)
        embed.add_field(name="💾 Say ліміт", value=f"`{config.SAY_LIMIT}/год`", inline=True)
        
        # Версія бота в самому низу
        embed.add_field(name="🔢 Версія", value=f"`{config.GLOBAL_SETTINGS['version']}`", inline=False)
        
        embed.set_thumbnail(url=config.GLOBAL_SETTINGS["image_url"])
        embed.set_footer(text=utils.midnight_footer())
        
        # Додаємо ephemeral=True сюди 👇
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="help", description="Список команд")
    async def help_cmd(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🌑 Midnight Bot | Допомога", color=0x2b2d31)
        embed.add_field(name="📊 Статистика", value="`/stats` `/leaderboard`", inline=False)
        embed.add_field(name="🎮 Геймінг", value="`/games` `/kings`", inline=False)
        embed.add_field(name="🎙️ Войс", value="`/say` `/set_say_limit`", inline=False)
        embed.add_field(
            name="⚙️ Система",
            value="`/ping` `/midnight_info` `/set_monitoring` `/set_voice` `/set_stats`",
            inline=False
        )
        embed.set_footer(text=utils.midnight_footer())
        await interaction.response.send_message(embed=embed)

    # ── Команди Налаштувань (Адмінські) ─────────────────────────
    @app_commands.command(name="set_monitoring", description="Увімкнути/Вимкнути моніторинг ігор")
    @app_commands.choices(стан=[
        app_commands.Choice(name="Увімкнути", value="on"),
        app_commands.Choice(name="Вимкнути", value="off")
    ])
    async def set_monitoring_cmd(self, interaction: discord.Interaction, стан: app_commands.Choice[str]):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Тільки адміни", ephemeral=True)
        config.GLOBAL_SETTINGS["monitoring"] = (стан.value == "on")
        await interaction.response.send_message(f"📡 Моніторинг: **{'Увімкнено' if config.GLOBAL_SETTINGS['monitoring'] else 'Вимкнено'}**")

    @app_commands.command(name="set_voice", description="Увімкнути/Вимкнути войс-гард")
    @app_commands.choices(стан=[
        app_commands.Choice(name="Увімкнути", value="on"),
        app_commands.Choice(name="Вимкнути", value="off")
    ])
    async def set_voice_cmd(self, interaction: discord.Interaction, стан: app_commands.Choice[str]):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Тільки адміни", ephemeral=True)
            
        config.GLOBAL_SETTINGS["voice_guard"] = (стан.value == "on")
        if not config.GLOBAL_SETTINGS["voice_guard"]:
            # Відключаємо бота від усіх голосових каналів, якщо вимкнули войс-гард
            for vc in self.bot.voice_clients: 
                await vc.disconnect()
        await interaction.response.send_message(f"🎙️ Войс-гард: **{'Увімкнено' if config.GLOBAL_SETTINGS['voice_guard'] else 'Вимкнено'}**")

    @app_commands.command(name="set_stats", description="Увімкнути/Вимкнути збір статистики")
    @app_commands.choices(стан=[
        app_commands.Choice(name="Увімкнути", value="on"),
        app_commands.Choice(name="Вимкнути", value="off")
    ])
    async def set_stats_cmd(self, interaction: discord.Interaction, стан: app_commands.Choice[str]):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Тільки адміни", ephemeral=True)
            
        config.GLOBAL_SETTINGS["voice_stats"] = (стан.value == "on")
        await interaction.response.send_message(f"📊 Статистика: **{'Увімкнено' if config.GLOBAL_SETTINGS['voice_stats'] else 'Вимкнено'}**")

# Функція завантаження кога
async def setup(bot):
    await bot.add_cog(CommandsCog(bot))