import discord
import asyncio
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from gtts import gTTS

from core import config, database

def ensure_ffmpeg():
    found = shutil.which("ffmpeg")
    if found: return found
    print("FFmpeg не знайдено — встановлюю (через apt-get)...")
    try:
        subprocess.run(["apt-get", "update", "-qq"], capture_output=True, timeout=60)
        subprocess.run(["apt-get", "install", "-y", "-qq", "ffmpeg"], capture_output=True, timeout=120)
        return shutil.which("ffmpeg")
    except Exception as e:
        print(f"apt failed: {e}")
    return None

FFMPEG_PATH = ensure_ffmpeg()

def format_time(seconds):
    seconds = max(0, int(seconds))
    m_total = seconds // 60
    if m_total == 0: return "< 1хв"
    h, m = m_total // 60, m_total % 60
    if h == 0:  return f"{m}хв"
    if m == 0:  return f"{h}г"
    return f"{h}г {m}хв"

def midnight_footer():
    return f"🌑 Midnight System • {datetime.now(timezone.utc).strftime('%H:%M UTC')}"

def streak_emoji(uid):
    s = database.get_streak(uid)
    return f" 🔥{s}" if s >= 3 else ""

def check_say_limit(user_id):
    if config.SAY_LIMIT == 0: return True, 0, 0
    now = datetime.now().timestamp()
    hour_ago = now - 3600
    
    usage = [t for t in config.say_usage.get(user_id, []) if t > hour_ago]
    config.say_usage[user_id] = usage
    remaining = config.SAY_LIMIT - len(usage)
    
    if remaining <= 0:
        reset_in = int(usage[0] + 3600 - now)
        return False, 0, reset_in
    return True, remaining, 0

def record_say_usage(user_id):
    config.say_usage.setdefault(user_id, []).append(datetime.now().timestamp())

async def join_voice_safe(bot):
    if not config.GLOBAL_SETTINGS["voice_guard"]: return
    ch = bot.get_channel(config.VOICE_ID)
    if not ch: return
    vc = discord.utils.get(bot.voice_clients, guild=ch.guild)
    if not vc:
        try: await ch.connect(timeout=20.0, reconnect=True)
        except Exception as e: print(f"ERROR join_voice: {e}")
    elif vc.channel.id != config.VOICE_ID:
        await vc.move_to(ch)

async def play_tts(text, guild, bot):
    tmp_name = None
    try:
        ffmpeg = FFMPEG_PATH or shutil.which("ffmpeg")
        if not ffmpeg:
            print("ERROR play_tts: ffmpeg не знайдено")
            return
            
        tts = gTTS(text=text, lang="uk")
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_name = tmp.name
            
        await bot.loop.run_in_executor(None, tts.save, tmp_name)
        
        vc = discord.utils.get(bot.voice_clients, guild=guild)
        if not vc:
            await join_voice_safe(bot)
            await asyncio.sleep(2)
            vc = discord.utils.get(bot.voice_clients, guild=guild)
            
        if not vc:
            return
            
        while vc.is_playing(): 
            await asyncio.sleep(0.5)
            
        vc.play(discord.FFmpegPCMAudio(tmp_name, executable=ffmpeg))
        
        while vc.is_playing(): 
            await asyncio.sleep(0.5)
            
    except Exception as e:
        print(f"ERROR play_tts: {e}")
    finally:
        if tmp_name and os.path.exists(tmp_name):
            try:
                os.remove(tmp_name)
            except:
                pass

