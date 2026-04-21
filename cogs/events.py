import discord
from discord.ext import commands
import asyncio
from datetime import datetime

# Імпортуємо наш стан, базу даних та допоміжні функції
from core import config, database, utils

def get_game_name(member):
    """Отримує назву гри, в яку зараз грає користувач."""
    if not member.activities: 
        return None
    for act in member.activities:
        # Ігноруємо кастомні статуси та Spotify
        if isinstance(act, discord.CustomActivity) or act.name == "Spotify": 
            continue
        if hasattr(act, 'name') and act.name: 
            return act.name
    return None


class EventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Обробка входів, виходів та переміщень у голосових каналах."""
        
        # 1. Войс-гард (авто-перепідключення бота, якщо його кікнули)
        if member.id == self.bot.user.id and before.channel and not after.channel:
            if config.GLOBAL_SETTINGS["voice_guard"]:
                await asyncio.sleep(5)
                # Викликаємо функцію з utils, передаючи їй об'єкт bot
                await utils.join_voice_safe(self.bot)
            return

        # Ігноруємо інших ботів або якщо статистика вимкнена
        if member.bot or not config.GLOBAL_SETTINGS["voice_stats"]: 
            return
            
        now = datetime.now().timestamp()

        # 2. Користувач ЗАЙШОВ у войс
        if not before.channel and after.channel:
            config.voice_start_times[member.id] = now
            database.save_voice_sessions()
            print(f"JOIN: {member.name}")

        # 3. Користувач ВИЙШОВ з войсу
        elif before.channel and not after.channel:
            if member.id in config.voice_start_times:
                duration = now - config.voice_start_times.pop(member.id)
                database.save_voice_sessions()
                
                # Перевіряємо, чи грав він у гру під час перебування у войсі
                game = config.game_sessions.get(member.id, {}).get("game")
                database.add_voice_time(member.id, duration, game)
                
                # Видаляємо ігрову сесію, щоб periodic_save не порахував її двічі
                if member.id in config.game_sessions:
                    del config.game_sessions[member.id]
                    database.save_game_sessions()
                    
                print(f"LEAVE: {member.name} | {utils.format_time(duration)}")
                
                # Оновлюємо таблицю Залу Слави
                asyncio.create_task(utils.update_fame_message(member.guild, self.bot))

        # 4. Користувач ПЕРЕЙШОВ з одного каналу в інший
        elif before.channel and after.channel and before.channel.id != after.channel.id:
            print(f"SWITCH: {member.name}")


    @commands.Cog.listener()
    async def on_presence_update(self, before, after):
        """Обробка зміни статусу активності (запуск/закриття ігор)."""
        
        # Ігноруємо ботів або якщо моніторинг вимкнено
        if not config.GLOBAL_SETTINGS["monitoring"] or after.bot: 
            return
            
        await asyncio.sleep(1) # Невелика затримка для стабілізації статусу Discord
        
        guild = after.guild
        before_game = get_game_name(before)
        after_game = get_game_name(after)
        
        # Якщо гра не змінилася (наприклад, змінився лише статус "В мережі/Відійшов")
        if before_game == after_game: 
            return

        changed = False
        now = datetime.now().timestamp()

        # 1. Гра ЗАКІНЧИЛАСЬ або შეიცვალა (була before_game)
        if before_game:
            # Рахуємо та записуємо час
            if after.id in config.game_sessions and config.game_sessions[after.id]["game"] == before_game:
                dur = now - config.game_sessions[after.id]["start_time"]
                database.add_game_time_only(after.id, dur, before_game)
                del config.game_sessions[after.id]
                database.save_game_sessions()
                
            # Оновлюємо глобальний словник активних ігор
            if before_game in config.active_games:
                players = [m.display_name for m in guild.members
                           if get_game_name(m) == before_game and not m.bot]
                if not players: 
                    del config.active_games[before_game] # Гра більше не активна
                else:           
                    config.active_games[before_game]["players"] = players
                changed = True

        # 2. ПОЧАЛАСЬ нова гра (є after_game)
        if after_game:
            config.game_sessions[after.id] = {"game": after_game, "start_time": now}
            database.save_game_sessions()
            
            # Збираємо всіх, хто зараз грає в цю гру
            players = [m.display_name for m in guild.members
                       if get_game_name(m) == after_game and not m.bot]
                       
            if players:
                if after_game not in config.active_games:
                    # Нова гра в списку
                    config.active_games[after_game] = {"players": players, "start_time": now}
                else:
                    # Оновлюємо список гравців для існуючої гри
                    config.active_games[after_game]["players"] = players
                changed = True

        # 3. Якщо були зміни, оновлюємо Live-повідомлення в моніторі
        if changed:
            await utils.update_fame_message(guild, self.bot)
            await utils.update_live_message(guild, self.bot)


# Функція, яку викликає bot.load_extension() у main.py
async def setup(bot):
    await bot.add_cog(EventsCog(bot))