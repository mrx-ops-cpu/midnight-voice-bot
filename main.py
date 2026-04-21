import discord
from discord.ext import commands, tasks
from discord import app_commands
from flask import Flask
from threading import Thread
import os, asyncio, json, shutil, subprocess
from datetime import datetime, date, time, timezone, timedelta

# ── FFmpeg ──────────────────────────────────────────────────
def ensure_ffmpeg():
    found = shutil.which("ffmpeg")
    if found:
        print(f"FFmpeg OK: {found}"); return found
    print("FFmpeg не знайдено — встановлюю...")
    try:
        subprocess.run(["apt-get","update","-qq"], capture_output=True, timeout=60)
        subprocess.run(["apt-get","install","-y","-qq","ffmpeg"], capture_output=True, timeout=120)
        found = shutil.which("ffmpeg")
        if found:
            print(f"FFmpeg встановлено: {found}"); return found
    except Exception as e:
        print(f"apt failed: {e}")
    print("ERROR: FFmpeg не встановлено"); return None

FFMPEG_PATH = ensure_ffmpeg()

# ── Flask ────────────────────────────────────────────────────
app = Flask('')

@app.route('/')
def home(): return "MIDNIGHT SYSTEM ONLINE"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    Thread(target=run, daemon=True).start()

# ── Константи ────────────────────────────────────────────────
GLOBAL_SETTINGS = {
    "monitoring":  True,
    "voice_guard": True,
    "voice_stats": True,
    "version":     "v4.2.0",
    "image_url":   "https://cdn.discordapp.com/avatars/1492662597357404211/a_4bf48afaac3798695e46c007ce568803.gif?size=1024",
    "start_time":  datetime.now(timezone.utc)
}

VOICE_ID          = 1458906259922354277
GAMING_LOG_ID     = 1493054931224105070
GAMING_MONITOR_ID = 1495833786741424178

SHORT_TITLES = {
    "Dota 2":"👑 Дота","Counter-Strike 2":"🔫 КС","CS2":"🔫 КС",
    "League of Legends":"⚔️ ЛоЛ","Valorant":"🎯 Вало","Minecraft":"⛏️ Майн",
    "GTA V":"🚗 ГТА","Grand Theft Auto V":"🚗 ГТА","Grand Theft Auto V Legacy":"🚗 ГТА",
    "Apex Legends":"🏆 Апекс","EA Sports FC 26":"⚽ Футбол","EA Sports FC 25":"⚽ Футбол",
    "FIFA 23":"⚽ Футбол","FIFA 24":"⚽ Футбол","RADMIR CRMP":"🚔 Радмір",
    "Fortnite":"🪂 Форт","Rocket League":"🚀 РЛ","World of Warcraft":"🧙 ВоВ",
    "Call of Duty":"🪖 КоД","Among Us":"🕵️ Амонг","Rust":"🪓 Раст",
    "PUBG":"🎯 ПАБГ","PUBG: BATTLEGROUNDS":"🎯 ПАБГ",
    "Majestic RP":"🏙️ Маєстік","ARC Raiders":"🤖 АРК",
    "Way of the Hunter":"🦌 Мисливець","Project Zomboid":"🧟 Зомбоїд",
    "World of Warships":"⚓ Кораблі","Arena Breakout: Infinite":"🪖 Арена",
    "Far Cry 6":"🌴 ФарКрай","Metro: Last Light Redux":"🚇 Метро",
}

DATA_DIR           = "/app/data"
STATS_FILE         = os.path.join(DATA_DIR, "voice_stats.json")
SESSIONS_FILE      = os.path.join(DATA_DIR, "active_sessions.json")
GAME_SESSIONS_FILE = os.path.join(DATA_DIR, "game_sessions.json")
MSG_FILE           = os.path.join(DATA_DIR, "message_ids.json")
os.makedirs(DATA_DIR, exist_ok=True)

# RAM стан
voice_start_times = {}   # {user_id: timestamp}
game_sessions     = {}   # {user_id: {"game": str, "start_time": float}}
active_games      = {}   # {game_name: {"players": [...], "start_time": float}}
live_message_id   = None
fame_message_id   = None
SAY_LIMIT         = 3
say_usage         = {}   # {user_id: [timestamp, ...]}

