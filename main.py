import discord
from discord.ext import commands, tasks
from discord import app_commands
from flask import Flask, render_template
from threading import Thread
import os
import asyncio
import json
from datetime import datetime, time, timezone

# --- 1. ВЕБ-СЕРВЕР ДЛЯ RAILWAY ---
app = Flask(__name__, template_folder="templates")

@app.route('/')
def dashboard():
    stats = load_stats()

    top = sorted(stats["total"].items(), key=lambda x: x[1], reverse=True)[:10]

    formatted_top = []
    for uid, sec in top:
        user = bot.get_user(int(uid))
        name = user.name if user else f"ID {uid}"
        formatted_top.append((name, sec))

    chart_labels = list(range(1, 13))
    chart_data = [5, 10, 7, 12, 8, 15, 6, 9, 11, 14, 10, 13]

    return render_template(
        "dashboard.html",
        voice_online=len(voice_start_times),
        games=active_games,
        top_users=formatted_top,
        chart_labels=chart_labels,
        chart_data=chart_data
    )

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run, daemon=True); t.start()

# --- 2. НАЛАШТУВАННЯ ТА ПАМ'ЯТЬ ---
GLOBAL_SETTINGS = {
    "monitoring": True,
    "voice_guard": True,
    "voice_stats": True,
    "version": "v3.4.2",
    "image_url": "https://cdn.discordapp.com/avatars/1492662597357404211/a_4bf48afaac3798695e46c007ce568803.gif?size=1024"
}

DATA_DIR = "/app/data"
STATS_FILE = os.path.join(DATA_DIR, "voice_stats.json")
SESSIONS_FILE = os.path.join(DATA_DIR, "active_sessions.json")

os.makedirs(DATA_DIR, exist_ok=True)

VOICE_ID = 1458906259922354277
GAMING_LOG_ID = 1493054931224105070
GAMING_MONITOR_ID = 1495833786741424178  # Канал з живим списком ігор

# voice_start_times[user_id] = timestamp коли зайшов (float)
voice_start_times = {}

# Моніторинг ігор
# active_games = { "Dota 2": { "players": [member_id, ...], "start_time": timestamp } }
active_games = {}
gaming_message_id = None  # ID єдиного повідомлення яке редагується

# --- РОБОТА ЗІ СТАТИСТИКОЮ ---

def load_stats():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r") as f:
                data = json.load(f)
                if "total" not in data:
                    data["total"] = {}
                if "daily" not in data:
                    data["daily"] = {}
                return data
        except Exception as e:
            print(f"ERROR loading stats: {e}")
    return {"total": {}, "daily": {}}

def save_stats(data):
    try:
        with open(STATS_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"ERROR saving stats: {e}")

def load_sessions():
    if os.path.exists(SESSIONS_FILE):
        try:
            with open(SESSIONS_FILE, "r") as f:
                raw = json.load(f)
                # Ключі зберігаємо як int
                return {int(k): float(v) for k, v in raw.items()}
        except:
            pass
    return {}

def save_sessions():
    try:
        with open(SESSIONS_FILE, "w") as f:
            json.dump({str(k): v for k, v in voice_start_times.items()}, f)
    except Exception as e:
        print(f"ERROR saving sessions: {e}")

def format_time(seconds):
    """Форматує секунди у читабельний вигляд з секундами"""
    seconds = int(seconds)
    if seconds < 0:
        seconds = 0
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    res = []
    if h > 0:
        res.append(f"{h}г")
    if m > 0:
        res.append(f"{m}хв")
    # Секунди показуємо ЗАВЖДИ
    res.append(f"{s}с")
    return " ".join(res)

def add_voice_time(member_id: int, duration: float):
    """
    Додає duration до збереженої статистики.
    Викликається ТІЛЬКИ коли сесія закінчується (вихід з каналу).
    """
    if duration <= 0:
        return
    s = load_stats()
    uid = str(member_id)
    s["total"][uid] = s["total"].get(uid, 0) + duration
    s["daily"][uid] = s["daily"].get(uid, 0) + duration
    save_stats(s)
    print(f"STATS: +{format_time(duration)} для {member_id} | всього: {format_time(s['total'][uid])}")

def get_current_session(user_id: int) -> float:
    """Повертає тривалість поточної сесії в секундах (0 якщо не в войсі)"""
    if user_id in voice_start_times:
        return datetime.now().timestamp() - voice_start_times[user_id]
    return 0.0

