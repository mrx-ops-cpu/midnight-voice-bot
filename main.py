import discord
from discord.ext import commands
import os
import asyncio
from datetime import datetime, timezone
from threading import Thread
from flask import Flask, render_template

from dotenv import load_dotenv
load_dotenv()

from core import config, database, utils

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents, chunk_guilds_at_startup=True)

app = Flask(__name__, template_folder="templates")
bot.app = app

@app.route('/')
def home():
    voice_online = len(config.voice_start_times)
    now = datetime.now().timestamp()
    
    rooms_data = {}
    
    for uid, user_sessions in list(config.game_sessions.items()):
        for game, sess in user_sessions.items():
            norm_game = database.normalize_game_name(game)
            
            if norm_game not in rooms_data:
                room_start = config.active_rooms.get(norm_game, sess.get("session_start", now))
                rooms_data[norm_game] = {
                    "room_dur": int(now - room_start),
                    "players": []
                }
                
            name = database.get_display_name(uid, None, bot)
            rooms_data[norm_game]["players"].append(name)
        
    games = []
    for name, data in sorted(rooms_data.items(), key=lambda x: x[1]["room_dur"], reverse=True)[:10]:
        games.append({
            "name": name,
            "time": utils.format_time(data["room_dur"]),
            "players": ", ".join(data["players"])
        })
        
    s = database.load_stats()
    total = dict(s.get("total", {}))
    
    for uid, start in list(config.voice_start_times.items()):
        k = str(uid)
        total[k] = total.get(k, 0) + (now - start)
        
    top_users = []
    for uid, sec in sorted(total.items(), key=lambda x: x[1], reverse=True)[:5]:
        name = database.get_display_name(uid, None, bot)
        top_users.append((name, utils.format_time(sec)))
        
    history = dict(s.get("history", {}))
    today_daily_sec = sum(s.get("daily", {}).values())
    
    for uid, start in list(config.voice_start_times.items()):
        today_daily_sec += (now - config.voice_last_save.get(uid, start))
        
    today_str = datetime.now(timezone.utc).strftime("%d.%m")
    
    if today_str in history:
        history[today_str] += today_daily_sec
    else:
        history[today_str] = today_daily_sec
        
    chart_labels = list(history.keys())[-7:]
    chart_data = [round(history[k] / 3600, 1) for k in chart_labels]
    
    if not chart_labels:
        chart_labels = ["Немає даних"]
        chart_data = [0]

    return render_template('dashboard.html', 
                           voice_online=voice_online, 
                           games=games, 
                           top_users=top_users,
                           chart_labels=chart_labels,
                           chart_data=chart_data)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, use_reloader=False)

def keep_alive():
    Thread(target=run_flask, daemon=True).start()

INITIAL_EXTENSIONS = [
    'cogs.events',
    'cogs.commands',
    'cogs.tasks',
    'cogs.faceit',
    'cogs.faceit_webhooks'
]

@bot.event
async def on_ready():
    print(f'\n--- Midnight {config.GLOBAL_SETTINGS["version"]} ONLINE ---')
    print(f'--- FFmpeg: {utils.FFMPEG_PATH} ---')
    
    database.load_message_ids()
    
    if getattr(bot, "synced", False) is False:
        await bot.tree.sync()
        bot.synced = True
    
    saved_gs = database.load_game_sessions()
    saved_vs = database.load_voice_sessions()
    saved_rooms = database.load_active_rooms()
    
    config.game_sessions.clear()
    config.active_rooms.clear()

    for r, t in saved_rooms.items():
        config.active_rooms[r] = t

    for guild in bot.guilds:
        for member in guild.members:
            if member.bot: continue
            
            valid_acts = []
            for a in member.activities:
                if getattr(a, 'type', None) == discord.ActivityType.custom or isinstance(a, discord.CustomActivity):
                    continue
                if getattr(a, 'name', '') == "Spotify":
                    continue
                if hasattr(a, 'name') and a.name:
                    valid_acts.append(a.name)
            valid_acts = list(set(valid_acts))
            
            if valid_acts and config.GLOBAL_SETTINGS["monitoring"]:
                user_sessions = {}
                for game in valid_acts:
                    if member.id in saved_gs and game in saved_gs.get(member.id, {}):
                        user_sessions[game] = saved_gs[member.id][game]
                    else:
                        user_sessions[game] = {"start_time": datetime.now().timestamp(), "session_start": datetime.now().timestamp()}
                config.game_sessions[member.id] = user_sessions

        for channel in guild.voice_channels:
            for member in channel.members:
                if member.bot: continue
                config.voice_start_times[member.id] = saved_vs.get(str(member.id), datetime.now().timestamp())
                config.voice_last_save[member.id] = datetime.now().timestamp()

    now = datetime.now().timestamp()
    
    active_games_now = set()
    for user_sessions in config.game_sessions.values():
        for game in user_sessions.keys():
            active_games_now.add(database.normalize_game_name(game))
    
    ghost_rooms = [r for r in config.active_rooms if r not in active_games_now]
    for gr in ghost_rooms:
        del config.active_rooms[gr]
        
    for user_sessions in config.game_sessions.values():
        for game, sess in user_sessions.items():
            norm_g = database.normalize_game_name(game)
            if norm_g not in config.active_rooms:
                config.active_rooms[norm_g] = sess.get("session_start", now)
                
    database.save_active_rooms()

    bot.loop.create_task(utils.update_fame_message(guild, bot))
    bot.loop.create_task(utils.update_live_message(guild, bot))

    database.save_voice_sessions()
    database.save_game_sessions()

    await asyncio.sleep(2)
    await utils.join_voice_safe(bot)
    
    print(f"READY: {len(config.voice_start_times)} у войсі | {len(config.active_rooms)} активних кімнат")

async def main():
    keep_alive()
    
    for extension in INITIAL_EXTENSIONS:
        try:
            await bot.load_extension(extension)
            print(f"✅ Модуль завантажено: {extension}")
        except Exception as e:
            print(f"❌ Помилка завантаження {extension}: {e}")

    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        print("❌ УВАГА: DISCORD_TOKEN не знайдено!")
        return
    
    await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())