# ── Файлові операції ─────────────────────────────────────────
def load_stats():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE) as f:
                data = json.load(f)
            for k in ("total","daily","games","streaks"):
                data.setdefault(k, {})
            return data
        except Exception as e:
            print(f"ERROR load_stats: {e}")
    return {"total":{},"daily":{},"games":{},"streaks":{}}

def save_stats(data):
    try:
        with open(STATS_FILE,"w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"ERROR save_stats: {e}")

def load_voice_sessions():
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE) as f:
                raw = json.load(f)
            return {int(k): float(v) for k,v in raw.items()}
        except: pass
    return {}

def save_voice_sessions():
    try:
        with open(SESSIONS_FILE,"w") as f:
            json.dump({str(k):v for k,v in voice_start_times.items()}, f)
    except Exception as e:
        print(f"ERROR save_voice_sessions: {e}")

def load_game_sessions():
    if os.path.exists(GAME_SESSIONS_FILE):
        try:
            with open(GAME_SESSIONS_FILE) as f:
                raw = json.load(f)
            return {int(k): v for k,v in raw.items()}
        except: pass
    return {}

def save_game_sessions():
    try:
        with open(GAME_SESSIONS_FILE,"w") as f:
            json.dump({str(k):v for k,v in game_sessions.items()}, f)
    except Exception as e:
        print(f"ERROR save_game_sessions: {e}")

def load_message_ids():
    global live_message_id, fame_message_id
    if os.path.exists(MSG_FILE):
        try:
            with open(MSG_FILE) as f:
                d = json.load(f)
            live_message_id = d.get("live")
            fame_message_id = d.get("fame")
        except: pass

def save_message_ids():
    try:
        with open(MSG_FILE,"w") as f:
            json.dump({"live": live_message_id, "fame": fame_message_id}, f)
    except Exception as e:
        print(f"ERROR save_message_ids: {e}")

# ── Утиліти часу ─────────────────────────────────────────────
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

# ── Стрики ───────────────────────────────────────────────────
def update_streak(uid):
    s     = load_stats()
    today = date.today().isoformat()
    entry = s.setdefault("streaks",{}).get(uid, {"last_date":None,"count":0})
    if entry["last_date"] == today:
        return
    yest = (date.today()-timedelta(days=1)).isoformat()
    entry["count"] = entry["count"]+1 if entry["last_date"]==yest else 1
    entry["last_date"] = today
    s["streaks"][uid] = entry
    save_stats(s)

def get_streak(uid):
    entry = load_stats().get("streaks",{}).get(str(uid),{})
    today = date.today().isoformat()
    yest  = (date.today()-timedelta(days=1)).isoformat()
    return entry.get("count",0) if entry.get("last_date") in (today,yest) else 0

def streak_emoji(uid):
    s = get_streak(str(uid))
    return f" 🔥{s}" if s >= 3 else ""

# ── Запис статистики ─────────────────────────────────────────
def add_voice_time(member_id, duration, game=None):
    """Записує войс-час + опційно ігровий час. Один read/write."""
    if duration <= 0: return
    s   = load_stats()
    uid = str(member_id)
    s["total"][uid] = s["total"].get(uid,0) + duration
    s["daily"][uid] = s["daily"].get(uid,0) + duration
    if game:
        s.setdefault("games",{}).setdefault(uid,{})[game] = \
            s["games"][uid].get(game,0) + duration
    save_stats(s)
    update_streak(uid)
    print(f"VOICE +{format_time(duration)} uid={member_id} game={game}")

def add_game_time_only(member_id, duration, game):
    """Записує тільки ігровий час (без войс total/daily)."""
    if duration <= 0 or not game: return
    s   = load_stats()
    uid = str(member_id)
    s.setdefault("games",{}).setdefault(uid,{})[game] = \
        s["games"][uid].get(game,0) + duration
    save_stats(s)
    update_streak(uid)
    print(f"GAME  +{format_time(duration)} uid={member_id} game={game}")

def get_current_session(user_id):
    if user_id in voice_start_times:
        return datetime.now().timestamp() - voice_start_times[user_id]
    return 0.0

def get_total_time(user_id):
    return load_stats()["total"].get(str(user_id),0) + get_current_session(user_id)

