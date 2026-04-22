import discord
from discord.ext import commands
import asyncio
from datetime import datetime
from core import config, database, utils

def get_valid_games(member):
    """
    Повертає список усіх валідних ігор, у які зараз грає користувач.
    Ігнорує Spotify та CustomActivity (користувацькі статуси).
    """
    if not member.activities: 
        return []
        
    games = []
    for act in member.activities:
        if isinstance(act, discord.CustomActivity) or act.name == "Spotify": 
            continue
        if hasattr(act, 'name') and act.name: 
            if act.name not in games:
                games.append(act.name)
    return games

class EventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.id == self.bot.user.id and before.channel and not after.channel:
            if config.GLOBAL_SETTINGS["voice_guard"]:
                await asyncio.sleep(5)
                await utils.join_voice_safe(self.bot)
            return

        if member.bot or not config.GLOBAL_SETTINGS["voice_stats"]: 
            return
            
        now = datetime.now().timestamp()

        if not before.channel and after.channel:
            config.voice_start_times[member.id] = now
            config.voice_last_save[member.id] = now
            database.save_voice_sessions()
            print(f"JOIN: {member.name}")

        elif before.channel and not after.channel:
            if member.id in config.voice_start_times:
                start_time = config.voice_start_times.pop(member.id)
                last_save = config.voice_last_save.pop(member.id, start_time)
                duration = now - last_save 
                
                database.add_voice_time_only(member.id, duration)
                database.save_voice_sessions()

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
                
                database.add_game_time_only(after.id, dur, game)
                
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
            await utils.update_fame_message(guild, self.bot)
            await utils.update_live_message(guild, self.bot)

async def setup(bot):
    await bot.add_cog(EventsCog(bot))