import discord
from discord.ext import commands, tasks
from discord import app_commands
from flask import Flask
from threading import Thread
import os
import asyncio
import json
from datetime import datetime, time, timezone

# --- 1. ВЕБ-СЕРВЕР ДЛЯ ПІДТРИМКИ ЖИТТЄДІЯЛЬНОСТІ ---
app = Flask('')
@app.route('/')
def home(): return "MIDNIGHT SYSTEM ONLINE"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run, daemon=True); t.start()

# --- 2. НАЛАШТУВАННЯ ТА БАЗА ДАНИХ (VOLUME) ---
GLOBAL_SETTINGS = {
    "monitoring": True,    # Анонси ігор (від 3-х осіб)
    "voice_guard": True,   # Авто-вхід бота у голосовий канал
    "voice_stats": True,   # Збір статистики часу
    "version": "v3.2",
    "image_url": "https://cdn.discordapp.com/avatars/1492662597357404211/a_4bf48afaac3798695e46c007ce568803.gif?size=1024"
}

# ШЛЯХ ДО VOLUME (Має збігатися з Mount Path у Railway)
DATA_DIR = "/app/data"
STATS_FILE = os.path.join(DATA_DIR, "voice_stats.json")

# Створюємо папку для даних, якщо її ще немає
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)

# ТВОЇ ID (Перевір їх ще раз)
VOICE_ID = 1458906259922354277 
GAMING_LOG_ID = 1493054931224105070 

active_sessions = {}
pending_announcements = set()
voice_start_times = {}

def load_stats():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r") as f: return json.load(f)
        except: pass
    return {"total": {}, "daily": {}}

def save_stats(data):
    try:
        with open(STATS_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Помилка збереження: {e}")

def format_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    if h > 0: return f"{h}г {m}хв"
    return f"{m}хв"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# --- 3. КОМАНДИ КЕРУВАННЯ ---

@bot.tree.command(name="midnight_info", description="Системна інформація та статус модулів")
async def midnight_info(interaction: discord.Interaction):
    embed = discord.Embed(title="🌑 Midnight Bot | System Control", color=0x2b2d31)
    
    m_status = "🟢 ON" if GLOBAL_SETTINGS["monitoring"] else "🔴 OFF"
    v_status = "🟢 ON" if GLOBAL_SETTINGS["voice_guard"] else "🔴 OFF"
    s_status = "🟢 ON" if GLOBAL_SETTINGS["voice_stats"] else "🔴 OFF"
    
    embed.add_field(name="🎮 Game Monitor", value=f"Статус: `{m_status}`", inline=True)
    embed.add_field(name="🎙️ Voice Guardian", value=f"Статус: `{v_status}`", inline=True)
    embed.add_field(name="📊 Voice Analytics", value=f"Статус: `{s_status}`", inline=True)
    
    embed.add_field(name="🛠️ Команди", value=(
        "`/set_monitoring` • `/set_voice` • `/set_stats`\n"
        "`/leaderboard` — Рейтинг активності"
    ), inline=False)
    
    embed.set_thumbnail(url=GLOBAL_SETTINGS["image_url"])
    embed.set_footer(text=f"Midnight System {GLOBAL_SETTINGS['version']} | Дані в безпеці")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="set_stats")
@app_commands.choices(стан=[app_commands.Choice(name="Увімкнути", value="true"), app_commands.Choice(name="Вимкнути", value="false")])
async def set_stats(interaction: discord.Interaction, стан: app_commands.Choice[str]):
    GLOBAL_SETTINGS["voice_stats"] = (стан.value == "true")
    await interaction.response.send_message(f"📊 Статистика: **{'Увімкнено' if GLOBAL_SETTINGS['voice_stats'] else 'Вимкнено'}**", ephemeral=True)

@bot.tree.command(name="set_monitoring")
@app_commands.choices(стан=[app_commands.Choice(name="Увімкнути", value="true"), app_commands.Choice(name="Вимкнути", value="false")])
async def set_monitoring(interaction: discord.Interaction, стан: app_commands.Choice[str]):
    GLOBAL_SETTINGS["monitoring"] = (стан.value == "true")
    await interaction.response.send_message(f"📡 Моніторинг ігор: **{'Увімкнено' if GLOBAL_SETTINGS['monitoring'] else 'Вимкнено'}**", ephemeral=True)

@bot.tree.command(name="set_voice")
@app_commands.choices(стан=[app_commands.Choice(name="Увімкнути", value="true"), app_commands.Choice(name="Вимкнути", value="false")])
async def set_voice(interaction: discord.Interaction, стан: app_commands.Choice[str]):
    GLOBAL_SETTINGS["voice_guard"] = (стан.value == "true")
    if not GLOBAL_SETTINGS["voice_guard"]:
        for vc in bot.voice_clients: await vc.disconnect(force=True)
    await interaction.response.send_message(f"🎙️ Voice Guardian: **{'Увімкнено' if GLOBAL_SETTINGS['voice_guard'] else 'Вимкнено'}**", ephemeral=True)

