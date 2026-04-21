import discord
from discord.ext import commands, tasks
from discord import app_commands
from flask import Flask
from threading import Thread
import os
import asyncio
import json
from datetime import datetime, date, time, timezone, timedelta

# ============================================================
# 1. ВЕБ-СЕРВЕР ДЛЯ RAILWAY
# ============================================================
app = Flask('')

@app.route('/')
def home():
    return "MIDNIGHT SYSTEM ONLINE"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run, daemon=True)
    t.start()

# ============================================================
# 2. КОНСТАНТИ ТА НАЛАШТУВАННЯ
# ============================================================
GLOBAL_SETTINGS = {
    "monitoring": True,
    "voice_guard": True,
    "voice_stats": True,
    "version": "v4.1.0", # Оновив версію
    "image_url": "https://cdn.discordapp.com/avatars/1492662597357404211/a_4bf48afaac3798695e46c007ce568803.gif?size=1024",
    "start_time": datetime.now(timezone.utc)
}

# Канали
VOICE_ID          = 1458906259922354277
GAMING_LOG_ID     = 1493054931224105070
GAMING_MONITOR_ID = 1495833786741424178

# Титули для ігор
TITLES = {
    "Dota 2":                    "👑 Король Доти",
    "Counter-Strike 2":          "🔫 Задрот КС",
    "CS2":                       "🔫 Задрот КС",
    "League of Legends":         "⚔️ Повелитель Рифту",
    "Valorant":                  "🎯 Снайпер Валоранту",
    "Minecraft":                 "⛏️ Майстер Блоків",
    "GTA V":                     "🚗 Вуличний Гонщик",
    "Grand Theft Auto V":        "🚗 Вуличний Гонщик",
    "Grand Theft Auto V Legacy": "🚗 Вуличний Гонщик",
    "Apex Legends":              "🏆 Легенда Апекса",
    "EA Sports FC 26":           "⚽ Футбольний Бог",
    "EA Sports FC 25":           "⚽ Футбольний Бог",
    "FIFA 23":                   "⚽ Футбольний Бог",
    "FIFA 24":                   "⚽ Футбольний Бог",
    "RADMIR CRMP":               "🚔 Вуличний Авторитет",
    "World of Warcraft":         "🧙 Майстер Азерота",
    "Fortnite":                  "🪂 Чемпіон Острова",
    "Call of Duty":              "🪖 Бойова Машина",
    "Rocket League":             "🚀 Повітряний Ас",
    "Among Us":                  "🕵️ Майстер Брехні",
}
DEFAULT_TITLE = "🎮 Майстер {game}"

# Файли даних
DATA_DIR      = "/app/data"
STATS_FILE    = os.path.join(DATA_DIR, "voice_stats.json")
SESSIONS_FILE = os.path.join(DATA_DIR, "active_sessions.json")
MSG_FILE      = os.path.join(DATA_DIR, "message_ids.json")

os.makedirs(DATA_DIR, exist_ok=True)

# RAM-стан
voice_start_times = {}  # {user_id: timestamp}
active_games      = {}  # {game_name: {"players": [...], "start_time": ts}}
game_sessions     = {}  # {user_id: {"game": name, "start_time": ts}}

# ID повідомлень що редагуються
live_message_id = None  # Повідомлення №1 — хто грає зараз
fame_message_id = None  # Повідомлення №2 — Зал Слави

# ============================================================
# 3. РОБОТА З ДАНИМИ
# ============================================================

def load_stats() -> dict:
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r") as f:
                data = json.load(f)
            for key in ("total", "daily", "games", "streaks"):
                if key not in data:
                    data[key] = {}
            return data
        except Exception as e:
            print(f"ERROR load_stats: {e}")
    return {"total": {}, "daily": {}, "games": {}, "streaks": {}}

def save_stats(data: dict):
    try:
        with open(STATS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"ERROR save_stats: {e}")

def load_sessions() -> dict:
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE, "r") as f:
                raw = json.load(f)
            return {int(k): float(v) for k, v in raw.items()}
        except:
            pass
    return {}

