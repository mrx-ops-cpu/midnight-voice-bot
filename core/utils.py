import discord
import asyncio
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from gtts import gTTS

from core import config, database

# ── Перевірка та встановлення FFmpeg ─────────────────────────
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

# ── Форматування та Дизайн ───────────────────────────────────
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

def get_short_title(game):
    return config.SHORT_TITLES.get(game, f"🎮 {game[:14]}")

# ── Ліміти команди /say ──────────────────────────────────────
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

# ── Робота з Голосом (TTS & Войс-гард) ───────────────────────
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
    try:
        ffmpeg = FFMPEG_PATH or shutil.which("ffmpeg")
        if not ffmpeg:
            print("ERROR play_tts: ffmpeg не знайдено")
            return
            
        tts = gTTS(text=text, lang="uk")
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tts.save(tmp.name)
        tmp.close()
        
        vc = discord.utils.get(bot.voice_clients, guild=guild)
        if not vc:
            await join_voice_safe(bot)
            await asyncio.sleep(2)
            vc = discord.utils.get(bot.voice_clients, guild=guild)
            
        if not vc:
            os.remove(tmp.name)
            return
            
        while vc.is_playing(): await asyncio.sleep(0.5)
        vc.play(discord.FFmpegPCMAudio(tmp.name, executable=ffmpeg))
        while vc.is_playing(): await asyncio.sleep(0.5)
        
        os.remove(tmp.name)
    except Exception as e:
        print(f"ERROR play_tts: {e}")

# ── Створення Embeds ─────────────────────────────────────────
def build_live_embed():
    embed = discord.Embed(title="🎮 Активні катки", color=0x57F287, timestamp=datetime.now(timezone.utc))
    if not config.active_games:
        embed.description = "*Зараз ніхто не грає*"
        return embed
        
    lines = []
    for name, data in config.active_games.items():
        dur = int(datetime.now().timestamp() - data["start_time"])
        names = ", ".join(data["players"]) if data["players"] else "?"
        lines.append(f"**{name}**\n👥 {names}\n⏱️ {format_time(dur)}\n")
        
    embed.description = "\n".join(lines)
    embed.set_footer(text="🔴 Live • Оновлюється автоматично")
    return embed

def build_fame_embed(guild, bot):
    embed = discord.Embed(title="🏛️ Зал Слави", color=0xf1c40f, timestamp=datetime.now(timezone.utc))
    s = database.load_stats()
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣"]

    # Топ войсу — з урахуванням поточних сесій
    total = dict(s.get("total", {}))
    for uid, start in config.voice_start_times.items():
        k = str(uid)
        total[k] = total.get(k, 0) + (datetime.now().timestamp() - start)
        
    top3 = sorted(total.items(), key=lambda x: x[1], reverse=True)[:3]
    lines = [f"{medals[i]} **{database.get_display_name(uid, guild, bot)}**{streak_emoji(uid)} — `{format_time(sec)}`"
             for i, (uid, sec) in enumerate(top3)]
    embed.add_field(name="🎙️ Топ войсу", value="\n".join(lines) if lines else "*Немає даних*", inline=False)

    # Топ-3 ігри
    top_games = database.get_top_games(3, 5)
    if top_games:
        for game, data in top_games.items():
            title = get_short_title(game)
            plines = [f"{medals[i] if i<len(medals) else '•'} {database.get_display_name(uid, guild, bot)} — `{format_time(sec)}`"
                      for i, (uid, sec) in enumerate(data["players"])]
            embed.add_field(name=f"{title}  ·  {format_time(data['total'])} загалом", value="\n".join(plines), inline=False)
    else:
        embed.add_field(name="🎮 Ігри", value="*Ще немає даних*", inline=False)

    embed.set_footer(text="⭐ Зал Слави • Оновлюється автоматично")
    return embed

# ── Оновлення Повідомлень (Live Message Updater) ─────────────
async def update_live_message(guild, bot):
    ch = bot.get_channel(config.GAMING_MONITOR_ID)
    if not ch: return
    embed = build_live_embed()
    embed.set_footer(text=midnight_footer())
    
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
    embed.set_footer(text=midnight_footer())
    
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