def get_daily_time(user_id):
    return load_stats()["daily"].get(str(user_id),0) + get_current_session(user_id)

def get_display_name(uid, guild):
    try:
        m = guild.get_member(int(uid)) if guild else None
        if m: return m.display_name
        u = bot.get_user(int(uid))
        if u: return u.display_name
    except: pass
    return f"User {uid}"

def get_top_games(limit_games=3, limit_players=5):
    """Топ ігор по сумарному часу всіх гравців."""
    s = load_stats()
    gd = {}
    for uid, ug in s.get("games",{}).items():
        for game, sec in ug.items():
            if game not in gd:
                gd[game] = {"total":0,"players":[]}
            gd[game]["total"] += sec
            gd[game]["players"].append((uid, sec))
    sorted_g = sorted(gd.items(), key=lambda x: x[1]["total"], reverse=True)
    result = {}
    for game, data in sorted_g[:limit_games]:
        result[game] = {
            "players": sorted(data["players"], key=lambda x: x[1], reverse=True)[:limit_players],
            "total":   data["total"]
        }
    return result

def get_short_title(game):
    return SHORT_TITLES.get(game, f"🎮 {game[:14]}")

# ── Ініціалізація бота ───────────────────────────────────────
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents, chunk_guilds_at_startup=True)

# ── Войс-гард + TTS ─────────────────────────────────────────
async def join_voice_safe():
    if not GLOBAL_SETTINGS["voice_guard"]: return
    ch = bot.get_channel(VOICE_ID)
    if not ch: return
    vc = discord.utils.get(bot.voice_clients, guild=ch.guild)
    if not vc:
        try: await ch.connect(timeout=20.0, reconnect=True)
        except Exception as e: print(f"ERROR join_voice: {e}")
    elif vc.channel.id != VOICE_ID:
        await vc.move_to(ch)

async def play_tts(text, guild):
    try:
        from gtts import gTTS
        import tempfile
        ffmpeg = FFMPEG_PATH or shutil.which("ffmpeg")
        if not ffmpeg:
            print("ERROR play_tts: ffmpeg не знайдено"); return
        tts = gTTS(text=text, lang="uk")
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tts.save(tmp.name); tmp.close()
        vc = discord.utils.get(bot.voice_clients, guild=guild)
        if not vc:
            await join_voice_safe(); await asyncio.sleep(2)
            vc = discord.utils.get(bot.voice_clients, guild=guild)
        if not vc:
            os.remove(tmp.name); return
        while vc.is_playing(): await asyncio.sleep(0.5)
        vc.play(discord.FFmpegPCMAudio(tmp.name, executable=ffmpeg))
        while vc.is_playing(): await asyncio.sleep(0.5)
        os.remove(tmp.name)
        print(f"TTS done: {text[:40]}")
    except Exception as e:
        print(f"ERROR play_tts: {e}")

# ── /say ліміт ──────────────────────────────────────────────
def check_say_limit(user_id):
    if SAY_LIMIT == 0: return True, 0, 0
    now      = datetime.now().timestamp()
    hour_ago = now - 3600
    usage    = [t for t in say_usage.get(user_id,[]) if t > hour_ago]
    say_usage[user_id] = usage
    remaining = SAY_LIMIT - len(usage)
    if remaining <= 0:
        reset_in = int(usage[0] + 3600 - now)
        return False, 0, reset_in
    return True, remaining, 0

def record_say_usage(user_id):
    say_usage.setdefault(user_id,[]).append(datetime.now().timestamp())

