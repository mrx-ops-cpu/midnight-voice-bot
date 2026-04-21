import discord
from discord.ext import commands, tasks
from datetime import datetime, time, timezone

# Імпортуємо наші модулі
from core import config, database, utils

class TasksCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Запускаємо фонові задачі при ініціалізації Кога
        self.periodic_save.start()
        self.daily_report.start()

    def cog_unload(self):
        # Зупиняємо задачі, якщо Ког буде вивантажено (reload)
        self.periodic_save.cancel()
        self.daily_report.cancel()

    # ── Periodic save (кожні 2 хв) ───────────────────────────────
    @tasks.loop(minutes=2)
    async def periodic_save(self):
        """
        Кожні 2 хвилини зберігає:
        - войс-сесії → total + daily + games
        - ігрові сесії без войсу → тільки games
        Один load/save для всіх.
        """
        if not config.GLOBAL_SETTINGS["voice_stats"]: 
            return
            
        now = datetime.now().timestamp()
        s = database.load_stats()
        sv, sg = 0, 0

        # Обробка Войсу
        for uid, start in list(config.voice_start_times.items()):
            dur = now - start
            if dur < 30: continue # Не зберігаємо сесії менше 30 секунд
            k = str(uid)
            game = config.game_sessions.get(uid, {}).get("game")
            
            s["total"][k] = s["total"].get(k, 0) + dur
            s["daily"][k] = s["daily"].get(k, 0) + dur
            
            if game:
                s.setdefault("games", {}).setdefault(k, {})[game] = s["games"][k].get(game, 0) + dur
                
            config.voice_start_times[uid] = now
            if uid in config.game_sessions:
                config.game_sessions[uid]["start_time"] = now
            sv += 1

        # Обробка Ігор без войсу
        for uid, sess in list(config.game_sessions.items()):
            if uid in config.voice_start_times: 
                continue  # вже оброблено у циклі вище
                
            dur = now - sess["start_time"]
            if dur < 30: continue
            k = str(uid)
            game = sess["game"]
            
            s.setdefault("games", {}).setdefault(k, {})[game] = s["games"][k].get(game, 0) + dur
            config.game_sessions[uid]["start_time"] = now
            sg += 1

        # Якщо були зміни, зберігаємо у файли
        if sv > 0 or sg > 0:
            database.save_stats(s)
            database.save_game_sessions()
            print(f"PERIODIC: войс={sv} ігри={sg}")

    @periodic_save.before_loop
    async def before_periodic_save(self):
        """Чекаємо, поки бот повністю завантажиться, перш ніж почати збереження"""
        await self.bot.wait_until_ready()

    # ── Щоденний звіт ────────────────────────────────────────────
    @tasks.loop(time=time(hour=0, minute=0, tzinfo=timezone.utc))
    async def daily_report(self):
        if not config.GLOBAL_SETTINGS["voice_stats"]: 
            return
            
        # 1. Фінально зберігаємо поточні сесії перед скиданням дня
        now = datetime.now().timestamp()
        s = database.load_stats()
        
        for uid, start in list(config.voice_start_times.items()):
            dur = now - start
            k = str(uid)
            game = config.game_sessions.get(uid, {}).get("game")
            
            s["total"][k] = s["total"].get(k, 0) + dur
            s["daily"][k] = s["daily"].get(k, 0) + dur
            
            if game:
                s.setdefault("games", {}).setdefault(k, {})[game] = s["games"][k].get(game, 0) + dur
                
            config.voice_start_times[uid] = now
            if uid in config.game_sessions:
                config.game_sessions[uid]["start_time"] = now
                
        database.save_stats(s)

        # 2. Формуємо звіт для каналу
        ch = self.bot.get_channel(config.GAMING_LOG_ID)
        s2 = database.load_stats()
        top = sorted(s2.get("daily", {}).items(), key=lambda x: x[1], reverse=True)[:5]
        
        if not top or not ch:
            # Якщо ніхто не сидів, просто скидаємо і виходимо
            s2["daily"] = {}
            database.save_stats(s2)
            return

        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        guild = self.bot.guilds[0] if self.bot.guilds else None
        lines = []
        
        for i, (uid, sec) in enumerate(top):
            display_name = database.get_display_name(uid, guild, self.bot)
            emoji = utils.streak_emoji(uid)
            time_str = utils.format_time(sec)
            lines.append(f"{medals[i]} {display_name}{emoji} — {time_str}")
            
        embed = discord.Embed(
            title="📊 Підсумки дня", 
            description="\n".join(lines),
            color=0x9b59b6, 
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text=utils.midnight_footer())
        
        # 3. Відправляємо звіт
        await ch.send(embed=embed)
        
        # 4. Очищаємо денну статистику
        s2["daily"] = {}
        database.save_stats(s2)
        print("DAILY RESET done")

    @daily_report.before_loop
    async def before_daily_report(self):
        """Чекаємо, поки бот підключиться до Discord API"""
        await self.bot.wait_until_ready()

# Функція завантаження кога
async def setup(bot):
    await bot.add_cog(TasksCog(bot))