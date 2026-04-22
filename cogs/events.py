import discord
from discord.ext import commands
import asyncio
from datetime import datetime
from core import config, database, utils

def get_game_name(member):
    if not member.activities: 
        return None
        
    valid_acts = []
    for act in member.activities:
        if isinstance(act, discord.CustomActivity) or act.name == "Spotify": 
            continue
        if hasattr(act, 'name') and act.name: 
            valid_acts.append(act)
            
    if not valid_acts:
        return None
        
    valid_acts.sort(
        key=lambda a: a.created_at.timestamp() if hasattr(a, 'created_at') and a.created_at else 0, 
        reverse=True
    )
    
    return valid_acts[0].name

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
        
        after_game = get_game_name(after)
        current_saved_game = config.game_sessions.get(after.id, {}).get("game")
        
        if current_saved_game == after_game: 
            return

        changed = False
        now = datetime.now().timestamp()

        if current_saved_game and current_saved_game != after_game:
            dur = now - config.game_sessions[after.id]["start_time"]
            database.add_game_time_only(after.id, dur, current_saved_game)
            del config.game_sessions[after.id]
            
            norm_ended = database.normalize_game_name(current_saved_game)
            still_playing = any(database.normalize_game_name(s["game"]) == norm_ended for s in config.game_sessions.values())
            if not still_playing and norm_ended in config.active_rooms:
                del config.active_rooms[norm_ended]
                
            changed = True

        if after_game and current_saved_game != after_game:
            config.game_sessions[after.id] = {
                "game": after_game, 
                "start_time": now, 
                "session_start": now
            }
            
            norm_started = database.normalize_game_name(after_game)
            if norm_started not in config.active_rooms:
                config.active_rooms[norm_started] = now
                
            changed = True

        if changed:
            database.save_game_sessions()
            database.save_active_rooms()
            await utils.update_fame_message(guild, self.bot)
            await utils.update_live_message(guild, self.bot)

async def setup(bot):
    await bot.add_cog(EventsCog(bot))