# --- 4. ЛІДЕРБОРД (ДЕНЬ / ВЕСЬ ЧАС) ---

@bot.tree.command(name="leaderboard", description="Топ активності у голосових каналах")
@app_commands.choices(період=[
    app_commands.Choice(name="Весь час", value="total"),
    app_commands.Choice(name="Сьогодні", value="daily")
])
async def leaderboard(interaction: discord.Interaction, період: app_commands.Choice[str]):
    if not GLOBAL_SETTINGS["voice_stats"]:
        return await interaction.response.send_message("❌ Модуль статистики вимкнено.", ephemeral=True)

    stats = load_stats()
    target_data = stats.get(період.value, {})
    sorted_stats = sorted(target_data.items(), key=lambda x: x[1], reverse=True)[:10]
    
    title_type = "За весь час" if період.value == "total" else "За сьогодні"
    embed = discord.Embed(title="🏆 Midnight Voice Leaderboard", color=0xf1c40f)
    
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    leader_text = ""
    for i, (u_id, sec) in enumerate(sorted_stats, 1):
        member = interaction.guild.get_member(int(u_id))
        name = member.display_name if member else f"Гравець"
        prefix = medals.get(i, f"**{i}.**")
        leader_text += f"{prefix} {name} — `{format_time(sec)}`\n"
    
    embed.add_field(name=f"📊 Рейтинг: {title_type}", value=leader_text or "Даних поки немає", inline=False)
    embed.set_footer(text=f"Дані зберігаються на Volume")
    await interaction.response.send_message(embed=embed)

# --- 5. ЛОГІКА ТА ЗБЕРЕЖЕННЯ ---

@bot.event
async def on_voice_state_update(member, before, after):
    # Авто-вхід бота
    if member.id == bot.user.id and before.channel and not after.channel:
        if GLOBAL_SETTINGS["voice_guard"]:
            await asyncio.sleep(5)
            ch = bot.get_channel(VOICE_ID)
            if ch: await ch.connect()

    if member.bot or not GLOBAL_SETTINGS["voice_stats"]: return

    # Трекінг часу
    if not before.channel and after.channel:
        voice_start_times[member.id] = datetime.now().timestamp()
    elif before.channel and not after.channel:
        if member.id in voice_start_times:
            duration = datetime.now().timestamp() - voice_start_times[member.id]
            del voice_start_times[member.id]
            s = load_stats()
            uid = str(member.id)
            s["total"][uid] = s["total"].get(uid, 0) + duration
            s["daily"][uid] = s["daily"].get(uid, 0) + duration
            save_stats(s)

@tasks.loop(time=time(hour=0, minute=0, tzinfo=timezone.utc))
async def daily_report():
    if not GLOBAL_SETTINGS["voice_stats"]: return
    ch = bot.get_channel(GAMING_LOG_ID)
    s = load_stats()
    if not s["daily"] or not ch: return
    
    top = sorted(s["daily"].items(), key=lambda x: x[1], reverse=True)[:5]
    msg = "📊 **Підсумки дня в голосових каналах:**\n"
    for i, (uid, sec) in enumerate(top, 1):
        u = bot.get_user(int(uid))
        msg += f"{i}. **{u.display_name if u else uid}** — {format_time(sec)}\n"
    
    await ch.send(msg)
    s["daily"] = {}
    save_stats(s)

# --- 6. МОНІТОРИНГ ІГОР ---

async def announce_game(guild_id, game_name):
    await asyncio.sleep(30)
    g = bot.get_guild(guild_id)
    if not g: return
    players = [m for m in g.members if m.activity and m.activity.type == discord.ActivityType.playing and m.activity.name == game_name]
    
    if len(players) >= 3:
        active_sessions[game_name] = [m.id for m in players]
        ch = bot.get_channel(GAMING_LOG_ID)
        if ch:
            names = [m.display_name for m in players]
            content = f"🎮 **Бачу нову катку!**\n**Гравці:** {', '.join(names)}\n**Гра:** {game_name}"
            try:
                if isinstance(ch, discord.ForumChannel): await ch.create_thread(name=f"🎮 {game_name}", content=content)
                else: await ch.send(content)
            except: pass
    pending_announcements.discard(game_name)

@bot.event
async def on_presence_update(before, after):
    if not GLOBAL_SETTINGS["monitoring"]: return
    if after.activity and after.activity.type == discord.ActivityType.playing:
        if not (before.activity and before.activity.name == after.activity.name):
            name = after.activity.name
            if name not in pending_announcements and name not in active_sessions:
                pending_announcements.add(name)
                asyncio.create_task(announce_game(after.guild.id, name))

@bot.event
async def on_ready():
    print(f'--- Midnight ONLINE | Volume: {STATS_FILE} ---')
    await bot.tree.sync()
    if not daily_report.is_running(): daily_report.start()

if __name__ == "__main__":
    keep_alive()
    bot.run("MTQ5MjY2MjU5NzM1NzQwNDIxMQ.GYOjct.FXboTEBC3CQDhARJM4MJSSQJGtVkhp6yQSAlks")