def get_total_time(user_id: int) -> float:
    """Повертає загальний час = збережений + поточна сесія"""
    s = load_stats()
    saved = s["total"].get(str(user_id), 0)
    return saved + get_current_session(user_id)

def get_daily_time(user_id: int) -> float:
    """Повертає денний час = збережений + поточна сесія"""
    s = load_stats()
    saved = s["daily"].get(str(user_id), 0)
    return saved + get_current_session(user_id)

# --- ІНТЕНТИ ТА ІНІЦІАЛІЗАЦІЯ ---
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents, chunk_guilds_at_startup=True)

# --- 3. АВТОНОМНИЙ ВХІД У ВОЙС ---
async def join_voice_safe():
    if not GLOBAL_SETTINGS["voice_guard"]:
        return
    channel = bot.get_channel(VOICE_ID)
    if not channel:
        return
    current_vc = discord.utils.get(bot.voice_clients, guild=channel.guild)
    if not current_vc:
        try:
            await channel.connect(timeout=20.0, reconnect=True)
        except Exception as e:
            print(f"ERROR joining voice: {e}")
    elif current_vc.channel.id != VOICE_ID:
        await current_vc.move_to(channel)

# --- 4. СЛЕШ-КОМАНДИ ---

@bot.tree.command(name="midnight_info", description="Статус системи")
async def midnight_info(interaction: discord.Interaction):
    embed = discord.Embed(title="🌑 Midnight Bot | Status", color=0x2b2d31)
    for label, key in [("🎮 Game Monitor", "monitoring"), ("🎙️ Voice Guardian", "voice_guard"), ("📊 Voice Analytics", "voice_stats")]:
        status = "🟢 ON" if GLOBAL_SETTINGS[key] else "🔴 OFF"
        embed.add_field(name=label, value=f"Статус: `{status}`", inline=True)
    embed.add_field(name="👥 Зараз у войсі", value=f"`{len(voice_start_times)}` користувачів", inline=True)
    embed.set_thumbnail(url=GLOBAL_SETTINGS["image_url"])
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="mystats", description="Твоя особиста статистика")
async def mystats(interaction: discord.Interaction):
    if not GLOBAL_SETTINGS["voice_stats"]:
        return await interaction.response.send_message("❌ Статистика вимкнена", ephemeral=True)

    uid = interaction.user.id
    total = get_total_time(uid)
    daily = get_daily_time(uid)
    current = get_current_session(uid)

    embed = discord.Embed(
        title=f"📊 Статистика {interaction.user.display_name}",
        color=0x3498db
    )
    embed.add_field(name="📅 Сьогодні", value=f"`{format_time(daily)}`", inline=True)
    embed.add_field(name="🏆 Весь час", value=f"`{format_time(total)}`", inline=True)

    if current > 0:
        embed.add_field(name="🎙️ Поточна сесія", value=f"`{format_time(current)}`", inline=True)

    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="leaderboard", description="Топ активності")
@app_commands.choices(період=[
    app_commands.Choice(name="Весь час", value="total"),
    app_commands.Choice(name="Сьогодні", value="daily")
])
async def leaderboard(interaction: discord.Interaction, період: app_commands.Choice[str]):
    if not GLOBAL_SETTINGS["voice_stats"]:
        return await interaction.response.send_message("❌ Вимкнено", ephemeral=True)

    s = load_stats()
    saved = dict(s.get(період.value, {}))

    # Додаємо поточні сесії БЕЗ подвійного рахування
    for user_id, start_time in voice_start_times.items():
        uid = str(user_id)
        current = datetime.now().timestamp() - start_time
        saved[uid] = saved.get(uid, 0) + current

    sorted_s = sorted(saved.items(), key=lambda x: x[1], reverse=True)[:10]

    res = ""
    medals = ["🥇", "🥈", "🥉"]
    for i, (u_id, sec) in enumerate(sorted_s):
        member = interaction.guild.get_member(int(u_id))
        if not member:
            try:
                member = await bot.fetch_user(int(u_id))
            except:
                pass
        name = member.display_name if hasattr(member, 'display_name') else (member.name if member else f"ID: {u_id}")
        medal = medals[i] if i < 3 else f"**{i+1}.**"
        res += f"{medal} {name} — `{format_time(sec)}`\n"

    embed = discord.Embed(
        title=f"🏆 Топ активності | {період.name}",
        description=res or "Ще немає даних",
        color=0xf1c40f
    )
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