# ── Slash команди ────────────────────────────────────────────
@bot.tree.command(name="stats", description="Твоя персональна картка статистики")
async def stats_cmd(interaction: discord.Interaction):
    if not GLOBAL_SETTINGS["voice_stats"]:
        return await interaction.response.send_message("❌ Статистика вимкнена", ephemeral=True)
    uid  = interaction.user.id
    suid = str(uid)
    s    = load_stats()
    total   = get_total_time(uid)
    daily   = get_daily_time(uid)
    current = get_current_session(uid)
    streak  = get_streak(suid)
    ug      = s.get("games",{}).get(suid,{})
    embed   = discord.Embed(title=f"📊 {interaction.user.display_name}{streak_emoji(suid)}", color=0x2b2d31)
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.add_field(name="📅 Сьогодні", value=f"`{format_time(daily)}`",   inline=True)
    embed.add_field(name="🏆 Весь час", value=f"`{format_time(total)}`",   inline=True)
    if current > 0:
        embed.add_field(name="🎙️ Зараз", value=f"`{format_time(current)}`", inline=True)
    if streak >= 3:
        embed.add_field(name="🔥 Стрик", value=f"`{streak} дні поспіль`",   inline=True)
    if ug:
        top = sorted(ug.items(), key=lambda x: x[1], reverse=True)[:5]
        embed.add_field(name="🎮 Час у іграх",
            value="\n".join(f"`{format_time(s)}` — {g}" for g,s in top), inline=False)
    embed.set_footer(text=midnight_footer())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="mystats", description="Твоя статистика")
async def mystats(interaction: discord.Interaction):
    await stats_cmd.callback(interaction)

@bot.tree.command(name="leaderboard", description="Топ активності сервера")
@app_commands.choices(період=[
    app_commands.Choice(name="Весь час",  value="total"),
    app_commands.Choice(name="Сьогодні", value="daily")
])
async def leaderboard(interaction: discord.Interaction, період: app_commands.Choice[str]):
    if not GLOBAL_SETTINGS["voice_stats"]:
        return await interaction.response.send_message("❌ Вимкнено", ephemeral=True)
    s    = load_stats()
    data = dict(s.get(період.value, {}))
    # Додаємо поточні активні сесії
    for uid, start in voice_start_times.items():
        k = str(uid)
        data[k] = data.get(k,0) + (datetime.now().timestamp() - start)
    top    = sorted(data.items(), key=lambda x: x[1], reverse=True)[:10]
    medals = ["🥇","🥈","🥉"]
    lines  = []
    for i, (uid, sec) in enumerate(top):
        name  = get_display_name(uid, interaction.guild)
        medal = medals[i] if i < 3 else f"**{i+1}.**"
        lines.append(f"{medal} {name}{streak_emoji(uid)} — `{format_time(sec)}`")
    embed = discord.Embed(
        title=f"🏆 Топ активності | {період.name}",
        description="\n".join(lines) or "Немає даних",
        color=0x2b2d31
    )
    embed.set_footer(text=midnight_footer())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ping", description="Затримка та аптайм")
async def ping_cmd(interaction: discord.Interaction):
    lat    = round(bot.latency * 1000)
    up     = datetime.now(timezone.utc) - GLOBAL_SETTINGS["start_time"]
    h, r   = divmod(int(up.total_seconds()), 3600)
    color  = 0x57F287 if lat < 100 else (0xFEE75C if lat < 200 else 0xED4245)
    embed  = discord.Embed(title="🏓 Pong!", color=color)
    embed.add_field(name="📡 Затримка", value=f"`{lat}ms`",            inline=True)
    embed.add_field(name="⏱️ Аптайм",  value=f"`{h}г {r//60}хв`",    inline=True)
    embed.add_field(name="🔢 Версія",  value=f"`{GLOBAL_SETTINGS['version']}`", inline=True)
    embed.set_footer(text=midnight_footer())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="help", description="Список команд")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="🌑 Midnight Bot | Допомога", color=0x2b2d31)
    embed.add_field(name="📊 Статистика", value="`/stats` `/leaderboard`", inline=False)
    embed.add_field(name="🎮 Геймінг",   value="`/games` `/kings`",        inline=False)
    embed.add_field(name="🎙️ Войс",      value="`/say` `/set_say_limit`",  inline=False)
    embed.add_field(name="⚙️ Система",
        value="`/ping` `/midnight_info` `/set_monitoring` `/set_voice` `/set_stats`",
        inline=False)
    embed.set_footer(text=midnight_footer())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="games", description="Хто грає зараз")
async def games_cmd(interaction: discord.Interaction):
    embed = build_live_embed()
    embed.set_footer(text=midnight_footer())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="kings", description="Зал Слави")
async def kings_cmd(interaction: discord.Interaction):
    embed = build_fame_embed(interaction.guild)
    embed.set_footer(text=midnight_footer())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="say", description="Озвучити текст у войсі")