def save_sessions():
    try:
        with open(SESSIONS_FILE, "w") as f:
            json.dump({str(k): v for k, v in voice_start_times.items()}, f)
    except Exception as e:
        print(f"ERROR save_sessions: {e}")

def load_message_ids():
    global live_message_id, fame_message_id
    if os.path.exists(MSG_FILE):
        try:
            with open(MSG_FILE, "r") as f:
                d = json.load(f)
            live_message_id = d.get("live")
            fame_message_id = d.get("fame")
        except:
            pass

def save_message_ids():
    try:
        with open(MSG_FILE, "w") as f:
            json.dump({"live": live_message_id, "fame": fame_message_id}, f)
    except Exception as e:
        print(f"ERROR save_message_ids: {e}")

# ============================================================
# 4. ЛОГІКА СТАТИСТИКИ
# ============================================================

def format_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    total_minutes = seconds // 60
    if total_minutes == 0:
        return "< 1хв"
    h = total_minutes // 60
    m = total_minutes % 60
    if h == 0:
        return f"{m}хв"
    if m == 0:
        return f"{h}г"
    return f"{h}г {m}хв"

def update_streak(uid: str):
    s = load_stats()
    today = date.today().isoformat()
    streaks = s.setdefault("streaks", {})
    entry = streaks.get(uid, {"last_date": None, "count": 0})

    if entry["last_date"] == today:
        save_stats(s)
        return

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    if entry["last_date"] == yesterday:
        entry["count"] += 1
    else:
        entry["count"] = 1

    entry["last_date"] = today
    streaks[uid] = entry
    s["streaks"] = streaks
    save_stats(s)

def get_streak(uid: str) -> int:
    s = load_stats()
    entry = s.get("streaks", {}).get(uid, {})
    today     = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    if entry.get("last_date") in (today, yesterday):
        return entry.get("count", 0)
    return 0

def streak_emoji(uid: str) -> str:
    streak = get_streak(str(uid))
    return f" 🔥{streak}" if streak >= 3 else ""

def add_voice_time(member_id: int, duration: float, game: str = None):
    if duration <= 0:
        return
    s   = load_stats()
    uid = str(member_id)

    s["total"][uid] = s["total"].get(uid, 0) + duration
    s["daily"][uid] = s["daily"].get(uid, 0) + duration

    if game:
        user_games = s.setdefault("games", {}).setdefault(uid, {})
        user_games[game] = user_games.get(game, 0) + duration

    save_stats(s)
    update_streak(uid)
    print(f"STATS +{format_time(duration)} uid={member_id} game={game}")

def add_game_only_time(member_id: int, duration: float, game: str):
    """Записує тільки ігровий час у базу, навіть якщо юзер не у войсі."""
    if duration <= 0 or not game:
        return
    s = load_stats()
    uid = str(member_id)
    
    user_games = s.setdefault("games", {}).setdefault(uid, {})
    user_games[game] = user_games.get(game, 0) + duration
    
    save_stats(s)
    update_streak(uid)
    print(f"GAME STATS: +{format_time(duration)} uid={member_id} game={game}")

def get_current_session(user_id: int) -> float:
    if user_id in voice_start_times:
        return datetime.now().timestamp() - voice_start_times[user_id]
    return 0.0

def get_total_time(user_id: int) -> float:
    s = load_stats()
    return s["total"].get(str(user_id), 0) + get_current_session(user_id)

def get_daily_time(user_id: int) -> float:
    s = load_stats()
    return s["daily"].get(str(user_id), 0) + get_current_session(user_id)

def get_game_kings() -> dict:
    """Повертає {game_name: (uid, seconds)} — лідер кожної гри для команди /stats."""
    s = load_stats()
    kings = {}
    for uid, games in s.get("games", {}).items():
        for game, sec in games.items():
            if game not in kings or sec > kings[game][1]:
                kings[game] = (uid, sec)
    return kings