def build_live_embed(guild, bot):
    embed = discord.Embed(title="🎮 Активні катки", color=0x57F287, timestamp=datetime.now(timezone.utc))
    if not config.game_sessions:
        embed.description = "*Зараз ніхто не грає*"
        embed.set_footer(text="🔴 Live • Оновлюється автоматично")
        return embed
        
    now = datetime.now().timestamp()
    rooms = {}
    
    for uid, user_sessions in config.game_sessions.items():
        for game, sess in user_sessions.items():
            norm_game = database.normalize_game_name(game)
            
            if norm_game not in rooms:
                room_start = config.active_rooms.get(norm_game, sess.get("session_start", now))
                rooms[norm_game] = {
                    "room_dur": int(now - room_start),
                    "players": []
                }
                
            player_name = database.get_display_name(uid, guild, bot)
            player_dur = int(now - sess.get("session_start", sess["start_time"]))
            rooms[norm_game]["players"].append((player_name, player_dur))
        
    sorted_rooms = sorted(rooms.items(), key=lambda x: x[1]["room_dur"], reverse=True)[:10]
    
    lines = []
    for game, data in sorted_rooms:
        lines.append(f"**🎮 {game}** ·  ⏱️ `{format_time(data['room_dur'])}`")
        players_sorted = sorted(data["players"], key=lambda x: x[1], reverse=True)
        for p_name, p_dur in players_sorted:
            lines.append(f"└ 👥 {p_name} — `{format_time(p_dur)}`")
        lines.append("") 
        
    embed.description = "\n".join(lines).strip()
    embed.set_footer(text="🔴 Live • Топ 10 • Оновлюється автоматично")
    return embed

def build_fame_embed(guild, bot):
    embed = discord.Embed(title="🏛️ Зал Слави", color=0xf1c40f, timestamp=datetime.now(timezone.utc))
    s = database.load_stats()
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣"]

    total = dict(s.get("total", {}))
    for uid, start in config.voice_start_times.items():
        k = str(uid)
        last_save = config.voice_last_save.get(uid, start)
        total[k] = total.get(k, 0) + (datetime.now().timestamp() - last_save)
        
    top3_voice = sorted(total.items(), key=lambda x: x[1], reverse=True)[:3]
    voice_lines = []
    for i, (uid, sec) in enumerate(top3_voice):
        name = database.get_display_name(uid, guild, bot)
        voice_lines.append(f"{medals[i]} **{name}**{streak_emoji(uid)} — `{format_time(sec)}`")
        
    embed.add_field(name="🎙️ Топ войсу (За весь час)", value="\n".join(voice_lines) if voice_lines else "*Немає даних*", inline=False)

    top_games = database.get_top_games(limit_games=10, limit_players=3) 
    if top_games:
        for game, data in top_games.items():
            plines = []
            for i, (uid, sec) in enumerate(data["players"]):
                name = database.get_display_name(uid, guild, bot)
                plines.append(f"{medals[i]} {name} — `{format_time(sec)}`")
            
            embed.add_field(
                name=f"🎮 {game}  ·  {format_time(data['total'])} загалом", 
                value="\n".join(plines), 
                inline=False
            )
    else:
        embed.add_field(name="🎮 Ігри", value="*Ще немає даних*", inline=False)

    embed.set_footer(text="⭐ Зал Слави • Накопичується назавжди")
    return embed

async def update_live_message(guild, bot):
    ch = bot.get_channel(config.GAMING_MONITOR_ID)
    if not ch: return
    embed = build_live_embed(guild, bot)
    
    if config.live_message_id:
        try:
            msg = await ch.fetch_message(config.live_message_id)
            await msg.edit(embed=embed)
            return
        except discord.NotFound:
            config.live_message_id = None
            
    try:
        async for msg in ch.history(limit=30):
            if msg.author.id == bot.user.id and msg.embeds and "Активні" in (msg.embeds[0].title or ""):
                config.live_message_id = msg.id
                await msg.edit(embed=embed)
                database.save_message_ids()
                return
    except: pass
    
    msg = await ch.send(embed=embed)
    config.live_message_id = msg.id
    database.save_message_ids()

async def update_fame_message(guild, bot):
    ch = bot.get_channel(config.GAMING_MONITOR_ID)
    if not ch: return
    embed = build_fame_embed(guild, bot)
    
    if config.fame_message_id:
        try:
            msg = await ch.fetch_message(config.fame_message_id)
            await msg.edit(embed=embed)
            return
        except discord.NotFound:
            config.fame_message_id = None
            
    try:
        async for msg in ch.history(limit=30):
            if msg.author.id == bot.user.id and msg.embeds and "Слави" in (msg.embeds[0].title or ""):
                config.fame_message_id = msg.id
                await msg.edit(embed=embed)
                database.save_message_ids()
                return
    except: pass
    
    msg = await ch.send(embed=embed)
    config.fame_message_id = msg.id
    database.save_message_ids()