@app_commands.describe(текст="Що сказати")
async def say_cmd(interaction: discord.Interaction, текст: str):
    if len(текст) > 200:
        return await interaction.response.send_message("❌ Максимум 200 символів", ephemeral=True)
    can, remaining, reset_in = check_say_limit(interaction.user.id)
    if not can:
        m, s = reset_in//60, reset_in%60
        return await interaction.response.send_message(
            f"⏳ Ліміт! Скинеться через **{m}хв {s}с**", ephemeral=True)
    record_say_usage(interaction.user.id)
    info = f" _(залишилось {remaining-1}/{SAY_LIMIT})_" if SAY_LIMIT > 0 else ""
    await interaction.response.send_message(f"🔊 Озвучую: **{текст}**{info}", ephemeral=True)
    asyncio.create_task(play_tts(текст, interaction.guild))

@bot.tree.command(name="set_say_limit", description="Ліміт /say на годину (0=без ліміту)")
@app_commands.describe(ліміт="Кількість на годину")
async def set_say_limit(interaction: discord.Interaction, ліміт: int):
    global SAY_LIMIT
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Тільки адміни", ephemeral=True)
    if ліміт < 0:
        return await interaction.response.send_message("❌ Від'ємне не можна", ephemeral=True)
    SAY_LIMIT = ліміт
    msg = "🔊 Ліміт вимкнено" if ліміт == 0 else f"🔊 Ліміт: **{ліміт}**/годину"
    await interaction.response.send_message(msg)

@bot.tree.command(name="midnight_info", description="Статус системи")
async def midnight_info(interaction: discord.Interaction):
    embed = discord.Embed(title="🌑 Midnight Bot | Status", color=0x2b2d31)
    for label, key in [("🎮 Моніторинг","monitoring"),("🎙️ Войс-гард","voice_guard"),("📊 Статистика","voice_stats")]:
        embed.add_field(name=label, value=f"`{'🟢 ON' if GLOBAL_SETTINGS[key] else '🔴 OFF'}`", inline=True)
    embed.add_field(name="👥 У войсі",   value=f"`{len(voice_start_times)}`", inline=True)
    embed.add_field(name="🎮 Ігор",      value=f"`{len(active_games)}`",      inline=True)
    embed.add_field(name="💾 Say ліміт", value=f"`{SAY_LIMIT}/год`",          inline=True)
    embed.set_thumbnail(url=GLOBAL_SETTINGS["image_url"])
    embed.set_footer(text=midnight_footer())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="set_monitoring")
@app_commands.choices(стан=[app_commands.Choice(name="Увімкнути",value="on"),app_commands.Choice(name="Вимкнути",value="off")])
async def set_monitoring(interaction: discord.Interaction, стан: app_commands.Choice[str]):
    GLOBAL_SETTINGS["monitoring"] = (стан.value=="on")
    await interaction.response.send_message(f"📡 Моніторинг: **{'Увімкнено' if GLOBAL_SETTINGS['monitoring'] else 'Вимкнено'}**")

@bot.tree.command(name="set_voice")
@app_commands.choices(стан=[app_commands.Choice(name="Увімкнути",value="on"),app_commands.Choice(name="Вимкнути",value="off")])
async def set_voice(interaction: discord.Interaction, стан: app_commands.Choice[str]):
    GLOBAL_SETTINGS["voice_guard"] = (стан.value=="on")
    if not GLOBAL_SETTINGS["voice_guard"]:
        for vc in bot.voice_clients: await vc.disconnect()
    await interaction.response.send_message(f"🎙️ Войс-гард: **{'Увімкнено' if GLOBAL_SETTINGS['voice_guard'] else 'Вимкнено'}**")

@bot.tree.command(name="set_stats")
@app_commands.choices(стан=[app_commands.Choice(name="Увімкнути",value="on"),app_commands.Choice(name="Вимкнути",value="off")])
async def set_stats(interaction: discord.Interaction, стан: app_commands.Choice[str]):
    GLOBAL_SETTINGS["voice_stats"] = (стан.value=="on")
    await interaction.response.send_message(f"📊 Статистика: **{'Увімкнено' if GLOBAL_SETTINGS['voice_stats'] else 'Вимкнено'}**")

