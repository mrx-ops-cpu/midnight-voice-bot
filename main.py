import discord
from discord.ext import commands, tasks
from discord import app_commands
from flask import Flask
from threading import Thread
import os
import asyncio
import json
from datetime import datetime, time, timezone

# --- 1. ВЕБ-СЕРВЕР ДЛЯ RAILWAY ---
app = Flask('')
@app.route('/')
def home(): return "MIDNIGHT SYSTEM ONLINE"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run, daemon=True); t.start()

# --- 2. НАЛАШТУВАННЯ ТА ПАМ'ЯТЬ (VOLUME) ---
GLOBAL_SETTINGS = {
    "monitoring": True,    # Анонси ігор
    "voice_guard": True,   # Авто-вхід бота у войс
    "voice_stats": True,   # Збір статистики
    "version": "v3.3",
    "image_url": "https://cdn.discordapp.com/avatars/1492662597357404211/a_4bf48afaac3798695e46c007ce568803.gif?size=1024"
}

# Шлях до твого підключеного Volume
DATA_DIR = "/app/data"
STATS_FILE = os.path.join(DATA_DIR, "voice_stats.json")

# Авто-створення папки на диску
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)

# Твої ID
VOICE_ID = 1458906259922354277 
GAMING_LOG_ID = 1493054931224105070 

active_sessions = {}
pending_announcements = set()
voice_start_times = {}

# Робота з базою даних
def load_stats():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r") as f: return json.load(f)
        except: pass
    return {"total": {}, "daily": {}}

def save_stats(data):
    try:
        with open(STATS_FILE, "w") as f: json.dump(data, f, indent=4)
    except: pass

def format_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    if h > 0: return f"{h}г {m}хв"
    return f"{m}хв"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# --- 3. ФУНКЦІЯ АВТОНОМНОГО ВХОДУ ---
async def join_voice_safe():
    if not GLOBAL_SETTINGS["voice_guard"]: return
    
    channel = bot.get_channel(VOICE_ID)
    if not channel:
        print(f"❌ Канал {VOICE_ID} не знайдено.")
        return

    # Перевірка, чи ми вже підключені
    current_vc = discord.utils.get(bot.voice_clients, guild=channel.guild)
    
    if not current_vc:
        try:
            await channel.connect(timeout=20.0, reconnect=True)
            print(f"✅ Успішно зайшов у канал: {channel.name}")
        except Exception as e:
            print(f"❌ Помилка входу: {e}")
    elif current_vc.channel.id != VOICE_ID:
        await current_vc.move_to(channel)

# --- 4. СЛЕШ-КОМАНДИ ---

@bot.tree.command(name="midnight_info", description="Статус системи та модулів")
async def midnight_info(interaction: discord.Interaction):
    embed = discord.Embed(title="🌑 Midnight Bot | System Status", color=0x2b2d31)
    
    m_status = "🟢 ON" if GLOBAL_SETTINGS["monitoring"] else "🔴 OFF"
    v_status = "🟢 ON" if GLOBAL_SETTINGS["voice_guard"] else "🔴 OFF"
    s_status = "🟢 ON" if GLOBAL_SETTINGS["voice_stats"] else "🔴 OFF"
    
    embed.add_field(name="🎮 Game Monitor", value=f"Статус: `{m_status}`", inline=True)
    embed.add_field(name="🎙️ Voice Guardian", value=f"Статус: `{v_status}`", inline=True)
    embed.add_field(name="📊 Voice Analytics", value=f"Статус: `{s_status}`", inline=True)
    
    embed.set_thumbnail(url=GLOBAL_SETTINGS["image_url"])
    embed.set_footer(text=f"Midnight {GLOBAL_SETTINGS['version']} | Persistent Storage Active")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="leaderboard", description="Топ активності")
@app_commands.choices(період=[
    app_commands.Choice(name="Весь час", value="total"),
    app_commands.Choice(name="Сьогодні", value="daily")
])
async def leaderboard(interaction: discord.Interaction, період: app_commands.Choice[str]):
    if not GLOBAL_SETTINGS["voice_stats"]:
        return await interaction.response.send_message("❌ Статистика вимкнена.", ephemeral=True)

    stats = load_stats().get(період.value, {})
    sorted_stats = sorted(stats.items(), key=lambda x: x[1], reverse=True)[:10]
    
    embed = discord.Embed(title=f"🏆 Топ активності ({період.name})", color=0xf1c40f)
    leader_text = ""
    for i, (u_id, sec) in enumerate(sorted_stats, 1):
        member = interaction.guild.get_member(int(u_id))
        name = member.display_name if member else f"ID: {u_id}"
        leader_text += f"**{i}.** {name} — `{format_time(sec)}`\n"
    
    embed.description = leader_text or "Даних поки немає."
    await interaction.response.send_message(embed=embed)

# --- 5. ЛОГІКА ПОДІЙ ---

@bot.event
async def on_voice_state_update(member, before, after):
    # Якщо бота вигнали - він повертається
    if member.id == bot.user.id and before.channel and not after.channel:
        if GLOBAL_SETTINGS["voice_guard"]:
            await asyncio.sleep(5)
            await join_voice_safe()

    if member.bot or not GLOBAL_SETTINGS["voice_stats"]: return

    # Трекінг часу для статистики
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
    ch, s = bot.get_channel(GAMING_LOG_ID), load_stats()
    if not s["daily"] or not ch: return
    
    top = sorted(s["daily"].items(), key=lambda x: x[1], reverse=True)[:5]
    msg = "📊 **Підсумки дня:**\n"
    for i, (uid, sec) in enumerate(top, 1):
        u = bot.get_user(int(uid))
        msg += f"{i}. **{u.display_name if u else uid}** — {format_time(sec)}\n"
    
    await ch.send(msg)
    s["daily"] = {} # Очищення дня
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
            content = f"🎮 **Нова катка!**\n**Гравці:** {', '.join(names)}\n**Гра:** {game_name}"
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

# --- 7. ЗАПУСК ---

@bot.event
async def on_ready():
    print(f'--- Midnight {GLOBAL_SETTINGS["version"]} ONLINE ---')
    print(f'--- Папка даних: {DATA_DIR} ---')
    await bot.tree.sync()
    if not daily_report.is_running(): daily_report.start()
    
    # Автоматичний вхід при включенні
    await asyncio.sleep(2)
    await join_voice_safe()

if __name__ == "__main__":
    keep_alive()
    bot.run("MTQ5MjY2MjU5NzM1NzQwNDIxMQ.GYOjct.FXboTEBC3CQDhARJM4MJSSQJGtVkhp6yQSAlks")