def get_fame_stats(limit_games=6, limit_players=3) -> dict:
    """Повертає найпопулярніші ігри та Топ-X гравців у кожній для Залу Слави."""
    s = load_stats()
    games_data = {}
    
    for uid, user_games in s.get("games", {}).items():
        for game, sec in user_games.items():
            if game not in games_data:
                games_data[game] = {"total_time": 0, "players": []}
            games_data[game]["total_time"] += sec
            games_data[game]["players"].append((uid, sec))

    sorted_games = sorted(games_data.items(), key=lambda x: x[1]["total_time"], reverse=True)
    
    result = {}
    for game, data in sorted_games[:limit_games]:
        top_players = sorted(data["players"], key=lambda x: x[1], reverse=True)[:limit_players]
        result[game] = top_players

    return result

def get_title(game: str) -> str:
    return TITLES.get(game, DEFAULT_TITLE.format(game=game))

def midnight_footer() -> str:
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")
    return f"🌑 Midnight System • {now}"

# ============================================================
# 5. ІНІЦІАЛІЗАЦІЯ БОТА
# ============================================================
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents, chunk_guilds_at_startup=True)

# ============================================================
# 6. ВОЙС-ГАРД
# ============================================================
async def join_voice_safe():
    if not GLOBAL_SETTINGS["voice_guard"]:
        return
    channel = bot.get_channel(VOICE_ID)
    if not channel:
        return
    vc = discord.utils.get(bot.voice_clients, guild=channel.guild)
    if not vc:
        try:
            await channel.connect(timeout=20.0, reconnect=True)
        except Exception as e:
            print(f"ERROR join_voice: {e}")
    elif vc.channel.id != VOICE_ID:
        await vc.move_to(channel)

async def play_tts(text: str, guild: discord.Guild):
    try:
        from gtts import gTTS
        import tempfile

        tts = gTTS(text=text, lang="uk")
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tts.save(tmp.name)
        tmp.close()

        vc = discord.utils.get(bot.voice_clients, guild=guild)
        if not vc:
            await join_voice_safe()
            await asyncio.sleep(2)
            vc = discord.utils.get(bot.voice_clients, guild=guild)

        if not vc:
            print("ERROR play_tts: бот не в войсі")
            return

        while vc.is_playing():
            await asyncio.sleep(0.5)

        ffmpeg_opts = {
            'executable': '/usr/bin/ffmpeg'
        }
        vc.play(discord.FFmpegPCMAudio(tmp.name, executable='/usr/bin/ffmpeg'))

        while vc.is_playing():
            await asyncio.sleep(0.5)

        os.remove(tmp.name)
        print(f"TTS played: {text[:50]}")

    except Exception as e:
        print(f"ERROR play_tts: {e}")

# ============================================================
# 7. SLASH-КОМАНДИ
# ============================================================

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
    user_games = s.get("games", {}).get(suid, {})

    embed = discord.Embed(
        title=f"📊 {interaction.user.display_name}{streak_emoji(suid)}",
        color=0x2b2d31
    )
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.add_field(name="📅 Сьогодні",  value=f"`{format_time(daily)}`",   inline=True)
    embed.add_field(name="🏆 Весь час",  value=f"`{format_time(total)}`",   inline=True)
    if current > 0:
        embed.add_field(name="🎙️ Зараз", value=f"`{format_time(current)}`", inline=True)
    if streak >= 3:
        embed.add_field(name="🔥 Стрик", value=f"`{streak} дні поспіль`",   inline=True)

    if user_games:
        sorted_games = sorted(user_games.items(), key=lambda x: x[1], reverse=True)[:5]
        games_text   = "\n".join(f"`{format_time(sec)}` — {game}" for game, sec in sorted_games)
        embed.add_field(name="🎮 Час у іграх", value=games_text, inline=False)

    kings = get_game_kings()
    titles_earned = [get_title(g) for g, (k_uid, _) in kings.items() if k_uid == suid]
    if titles_earned:
        embed.add_field(name="🎖️ Титули", value="\n".join(titles_earned), inline=False)

    embed.set_footer(text=midnight_footer())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="mystats", description="Твоя особиста статистика")
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

    s     = load_stats()
    saved = dict(s.get(період.value, {}))

    for user_id, start_time in voice_start_times.items():
        uid = str(user_id)
        saved[uid] = saved.get(uid, 0) + (datetime.now().timestamp() - start_time)

    sorted_s = sorted(saved.items(), key=lambda x: x[1], reverse=True)[:10]
    medals   = ["🥇", "🥈", "🥉"]
    res = ""
    for i, (u_id, sec) in enumerate(sorted_s):
        name = get_display_name(u_id, interaction.guild)
        medal = medals[i] if i < 3 else f"**{i+1}.**"
        res  += f"{medal} {name}{streak_emoji(u_id)} — `{format_time(sec)}`\n"

    embed = discord.Embed(
        title=f"🏆 Топ активності | {період.name}",
        description=res or "Ще немає даних",
        color=0x2b2d31
    )
    embed.set_footer(text=midnight_footer())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ping", description="Затримка API та час роботи бота")