# ── Події войсу ──────────────────────────────────────────────
@bot.event
async def on_voice_state_update(member, before, after):
    # Войс-гард
    if member.id == bot.user.id and before.channel and not after.channel:
        if GLOBAL_SETTINGS["voice_guard"]:
            await asyncio.sleep(5)
            await join_voice_safe()
        return

    if member.bot or not GLOBAL_SETTINGS["voice_stats"]: return
    now = datetime.now().timestamp()

    if not before.channel and after.channel:
        # Зайшов у войс
        voice_start_times[member.id] = now
        save_voice_sessions()
        print(f"JOIN: {member.name}")

    elif before.channel and not after.channel:
        # Вийшов з войсу
        if member.id in voice_start_times:
            duration = now - voice_start_times.pop(member.id)
            save_voice_sessions()
            game = game_sessions.get(member.id, {}).get("game")
            add_voice_time(member.id, duration, game)
            # Видаляємо ігрову сесію щоб не рахувати двічі в periodic_save
            if member.id in game_sessions:
                del game_sessions[member.id]
                save_game_sessions()
            print(f"LEAVE: {member.name} | {format_time(duration)}")
            # Оновлюємо Зал Слави
            asyncio.create_task(update_fame_message(member.guild))

    elif before.channel and after.channel and before.channel.id != after.channel.id:
        print(f"SWITCH: {member.name}")

# ── Моніторинг ігор ──────────────────────────────────────────
def get_game_name(member):
    if not member.activities: return None
    for act in member.activities:
        if isinstance(act, discord.CustomActivity) or act.name == "Spotify": continue
        if hasattr(act,'name') and act.name: return act.name
    return None

@bot.event
async def on_presence_update(before, after):
    if not GLOBAL_SETTINGS["monitoring"] or after.bot: return
    await asyncio.sleep(1)
    guild       = after.guild
    before_game = get_game_name(before)
    after_game  = get_game_name(after)
    if before_game == after_game: return

    changed = False

    if before_game:
        # Записуємо час гри що закінчилась
        if after.id in game_sessions and game_sessions[after.id]["game"] == before_game:
            dur = datetime.now().timestamp() - game_sessions[after.id]["start_time"]
            add_game_time_only(after.id, dur, before_game)
            del game_sessions[after.id]
            save_game_sessions()
        # Оновлюємо active_games
        if before_game in active_games:
            players = [m.display_name for m in guild.members
                       if get_game_name(m) == before_game and not m.bot]
            if not players: del active_games[before_game]
            else:           active_games[before_game]["players"] = players
            changed = True

    if after_game:
        game_sessions[after.id] = {"game": after_game, "start_time": datetime.now().timestamp()}
        save_game_sessions()
        players = [m.display_name for m in guild.members
                   if get_game_name(m) == after_game and not m.bot]
        if players:
            if after_game not in active_games:
                active_games[after_game] = {"players": players, "start_time": datetime.now().timestamp()}
            else:
                active_games[after_game]["players"] = players
            changed = True

    if changed:
        await update_fame_message(guild)
        await update_live_message(guild)

# ── Periodic save (кожні 2 хв) ───────────────────────────────
@tasks.loop(minutes=2)
async def periodic_save():
    """
    Кожні 2 хвилини зберігає:
    - войс-сесії → total + daily + games
    - ігрові сесії без войсу → тільки games
    Один load/save для всіх.
    """
    if not GLOBAL_SETTINGS["voice_stats"]: return
    now   = datetime.now().timestamp()
    s     = load_stats()
    sv, sg = 0, 0

    # Войс
    for uid, start in list(voice_start_times.items()):
        dur = now - start
        if dur < 30: continue
        k    = str(uid)
        game = game_sessions.get(uid, {}).get("game")
        s["total"][k] = s["total"].get(k,0) + dur
        s["daily"][k] = s["daily"].get(k,0) + dur
        if game:
            s.setdefault("games",{}).setdefault(k,{})[game] = \
                s["games"][k].get(game,0) + dur
        voice_start_times[uid] = now
        if uid in game_sessions:
            game_sessions[uid]["start_time"] = now
        sv += 1

    # Ігри без войсу
    for uid, sess in list(game_sessions.items()):
        if uid in voice_start_times: continue  # вже оброблено вище
        dur = now - sess["start_time"]
        if dur < 30: continue
        k    = str(uid)
        game = sess["game"]
        s.setdefault("games",{}).setdefault(k,{})[game] = \
            s["games"][k].get(game,0) + dur
        game_sessions[uid]["start_time"] = now
        sg += 1

    if sv > 0 or sg > 0:
        save_stats(s)
        save_game_sessions()
        print(f"PERIODIC: войс={sv} ігри={sg}")