# --- 5. ЛОГІКА ПОДІЙ ---

@bot.event
async def on_voice_state_update(member, before, after):
    print(f"VOICE: {member.name} | {before.channel} -> {after.channel}")

    # Voice Guard — автоматичне повернення бота
    if member.id == bot.user.id and before.channel and not after.channel:
        if GLOBAL_SETTINGS["voice_guard"]:
            await asyncio.sleep(5)
            await join_voice_safe()
        return

    # Ботів не відстежуємо
    if member.bot:
        return

    if not GLOBAL_SETTINGS["voice_stats"]:
        return

    now = datetime.now().timestamp()

    # ЗАЙШОВ у войс (з нікуди)
    if not before.channel and after.channel:
        voice_start_times[member.id] = now
        save_sessions()
        print(f"START: {member.name} @ {after.channel.name}")

    # ВИЙШОВ з войсу (в нікуди)
    elif before.channel and not after.channel:
        if member.id in voice_start_times:
            duration = now - voice_start_times.pop(member.id)
            save_sessions()
            add_voice_time(member.id, duration)
            print(f"END: {member.name} | сесія: {format_time(duration)}")

    # ПЕРЕЙШОВ між каналами — сесія ПРОДОВЖУЄТЬСЯ, нічого не чіпаємо
    elif before.channel and after.channel and before.channel.id != after.channel.id:
        print(f"SWITCH: {member.name} | {before.channel.name} -> {after.channel.name}")

# --- 6. ЩОДЕННИЙ ЗВІТ ---

@tasks.loop(time=time(hour=0, minute=0, tzinfo=timezone.utc))
async def daily_report():
    if not GLOBAL_SETTINGS["voice_stats"]:
        return

    # Спочатку зберігаємо поточні сесії перед скиданням
    now = datetime.now().timestamp()
    for user_id, start_time in list(voice_start_times.items()):
        duration = now - start_time
        if duration > 0:
            add_voice_time(user_id, duration)
            voice_start_times[user_id] = now  # Скидаємо таймер сесії на новий день

    ch = bot.get_channel(GAMING_LOG_ID)
    s = load_stats()

    if not s["daily"] or not ch:
        s["daily"] = {}
        save_stats(s)
        return

    top = sorted(s["daily"].items(), key=lambda x: x[1], reverse=True)[:5]

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    lines = []
    for i, (uid, sec) in enumerate(top):
        user = bot.get_user(int(uid))
        name = user.name if user else f"User {uid}"
        lines.append(f"{medals[i]} {name} — {format_time(sec)}")

    embed = discord.Embed(
        title="📊 Підсумки дня",
        description="\n".join(lines),
        color=0x9b59b6,
        timestamp=datetime.now(timezone.utc)
    )
    await ch.send(embed=embed)

    # Скидаємо денну статистику
    s["daily"] = {}
    save_stats(s)
    print("DAILY RESET: Денна статистика скинута")

# --- 7. МОНІТОРИНГ ІГОР ---

def get_game_name(member):
    """Максимально всеїдна функція: ігнорує статуси, бере всі ігри та стріми"""
    if not member.activities:
        return None
        
    for act in member.activities:
        # Пропускаємо Custom Status та прослуховування Spotify
        if isinstance(act, discord.CustomActivity) or act.name == "Spotify":
            continue
            
        # Якщо це будь-яка інша активність (гра, стрім) і вона має назву — беремо її
        if hasattr(act, 'name') and act.name:
            return act.name
            
    return None

def build_games_embed() -> discord.Embed:
    """Будує embed зі списком всіх активних ігор"""
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
        players = data["players"]
        start = data["start_time"]
        duration = int(datetime.now().timestamp() - start)
        m = duration // 60
        h = m // 60
        time_str = f"{h}г {m % 60}хв" if h > 0 else f"{m}хв"

        names = ", ".join(players) if players else "?"
        lines.append(f"**{game_name}**\n👥 {names}\n⏱️ {time_str}\n")

    embed.description = "\n".join(lines)
    embed.set_footer(text="Оновлюється автоматично")
    return embed