async def ping_cmd(interaction: discord.Interaction):
    latency  = round(bot.latency * 1000)
    uptime   = datetime.now(timezone.utc) - GLOBAL_SETTINGS["start_time"]
    hours, r = divmod(int(uptime.total_seconds()), 3600)
    mins     = r // 60
    color    = 0x57F287 if latency < 100 else (0xFEE75C if latency < 200 else 0xED4245)

    embed = discord.Embed(title="🏓 Pong!", color=color)
    embed.add_field(name="📡 Затримка", value=f"`{latency}ms`",        inline=True)
    embed.add_field(name="⏱️ Аптайм",  value=f"`{hours}г {mins}хв`", inline=True)
    embed.add_field(name="🔢 Версія",  value=f"`{GLOBAL_SETTINGS['version']}`", inline=True)
    embed.set_footer(text=midnight_footer())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="help", description="Список усіх команд бота")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="🌑 Midnight Bot | Допомога", color=0x2b2d31)
    embed.add_field(
        name="📊 Статистика",
        value="`/stats` — Персональна картка\n`/leaderboard` — Топ сервера",
        inline=False
    )
    embed.add_field(
        name="🎮 Геймінг",
        value="`/games` — Активні катки\n`/kings` — Королі ігор",
        inline=False
    )
    embed.add_field(
        name="🎙️ Войс",
        value="`/say` — Озвучити текст у голосовому каналі",
        inline=False
    )
    embed.add_field(
        name="⚙️ Система",
        value=(
            "`/ping` — Затримка та аптайм\n"
            "`/midnight_info` — Статус модулів\n"
            "`/set_monitoring` — Моніторинг ігор\n"
            "`/set_voice` — Voice Guardian\n"
            "`/set_stats` — Статистика войсу"
        ),
        inline=False
    )
    embed.set_footer(text=midnight_footer())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="games", description="Хто грає прямо зараз")
async def games_cmd(interaction: discord.Interaction):
    embed = build_live_embed()
    embed.set_footer(text=midnight_footer())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="kings", description="Королі ігор сервера")
async def kings_cmd(interaction: discord.Interaction):
    embed = build_fame_embed(interaction.guild)
    embed.set_footer(text=midnight_footer())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="say", description="Озвучити текст у голосовому каналі")
@app_commands.describe(текст="Що сказати у войсі")
async def say_cmd(interaction: discord.Interaction, текст: str):
    if len(текст) > 200:
        return await interaction.response.send_message("❌ Максимум 200 символів", ephemeral=True)

    await interaction.response.send_message(
        f"🔊 Озвучую: **{текст}**",
        ephemeral=True
    )
    asyncio.create_task(play_tts(текст, interaction.guild))

@bot.tree.command(name="midnight_info", description="Статус системи")
async def midnight_info(interaction: discord.Interaction):
    embed = discord.Embed(title="🌑 Midnight Bot | Status", color=0x2b2d31)
    for label, key in [("🎮 Game Monitor", "monitoring"), ("🎙️ Voice Guardian", "voice_guard"), ("📊 Voice Analytics", "voice_stats")]:
        status = "🟢 ON" if GLOBAL_SETTINGS[key] else "🔴 OFF"
        embed.add_field(name=label, value=f"`{status}`", inline=True)
    embed.add_field(name="👥 У войсі",       value=f"`{len(voice_start_times)}`", inline=True)
    embed.add_field(name="🎮 Активних ігор", value=f"`{len(active_games)}`",      inline=True)
    embed.set_thumbnail(url=GLOBAL_SETTINGS["image_url"])
    embed.set_footer(text=midnight_footer())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="set_monitoring")