# ── Щоденний звіт ────────────────────────────────────────────
@tasks.loop(time=time(hour=0, minute=0, tzinfo=timezone.utc))
async def daily_report():
    if not GLOBAL_SETTINGS["voice_stats"]: return
    # Зберігаємо поточні сесії перед скиданням
    now = datetime.now().timestamp()
    s   = load_stats()
    for uid, start in list(voice_start_times.items()):
        dur  = now - start
        k    = str(uid)
        game = game_sessions.get(uid,{}).get("game")
        s["total"][k] = s["total"].get(k,0) + dur
        s["daily"][k] = s["daily"].get(k,0) + dur
        if game:
            s.setdefault("games",{}).setdefault(k,{})[game] = \
                s["games"][k].get(game,0) + dur
        voice_start_times[uid] = now
        if uid in game_sessions:
            game_sessions[uid]["start_time"] = now
    save_stats(s)

    ch  = bot.get_channel(GAMING_LOG_ID)
    s2  = load_stats()
    top = sorted(s2["daily"].items(), key=lambda x: x[1], reverse=True)[:5]
    if not top or not ch:
        s2["daily"] = {}; save_stats(s2); return

    medals = ["🥇","🥈","🥉","4️⃣","5️⃣"]
    guild  = bot.guilds[0] if bot.guilds else None
    lines  = [f"{medals[i]} {get_display_name(uid,guild)}{streak_emoji(uid)} — {format_time(sec)}"
              for i,(uid,sec) in enumerate(top)]
    embed  = discord.Embed(title="📊 Підсумки дня", description="\n".join(lines),
                           color=0x9b59b6, timestamp=datetime.now(timezone.utc))
    embed.set_footer(text=midnight_footer())
    await ch.send(embed=embed)
    s2["daily"] = {}; save_stats(s2)
    print("DAILY RESET done")

# ── Embeds ───────────────────────────────────────────────────
def build_live_embed():
    embed = discord.Embed(title="🎮 Активні катки", color=0x57F287,
                          timestamp=datetime.now(timezone.utc))
    if not active_games:
        embed.description = "*Зараз ніхто не грає*"
        return embed
    lines = []
    for name, data in active_games.items():
        dur   = int(datetime.now().timestamp() - data["start_time"])
        names = ", ".join(data["players"]) if data["players"] else "?"
        lines.append(f"**{name}**\n👥 {names}\n⏱️ {format_time(dur)}\n")
    embed.description = "\n".join(lines)
    embed.set_footer(text="🔴 Live • Оновлюється автоматично")
    return embed

def build_fame_embed(guild):
    embed   = discord.Embed(title="🏛️ Зал Слави", color=0xf1c40f,
                            timestamp=datetime.now(timezone.utc))
    s       = load_stats()
    medals  = ["🥇","🥈","🥉","4️⃣","5️⃣"]

    # Топ войсу — з урахуванням поточних сесій
    total = dict(s.get("total",{}))
    for uid, start in voice_start_times.items():
        k = str(uid)
        total[k] = total.get(k,0) + (datetime.now().timestamp() - start)
    top3 = sorted(total.items(), key=lambda x: x[1], reverse=True)[:3]
    lines = [f"{medals[i]} **{get_display_name(uid,guild)}**{streak_emoji(uid)} — `{format_time(sec)}`"
             for i,(uid,sec) in enumerate(top3)]
    embed.add_field(name="🎙️ Топ войсу",
                    value="\n".join(lines) if lines else "*Немає даних*",
                    inline=False)

    # Топ-3 ігри
    top_games = get_top_games(3, 5)
    if top_games:
        for game, data in top_games.items():
            title  = get_short_title(game)
            plines = [f"{medals[i] if i<len(medals) else '•'} {get_display_name(uid,guild)} — `{format_time(sec)}`"
                      for i,(uid,sec) in enumerate(data["players"])]
            embed.add_field(
                name=f"{title}  ·  {format_time(data['total'])} загалом",
                value="\n".join(plines),
                inline=False
            )
    else:
        embed.add_field(name="🎮 Ігри", value="*Ще немає даних*", inline=False)

    embed.set_footer(text="⭐ Зал Слави • Оновлюється автоматично")
    return embed

