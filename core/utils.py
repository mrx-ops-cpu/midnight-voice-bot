import discord
import asyncio
import os
import shutil
import subprocess
import tempfile
import hashlib
import json
from datetime import datetime, timezone
import edge_tts

from core import config, database

def ensure_ffmpeg():
    found = shutil.which("ffmpeg")
    if found: return found
    try:
        subprocess.run(["apt-get", "update", "-qq"], capture_output=True, timeout=60)
        subprocess.run(["apt-get", "install", "-y", "-qq", "ffmpeg"], capture_output=True, timeout=120)
        return shutil.which("ffmpeg")
    except Exception as e:
        print(f"apt failed: {e}")
    return None

FFMPEG_PATH = ensure_ffmpeg()

def format_time(seconds):
    try: seconds = float(seconds)
    except: seconds = 0.0
    
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
    return f" 🔥{s}" if s > 0 else ""

def fame_streak_emoji(uid):
    s = database.get_fame_streak(uid)
    return f"|(в топі {s} дн.)" if s > 0 else ""

def get_embed_hash(embed: discord.Embed) -> str:
    """Створює унікальний хеш для вмісту embed (ігноруючи час оновлення)"""
    d = embed.to_dict()
    if 'timestamp' in d:
        del d['timestamp']
    return hashlib.md5(json.dumps(d, sort_keys=True).encode('utf-8')).hexdigest()

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
    # Спочатку перевіряємо збережений канал, потім фолбек на VOICE_ID
    from core import database
    saved_id = database.load_bot_voice()
    channel_id = saved_id if saved_id else config.VOICE_ID
    ch = bot.get_channel(channel_id)
    if not ch: 
        # Якщо збережений канал не знайдено — пробуємо дефолтний
        ch = bot.get_channel(config.VOICE_ID)
    if not ch: return
    vc = discord.utils.get(bot.voice_clients, guild=ch.guild)
    if not vc:
        try: await ch.connect(timeout=20.0, reconnect=True)
        except Exception as e: print(f"ERROR join_voice: {e}")
    elif vc.channel.id != ch.id:
        await vc.move_to(ch)

async def play_tts(text, guild, bot):
    tmp_name = None
    try:
        ffmpeg = FFMPEG_PATH or shutil.which("ffmpeg")
        if not ffmpeg:
            print("ERROR play_tts: ffmpeg не знайдено")
            return

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_name = tmp.name

        from gtts import gTTS
        tts = gTTS(text=text, lang='uk', slow=False)
        tts.save(tmp_name)
        print(f"🔊 TTS: файл збережено {tmp_name} (Google Translate)")

        vc = discord.utils.get(bot.voice_clients, guild=guild)
        if not vc:
            await join_voice_safe(bot)
            await asyncio.sleep(2)
            vc = discord.utils.get(bot.voice_clients, guild=guild)

        if not vc:
            print("ERROR play_tts: голосовий канал не знайдено")
            return

        # Чекаємо поки закінчить грати (з тайм-аутом 30с)
        waited = 0
        while vc.is_playing() and waited < 30:
            await asyncio.sleep(0.5)
            waited += 0.5

        print(f"🔊 TTS: починаю відтворення...")
        
        finished = asyncio.Event()
        
        def after_play(error):
            if error:
                print(f"ERROR play_tts after: {error}")
            finished.set()
        
        vc.play(
            discord.FFmpegPCMAudio(tmp_name, executable=ffmpeg),
            after=after_play
        )

        # Чекаємо завершення з тайм-аутом 60с
        try:
            await asyncio.wait_for(finished.wait(), timeout=60)
        except asyncio.TimeoutError:
            print("⚠️ TTS: тайм-аут відтворення")

        print(f"✅ TTS: відтворення завершено")

    except Exception as e:
        print(f"ERROR play_tts: {e}")
        import traceback
        traceback.print_exc()
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
        if not isinstance(user_sessions, dict): continue
        for game, sess in user_sessions.items():
            if not isinstance(sess, dict): continue
            
            norm_game = database.normalize_game_name(game)
            
            if norm_game not in rooms:
                room_start = config.active_rooms.get(norm_game, sess.get("session_start", now))
                try: room_dur = int(now - float(room_start))
                except: room_dur = 0
                
                rooms[norm_game] = {
                    "room_dur": room_dur,
                    "players": []
                }
                
            player_name = database.get_display_name(uid, guild, bot)
            
            try: player_dur = int(now - float(sess.get("session_start", sess.get("start_time", now))))
            except: player_dur = 0
            
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

def get_user_avatar(uid, guild, bot):
    try:
        m = guild.get_member(int(uid)) if guild else None
        if m and m.display_avatar: return m.display_avatar.url
        if bot:
            u = bot.get_user(int(uid))
            if u and u.display_avatar: return u.display_avatar.url
    except: pass
    return ""