@app_commands.choices(стан=[app_commands.Choice(name="Увімкнути", value="on"), app_commands.Choice(name="Вимкнути", value="off")])
async def set_monitoring(interaction: discord.Interaction, стан: app_commands.Choice[str]):
    GLOBAL_SETTINGS["monitoring"] = (стан.value == "on")
    await interaction.response.send_message(f"📡 Моніторинг ігор: **{'Увімкнено' if GLOBAL_SETTINGS['monitoring'] else 'Вимкнено'}**")

@bot.tree.command(name="set_voice")
@app_commands.choices(стан=[app_commands.Choice(name="Увімкнути", value="on"), app_commands.Choice(name="Вимкнути", value="off")])
async def set_voice(interaction: discord.Interaction, стан: app_commands.Choice[str]):
    GLOBAL_SETTINGS["voice_guard"] = (стан.value == "on")
    if not GLOBAL_SETTINGS["voice_guard"]:
        for vc in bot.voice_clients:
            await vc.disconnect()
    await interaction.response.send_message(f"🎙️ Voice Guardian: **{'Увімкнено' if GLOBAL_SETTINGS['voice_guard'] else 'Вимкнено'}**")

@bot.tree.command(name="set_stats")
@app_commands.choices(стан=[app_commands.Choice(name="Увімкнути", value="on"), app_commands.Choice(name="Вимкнути", value="off")])
async def set_stats(interaction: discord.Interaction, стан: app_commands.Choice[str]):
    GLOBAL_SETTINGS["voice_stats"] = (стан.value == "on")
    await interaction.response.send_message(f"📊 Статистика: **{'Увімкнено' if GLOBAL_SETTINGS['voice_stats'] else 'Вимкнено'}**")

# ============================================================
# 8. ПОДІЇ ВОЙСУ
# ============================================================

@bot.event
async def on_voice_state_update(member, before, after):
    print(f"VOICE: {member.name} | {before.channel} -> {after.channel}")

    if member.id == bot.user.id and before.channel and not after.channel:
        if GLOBAL_SETTINGS["voice_guard"]:
            await asyncio.sleep(5)
            await join_voice_safe()
        return

    if member.bot:
        return
    if not GLOBAL_SETTINGS["voice_stats"]:
        return

    now = datetime.now().timestamp()

    if not before.channel and after.channel:
        voice_start_times[member.id] = now
        save_sessions()
        print(f"START: {member.name}")

    elif before.channel and not after.channel:
        if member.id in voice_start_times:
            duration = now - voice_start_times.pop(member.id)
            save_sessions()
            game = game_sessions.get(member.id, {}).get("game")
            add_voice_time(member.id, duration, game)
            
            # Якщо грав — видаляємо ігрову сесію
            if member.id in game_sessions:
                del game_sessions[member.id]
            print(f"END: {member.name} | {format_time(duration)}")
            
            for guild in bot.guilds:
                if member.guild == guild:
                    asyncio.create_task(update_fame_message(guild))
                    break

    elif before.channel and after.channel and before.channel.id != after.channel.id:
        print(f"SWITCH: {member.name}")

# ============================================================
# 9. ЩОДЕННИЙ ЗВІТ
# ============================================================

