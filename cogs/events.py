import discord
from discord.ext import commands, tasks
import asyncio
from datetime import datetime, timezone, timedelta
from core import config, database, utils

def get_valid_games(member):
    """
    Повертає список усіх валідних ігор, у які зараз грає користувач.
    """
    if not member.activities: 
        return []
        
    games = []
    for act in member.activities:
        if getattr(act, 'type', None) == discord.ActivityType.custom or isinstance(act, discord.CustomActivity): 
            continue
        if getattr(act, 'name', '') == "Spotify": 
            continue
            
        act_name = getattr(act, 'name', None)
        if act_name: 
            if act_name not in games:
                games.append(act_name)
    return games

class EventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_greeted = {}

    async def cog_load(self):
        self.midnight_streak_check.start()

    async def cog_unload(self):
        self.midnight_streak_check.cancel()

    @tasks.loop(minutes=5)
    async def midnight_streak_check(self):
        """Every 5 min, give streak to everyone currently in voice."""
        if not config.GLOBAL_SETTINGS["voice_stats"]:
            return
        for uid in list(config.voice_start_times.keys()):
            database.update_streak(uid)

    @midnight_streak_check.before_loop
    async def before_midnight_check(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):

        if member.id == self.bot.user.id:
            if before.channel and not after.channel:
                # Bot was kicked from voice
                if config.GLOBAL_SETTINGS["voice_guard"]:
                    await asyncio.sleep(5)
                    await utils.join_voice_safe(self.bot)
                return
            elif before.channel and after.channel and before.channel != after.channel:
                # Bot was moved to another channel
                if config.GLOBAL_SETTINGS["voice_guard"]:
                    await asyncio.sleep(2)
                    await utils.join_voice_safe(self.bot)
                return

        if member.bot or not config.GLOBAL_SETTINGS["voice_stats"]: 
            return
            
        now = datetime.now().timestamp()

        if not before.channel and after.channel:
            config.voice_start_times[member.id] = now
            config.voice_last_save[member.id] = now
            database.update_streak(member.id)
            database.save_voice_sessions()
            print(f"JOIN: {member.name}")

        elif before.channel and not after.channel:
            if member.id in config.voice_start_times:
                start_time = config.voice_start_times.pop(member.id)
                last_save = config.voice_last_save.pop(member.id, start_time)
                duration = now - last_save 
                
                database.add_voice_time_only(member.id, duration)
                database.save_voice_sessions()

        if after.channel and before.channel != after.channel:
            vc = discord.utils.get(self.bot.voice_clients, guild=member.guild)
            
            if vc and vc.channel and after.channel.id == vc.channel.id:
                
                last_time = self.last_greeted.get(member.id, 0)
                
                if now - last_time > 1800: 
                    self.last_greeted[member.id] = now
                    
                    greeting = f"Привіт, {member.display_name}!"
                    
                    async def delayed_greeting():
                        await asyncio.sleep(1.5)
                        await utils.play_tts(greeting, member.guild, self.bot)
                    
                    self.bot.loop.create_task(delayed_greeting())

    @commands.Cog.listener()
    async def on_presence_update(self, before, after):
        if not config.GLOBAL_SETTINGS["monitoring"] or after.bot: 
            return
            
        await asyncio.sleep(1)
        guild = after.guild
        
        after_games = get_valid_games(after)
        current_sessions = config.game_sessions.get(after.id, {})
        
        changed = False
        now = datetime.now().timestamp()
        
        for game in list(current_sessions.keys()):
            if game not in after_games:
                sess = current_sessions[game]
                dur = now - sess["start_time"]
                
                try:
                    database.add_game_time_only(after.id, dur, game)
                except Exception as e:
                    print(f"Error saving game time for {game}: {e}")
                
                del current_sessions[game]
                
                norm_ended = database.normalize_game_name(game)
                
                still_playing = False
                for uid, user_sessions in config.game_sessions.items():
                    for g in user_sessions.keys():
                        if database.normalize_game_name(g) == norm_ended:
                            still_playing = True
                            break
                    if still_playing: break
                            
                if not still_playing and norm_ended in config.active_rooms:
                    del config.active_rooms[norm_ended]
                    
                changed = True

        for game in after_games:
            if game not in current_sessions:
                current_sessions[game] = {
                    "start_time": now, 
                    "session_start": now
                }
                
                norm_started = database.normalize_game_name(game)
                
                if norm_started not in config.active_rooms:
                    config.active_rooms[norm_started] = now
                    
                changed = True

        if current_sessions:
            config.game_sessions[after.id] = current_sessions
        elif after.id in config.game_sessions:
            del config.game_sessions[after.id]

        if changed:
            database.save_game_sessions()
            database.save_active_rooms()
            await utils.update_live_message(guild, self.bot)

async def setup(bot):
    await bot.add_cog(EventsCog(bot))