async def update_live_message(guild):
    global live_message_id
    ch = bot.get_channel(GAMING_MONITOR_ID)
    if not ch: return
    embed = build_live_embed()
    embed.set_footer(text=midnight_footer())
    if live_message_id:
        try:
            await (await ch.fetch_message(live_message_id)).edit(embed=embed)
            return
        except discord.NotFound:
            live_message_id = None
    try:
        async for msg in ch.history(limit=30):
            if msg.author.id == bot.user.id and msg.embeds and "Активні" in (msg.embeds[0].title or ""):
                live_message_id = msg.id
                await msg.edit(embed=embed)
                save_message_ids(); return
    except: pass
    msg = await ch.send(embed=embed)
    live_message_id = msg.id
    save_message_ids()

async def update_fame_message(guild):
    global fame_message_id
    ch = bot.get_channel(GAMING_MONITOR_ID)
    if not ch: return
    embed = build_fame_embed(guild)
    embed.set_footer(text=midnight_footer())
    if fame_message_id:
        try:
            await (await ch.fetch_message(fame_message_id)).edit(embed=embed)
            return
        except discord.NotFound:
            fame_message_id = None
    try:
        async for msg in ch.history(limit=30):
            if msg.author.id == bot.user.id and msg.embeds and "Слави" in (msg.embeds[0].title or ""):
                fame_message_id = msg.id
                await msg.edit(embed=embed)
                save_message_ids(); return
    except: pass
    msg = await ch.send(embed=embed)
    fame_message_id = msg.id
    save_message_ids()

# ── on_ready ─────────────────────────────────────────────────
@bot.event
async def on_ready():
    global voice_start_times, active_games
    print(f'--- Midnight {GLOBAL_SETTINGS["version"]} ONLINE ---')
    print(f'--- FFmpeg: {FFMPEG_PATH} ---')
    await bot.tree.sync()
    load_message_ids()

    # Відновлюємо ігрові сесії
    saved_gs = load_game_sessions()
    # Відновлюємо войс сесії
    saved_vs = load_voice_sessions()

    active_games.clear()
    game_sessions.clear()

    for guild in bot.guilds:
        for member in guild.members:
            if member.bot: continue
            game = get_game_name(member)
            if game and GLOBAL_SETTINGS["monitoring"]:
                # Відновлюємо збережену сесію якщо та сама гра
                if member.id in saved_gs and saved_gs[member.id].get("game") == game:
                    game_sessions[member.id] = saved_gs[member.id]
                    print(f"RESTORED GAME: {member.name} — {game}")
                else:
                    game_sessions[member.id] = {"game": game, "start_time": datetime.now().timestamp()}
                if game not in active_games:
                    active_games[game] = {"players": [member.display_name], "start_time": datetime.now().timestamp()}
                elif member.display_name not in active_games[game]["players"]:
                    active_games[game]["players"].append(member.display_name)

        # Войс сесії
        for channel in guild.voice_channels:
            for member in channel.members:
                if member.bot: continue
                voice_start_times[member.id] = saved_vs.get(member.id, datetime.now().timestamp())
                print(f"VOICE SESSION: {member.name}")

        bot.loop.create_task(update_fame_message(guild))
        bot.loop.create_task(update_live_message(guild))

    save_voice_sessions()
    save_game_sessions()

    if not daily_report.is_running():  daily_report.start()
    if not periodic_save.is_running(): periodic_save.start()

    await asyncio.sleep(2)
    await join_voice_safe()
    print(f"READY: {len(voice_start_times)} войс | {len(active_games)} ігор | {len(game_sessions)} ігрових сесій")

if __name__ == "__main__":
    keep_alive()
    token = os.environ.get("DISCORD_TOKEN")
    if not token: raise ValueError("DISCORD_TOKEN не знайдено!")
    bot.run(token)