async def update_games_message(guild: discord.Guild):
    """Оновлює або створює єдине повідомлення зі списком ігор"""
    global gaming_message_id

    ch = bot.get_channel(GAMING_MONITOR_ID)
    if not ch:
        return

    embed = build_games_embed()

    # Пробуємо відредагувати існуюче повідомлення
    if gaming_message_id:
        try:
            msg = await ch.fetch_message(gaming_message_id)
            await msg.edit(embed=embed)
            return
        except discord.NotFound:
            gaming_message_id = None
        except Exception as e:
            print(f"ERROR editing games message: {e}")

    # Якщо повідомлення не існує — шукаємо останнє повідомлення бота в каналі
    try:
        async for msg in ch.history(limit=20):
            if msg.author.id == bot.user.id and msg.embeds:
                gaming_message_id = msg.id
                await msg.edit(embed=embed)
                return
    except:
        pass

    # Якщо нічого не знайшли — створюємо нове
    try:
        msg = await ch.send(embed=embed)
        gaming_message_id = msg.id
    except Exception as e:
        print(f"ERROR sending games message: {e}")

@bot.event
async def on_presence_update(before, after):
    if not GLOBAL_SETTINGS["monitoring"]:
        return
    if after.bot:
        return

    # Затримка, щоб Discord оновив статус
    await asyncio.sleep(1)
    guild = after.guild

    before_game = get_game_name(before)
    after_game = get_game_name(after)

    if before_game == after_game:
        return  # Нічого не змінилось

    changed = False

    # Гравець ВИЙШОВ з гри
    if before_game and before_game in active_games:
        # Перераховуємо актуальний список гравців для цієї гри
        players = [m.display_name for m in guild.members if get_game_name(m) == before_game]
        if not players:
            if before_game in active_games:
                del active_games[before_game]
        else:
            active_games[before_game]["players"] = players
        changed = True

    # Гравець ЗАЙШОВ у гру
    if after_game:
        # Збираємо всіх, хто зараз у цій грі
        players_in_game = [m.display_name for m in guild.members if get_game_name(m) == after_game]

        if len(players_in_game) >= 1:
            if after_game not in active_games:
                active_games[after_game] = {
                    "players": players_in_game,
                    "start_time": datetime.now().timestamp()
                }
            else:
                active_games[after_game]["players"] = players_in_game
            changed = True

    if changed:
        await update_games_message(guild)

# --- 8. СТАРТ БОТА ---

@bot.event
async def on_ready():
    global voice_start_times, active_games
    print(f'--- Midnight {GLOBAL_SETTINGS["version"]} ONLINE ---')

    await bot.tree.sync()

    # --- СКАНУВАННЯ ІГОР ПРИ ЗАПУСКУ ---
    # Це вирішує проблему амнезії, коли бот не бачив гравців, що ВЖЕ грали до запуску
    active_games.clear()
    for guild in bot.guilds:
        if not GLOBAL_SETTINGS["monitoring"]:
            continue
            
        changed_games = False
        for member in guild.members:
            if member.bot:
                continue
                
            game = get_game_name(member)
            if game:
                if game not in active_games:
                    active_games[game] = {
                        "players": [member.display_name],
                        "start_time": datetime.now().timestamp()
                    }
                else:
                    if member.display_name not in active_games[game]["players"]:
                        active_games[game]["players"].append(member.display_name)
                changed_games = True
        
        # Оновлюємо табло один раз для всього серверу при старті
        if changed_games:
            bot.loop.create_task(update_games_message(guild))

    # --- ВІДНОВЛЕННЯ СЕСІЙ ВОЙСУ ---
    saved_sessions = load_sessions()

    for guild in bot.guilds:
        for channel in guild.voice_channels:
            for member in channel.members:
                if member.bot:
                    continue
                if member.id in saved_sessions:
                    voice_start_times[member.id] = saved_sessions[member.id]
                    print(f"RESTORED: {member.name}")
                else:
                    voice_start_times[member.id] = datetime.now().timestamp()
                    print(f"NEW SESSION (on_ready): {member.name}")

    save_sessions()

    if not daily_report.is_running():
        daily_report.start()

    await asyncio.sleep(2)
    await join_voice_safe()

    print(f"READY: відстежую {len(voice_start_times)} юзерів у войсі та {len(active_games)} активних ігор")

if __name__ == "__main__":
    keep_alive()
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise ValueError("DISCORD_TOKEN не знайдено в змінних середовища!")
    bot.run(token)