async def update_fame_message(guild, bot):
    from core import image_gen
    monitor_id = database.load_monitor_channel() or config.GAMING_MONITOR_ID
    ch = bot.get_channel(monitor_id)
    if not ch: return
    
    s = database.load_stats()
    
    # --- VOICE DATA ---
    total = dict(s.get("total", {}))
    for uid, start in config.voice_start_times.items():
        k = str(uid)
        last_save = config.voice_last_save.get(uid, start)
        try:
            total[k] = float(total.get(k, 0)) + (datetime.now().timestamp() - float(last_save))
        except: pass
        
    top3_voice = sorted(total.items(), key=lambda x: float(x[1]) if isinstance(x[1], (int, float)) else 0, reverse=True)[:3]
    top_voice_data = []
    for uid, sec in top3_voice:
        name = database.get_display_name(uid, guild, bot)
        avatar = get_user_avatar(uid, guild, bot)
        top_voice_data.append({"name": name, "time": format_time(sec), "avatar_url": avatar})

    # --- STREAKS DATA ---
    voice_streaks_data = s.get("streaks", {})
    active_streaks = {}
    for uid_str, entry in voice_streaks_data.items():
        streak = database.get_streak(uid_str)
        if streak > 0:
            active_streaks[uid_str] = streak

    top3_streaks = sorted(active_streaks.items(), key=lambda x: x[1], reverse=True)[:3]
    top_streaks_data = []
    for uid_str, streak_count in top3_streaks:
        name = database.get_display_name(uid_str, guild, bot)
        avatar = get_user_avatar(uid_str, guild, bot)
        top_streaks_data.append({"name": name, "streak": f"{streak_count} днів підряд", "avatar_url": avatar})

    # --- GAMES DATA ---
    top_games = database.get_top_games(limit_games=5, limit_players=1)
    top_games_data = []
    
    game_icons = {
        "cs2": "https://cdn.akamai.steamstatic.com/steamcommunity/public/images/apps/730/69f7ebe2735c366c65c0b33dae00e12dc40edbe4.jpg",
        "dota 2": "https://cdn.akamai.steamstatic.com/steamcommunity/public/images/apps/570/0b00f1c1bad8a0699bc22bc9ed6f93d3950b73c4.jpg",
        "gta v": "https://cdn.akamai.steamstatic.com/steamcommunity/public/images/apps/271590/1e72f87eb927fa1485e68aefaff23c7fd7178051.jpg",
        "rust": "https://cdn.akamai.steamstatic.com/steamcommunity/public/images/apps/252490/4dfb2d6ffbb495d4f10738e4aee4a706da62828e.jpg",
        "pubg": "https://cdn.akamai.steamstatic.com/steamcommunity/public/images/apps/578080/2d49cfbb32c0201d810ba2d1ba704d2bfb2ca617.jpg"
    }

    if top_games:
        for game, data in top_games.items():
            icon_url = game_icons.get(game.lower(), "")
            mvp_data = None
            if data["players"]:
                mvp_uid, mvp_sec = data["players"][0]
                mvp_name = database.get_display_name(mvp_uid, guild, bot)
                mvp_avatar = get_user_avatar(mvp_uid, guild, bot)
                mvp_data = {"name": mvp_name, "time": format_time(mvp_sec), "avatar_url": mvp_avatar}
            
            top_games_data.append({
                "name": game,
                "time": format_time(data['total']),
                "icon_url": icon_url,
                "mvp": mvp_data
            })

    # Generate images
    voice_file = discord.File(await image_gen.generate_voice_image(top_voice_data), filename="fame_voice.png")
    streaks_file = discord.File(await image_gen.generate_streaks_image(top_streaks_data), filename="fame_streaks.png")
    games_file = discord.File(await image_gen.generate_games_image(top_games_data), filename="fame_games.png")

    # Hashes (serialize data dicts to check for changes)
    def hash_data(d): return hashlib.md5(json.dumps(d, sort_keys=True).encode('utf-8')).hexdigest()
    
    current_voice_hash = hash_data(top_voice_data)
    current_streaks_hash = hash_data(top_streaks_data)
    current_games_hash = hash_data(top_games_data)
    
    async def update_msg(msg_id_attr, hash_attr, current_hash, file_obj):
        saved_hash = getattr(config, hash_attr, None)
        msg_id = getattr(config, msg_id_attr, None)
        
        if saved_hash == current_hash and msg_id:
            return msg_id # No change needed
            
        if msg_id:
            try:
                msg = await ch.fetch_message(msg_id)
                await msg.edit(attachments=[file_obj], embed=None)
                setattr(config, hash_attr, current_hash)
                return msg_id
            except discord.NotFound:
                setattr(config, msg_id_attr, None)
                
        # Send new
        msg = await ch.send(file=file_obj)
        setattr(config, hash_attr, current_hash)
        return msg.id

    # Update messages
    config.fame_games_msg_id = await update_msg('fame_games_msg_id', 'last_fame_games_hash', current_games_hash, games_file)
    config.fame_voice_msg_id = await update_msg('fame_voice_msg_id', 'last_fame_voice_hash', current_voice_hash, voice_file)
    config.fame_streaks_msg_id = await update_msg('fame_streaks_msg_id', 'last_fame_streaks_hash', current_streaks_hash, streaks_file)
    
    database.save_message_ids()

async def update_live_message(guild, bot):
    monitor_id = database.load_monitor_channel() or config.GAMING_MONITOR_ID
    ch = bot.get_channel(monitor_id)
    if not ch: return
    embed = build_live_embed(guild, bot)
    
    current_hash = get_embed_hash(embed)
    if getattr(config, 'last_live_hash', None) == current_hash:
        return # Якщо вміст не змінився — пропускаємо запит до Discord
        
    if config.live_message_id:
        try:
            msg = await ch.fetch_message(config.live_message_id)
            await msg.edit(embed=embed)
            config.last_live_hash = current_hash
            return
        except discord.NotFound:
            config.live_message_id = None
            
    try:
        async for msg in ch.history(limit=30):
            if msg.author.id == bot.user.id and msg.embeds and "Активні" in (msg.embeds[0].title or ""):
                config.live_message_id = msg.id
                await msg.edit(embed=embed)
                config.last_live_hash = current_hash
                database.save_message_ids()
                return
    except: pass
    
    msg = await ch.send(embed=embed)
    config.live_message_id = msg.id
    config.last_live_hash = current_hash
    database.save_message_ids()

# Build fame embed removed