@tasks.loop(time=time(hour=0, minute=0, tzinfo=timezone.utc))
async def daily_report():
    if not GLOBAL_SETTINGS["voice_stats"]:
        return

    now = datetime.now().timestamp()
    for user_id, start_time in list(voice_start_times.items()):
        duration = now - start_time
        if duration > 0:
            game = game_sessions.get(user_id, {}).get("game")
            add_voice_time(user_id, duration, game)
            voice_start_times[user_id] = now

    ch = bot.get_channel(GAMING_LOG_ID)
    s  = load_stats()

    if not s["daily"] or not ch:
        s["daily"] = {}
        save_stats(s)
        return

    top    = sorted(s["daily"].items(), key=lambda x: x[1], reverse=True)[:5]
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    lines  = []
    for i, (uid, sec) in enumerate(top):
        guild = bot.guilds[0] if bot.guilds else None
        name  = get_display_name(uid, guild)
        lines.append(f"{medals[i]} {name}{streak_emoji(uid)} — {format_time(sec)}")

    embed = discord.Embed(
        title="📊 Підсумки дня",
        description="\n".join(lines),
        color=0x9b59b6,
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_footer(text=midnight_footer())
    await ch.send(embed=embed)

    s["daily"] = {}
    save_stats(s)
    print("DAILY RESET done")

# ============================================================
# 10. МОНІТОРИНГ ІГОР
# ============================================================

def get_game_name(member) -> str | None:
    if not member.activities:
        return None
    for act in member.activities:
        if isinstance(act, discord.CustomActivity) or act.name == "Spotify":
            continue
        if hasattr(act, 'name') and act.name:
            return act.name
    return None

def build_live_embed() -> discord.Embed:
    """Повідомлення №1 — хто грає зараз (від 1 людини)"""
    embed = discord.Embed(
        title="🎮 Активні катки",
        color=0x57F287,
        timestamp=datetime.now(timezone.utc)
    )
    if not active_games:
        embed.description = "*Зараз ніхто не грає*"
        return embed

    lines = []
    for game_name, data in active_games.items():
        duration = int(datetime.now().timestamp() - data["start_time"])
        time_str = format_time(duration)
        names    = ", ".join(data["players"]) if data["players"] else "?"
        lines.append(f"**{game_name}**\n👥 {names}\n⏱️ {time_str}\n")

    embed.description = "\n".join(lines)
    embed.set_footer(text="🔴 Live • Оновлюється автоматично")
    return embed

def get_display_name(uid: str, guild) -> str:
    try:
        member = guild.get_member(int(uid)) if guild else None
        if member:
            return member.display_name
        user = bot.get_user(int(uid))
        if user:
            return user.display_name
    except:
        pass
    return f"User {uid}"

def build_fame_embed(guild) -> discord.Embed:
    """Повідомлення №2 — Зал Слави (Топ-6 ігор та Топ-3 сервера)"""
    embed = discord.Embed(
        title="🏛️ Зал Слави",
        color=0xf1c40f,
        timestamp=datetime.now(timezone.utc)
    )

    s = load_stats()

    # Топ-3 сервера
    total_stats = s.get("total", {})
    top3   = sorted(total_stats.items(), key=lambda x: x[1], reverse=True)[:3]
    medals = ["🥇", "🥈", "🥉"]
    top_lines = []
    for i, (uid, sec) in enumerate(top3):
        name = get_display_name(uid, guild)
        top_lines.append(f"{medals[i]} **{name}**{streak_emoji(uid)} — `{format_time(sec)}`")

    embed.add_field(
        name="👑 Абсолютні лідери сервера",
        value="\n".join(top_lines) if top_lines else "*Немає даних*",
        inline=False
    )

    # Найпопулярніші ігри сервера
    fame_data = get_fame_stats(limit_games=6, limit_players=3)
    if fame_data:
        for game, players in fame_data.items():
            king_lines = []
            for i, (uid, sec) in enumerate(players):
                name = get_display_name(uid, guild)
                medal = medals[i] if i < len(medals) else "•"
                king_lines.append(f"{medal} {name} — `{format_time(sec)}`")
            
            title = get_title(game)
            embed.add_field(name=f"🎖️ {title}", value="\n".join(king_lines), inline=True)
    else:
        embed.add_field(name="🎖️ Королі ігор", value="*Ще немає даних*", inline=False)

    embed.set_footer(text="⭐ Зал Слави • Оновлюється автоматично")
    return embed

async def update_live_message(guild):
    global live_message_id
    ch = bot.get_channel(GAMING_MONITOR_ID)
    if not ch:
        return
    embed = build_live_embed()
    embed.set_footer(text=midnight_footer())

    if live_message_id:
        try:
            msg = await ch.fetch_message(live_message_id)
            await msg.edit(embed=embed)
            return
        except discord.NotFound:
            live_message_id = None

    try:
        async for msg in ch.history(limit=30):
            if msg.author.id == bot.user.id and msg.embeds and "Активні" in (msg.embeds[0].title or ""):
                live_message_id = msg.id
                await msg.edit(embed=embed)
                save_message_ids()
                return
    except:
        pass

    msg = await ch.send(embed=embed)
    live_message_id = msg.id
    save_message_ids()

async def update_fame_message(guild):
    global fame_message_id
    ch = bot.get_channel(GAMING_MONITOR_ID)
    if not ch:
        return
    embed = build_fame_embed(guild)
    embed.set_footer(text=midnight_footer())

    if fame_message_id:
        try:
            msg = await ch.fetch_message(fame_message_id)
            await msg.edit(embed=embed)
            return
        except discord.NotFound:
            fame_message_id = None

    try:
        async for msg in ch.history(limit=30):
            if msg.author.id == bot.user.id and msg.embeds and "Слави" in (msg.embeds[0].title or ""):
                fame_message_id = msg.id
                await msg.edit(embed=embed)
                save_message_ids()
                return
    except:
        pass

    msg = await ch.send(embed=embed)
    fame_message_id = msg.id
    save_message_ids()

@bot.event
async def on_presence_update(before, after):
    if not GLOBAL_SETTINGS["monitoring"] or after.bot:
        return

    await asyncio.sleep(1)
    guild = after.guild

    before_game = get_game_name(before)
    after_game  = get_game_name(after)

    if before_game == after_game:
        return

    changed = False

    # Вийшов з гри
    if before_game:
        if after.id in game_sessions and game_sessions[after.id]["game"] == before_game:
            duration = datetime.now().timestamp() - game_sessions[after.id]["start_time"]
            add_game_only_time(after.id, duration, before_game)
            del game_sessions[after.id]

        if before_game in active_games:
            players = [m.display_name for m in guild.members if get_game_name(m) == before_game and not m.bot]
            if len(players) < 1:
                del active_games[before_game]
            else:
                active_games[before_game]["players"] = players
            changed = True

    # Зайшов у гру
    if after_game:
        game_sessions[after.id] = {"game": after_game, "start_time": datetime.now().timestamp()}
        players = [m.display_name for m in guild.members if get_game_name(m) == after_game and not m.bot]
        if len(players) >= 1:
            if after_game not in active_games:
                active_games[after_game] = {"players": players, "start_time": datetime.now().timestamp()}
            else:
                active_games[after_game]["players"] = players
            changed = True

    if changed:
        await update_fame_message(guild)
        await update_live_message(guild)

# ============================================================
# 11. СТАРТ
# ============================================================

@bot.event
async def on_ready():
    global voice_start_times, active_games
    print(f'--- Midnight {GLOBAL_SETTINGS["version"]} ONLINE ---')

    await bot.tree.sync()
    load_message_ids()

    active_games.clear()
    game_sessions.clear()
    for guild in bot.guilds:
        if not GLOBAL_SETTINGS["monitoring"]:
            continue
        for member in guild.members:
            if member.bot:
                continue
            game = get_game_name(member)
            if game:
                game_sessions[member.id] = {
                    "game": game,
                    "start_time": datetime.now().timestamp()
                }
                if game not in active_games:
                    active_games[game] = {"players": [member.display_name], "start_time": datetime.now().timestamp()}
                elif member.display_name not in active_games[game]["players"]:
                    active_games[game]["players"].append(member.display_name)

        # Оновлюємо Зал Слави ПЕРШИМ, Активні катки ДРУГИМИ
        bot.loop.create_task(update_fame_message(guild))
        bot.loop.create_task(update_live_message(guild))

    saved = load_sessions()
    for guild in bot.guilds:
        for channel in guild.voice_channels:
            for member in channel.members:
                if member.bot:
                    continue
                voice_start_times[member.id] = saved.get(member.id, datetime.now().timestamp())
                print(f"SESSION: {member.name}")

    save_sessions()

    if not daily_report.is_running():
        daily_report.start()

    await asyncio.sleep(2)
    await join_voice_safe()

    print(f"READY: {len(voice_start_times)} у войсі | {len(active_games)} активних ігор")

if __name__ == "__main__":
    keep_alive()
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise ValueError("DISCORD_TOKEN не знайдено!")
    bot.run(token)
