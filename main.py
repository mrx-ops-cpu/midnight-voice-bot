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
    "monitoring": True,
    "voice_guard": True,
    "voice_stats": True,
    "version": "v3.3.3",
    "image_url": "https://cdn.discordapp.com/avatars/1492662597357404211/a_4bf48afaac3798695e46c007ce568803.gif?size=1024"
}

DATA_DIR = "/app/data"
STATS_FILE = os.path.join(DATA_DIR, "voice_stats.json")

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)

VOICE_ID = 1458906259922354277 
GAMING_LOG_ID = 1493054931224105070 

voice_start_times = {}
active_sessions = {}
pending_announcements = set()

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
    seconds = int(seconds)
    h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
    res = []
    if h > 0: res.append(f"{h}г")
    if m > 0: res.append(f"{m}хв")
    if s > 0 or not res: res.append(f"{s}с")
    return " ".join(res)

# --- ІНТЕНТИ ТА ІНІЦІАЛІЗАЦІЯ ---
intents = discord.Intents.all()
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix='!', intents=intents, chunk_guilds_at_startup=True)

# --- 3. ФУНКЦІЯ АВТОНОМНОГО ВХОДУ ---
async def join_voice_safe():
    if not GLOBAL_SETTINGS["voice_guard"]: return
    channel = bot.get_channel(VOICE_ID)
    if not channel: return
    current_vc = discord.utils.get(bot.voice_clients, guild=channel.guild)
    if not current_vc:
        try: await channel.connect(timeout=20.0, reconnect=True)
        except: pass
    elif current_vc.channel.id != VOICE_ID:
        await current_vc.move_to(channel)

# --- 4. СЛЕШ-КОМАНДИ ---

@bot.tree.command(name="midnight_info", description="Статус системи")
async def midnight_info(interaction: discord.Interaction):
    embed = discord.Embed(title="🌑 Midnight Bot | Status", color=0x2b2d31)
    for k, v in [("🎮 Game Monitor", "monitoring"), ("🎙️ Voice Guardian", "voice_guard"), ("📊 Voice Analytics", "voice_stats")]:
        status = "🟢 ON" if GLOBAL_SETTINGS[v] else "🔴 OFF"
        embed.add_field(name=k, value=f"Статус: `{status}`", inline=True)
    embed.set_thumbnail(url=GLOBAL_SETTINGS["image_url"])
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
        for vc in bot.voice_clients: await vc.disconnect()
    await interaction.response.send_message(f"🎙️ Voice Guardian: **{'Увімкнено' if GLOBAL_SETTINGS['voice_guard'] else 'Вимкнено'}**")

@bot.tree.command(name="set_stats")
@app_commands.choices(стан=[app_commands.Choice(name="Увімкнути", value="on"), app_commands.Choice(name="Вимкнути", value="off")])
async def set_stats(interaction: discord.Interaction, стан: app_commands.Choice[str]):
    GLOBAL_SETTINGS["voice_stats"] = (стан.value == "on")
    await interaction.response.send_message(f"📊 Статистика: **{'Увімкнено' if GLOBAL_SETTINGS['voice_stats'] else 'Вимкнено'}**")

@bot.tree.command(name="leaderboard", description="Топ активності")
@app_commands.choices(період=[app_commands.Choice(name="Весь час", value="total"), app_commands.Choice(name="Сьогодні", value="daily")])
async def leaderboard(interaction: discord.Interaction, період: app_commands.Choice[str]):
    if not GLOBAL_SETTINGS["voice_stats"]: return await interaction.response.send_message("❌ Вимкнено", ephemeral=True)
    
    stats_data = load_stats().get(період.value, {})
    sorted_s = sorted(stats_data.items(), key=lambda x: x[1], reverse=True)[:10]
    
    res = ""
    for i, (u_id, sec) in enumerate(sorted_s, 1):
        member = interaction.guild.get_member(int(u_id))
        if not member:
            try: member = await bot.fetch_user(int(u_id))
            except: pass
        name = member.display_name if hasattr(member, 'display_name') else (member.name if member else f"ID: {u_id}")
        res += f"**{i}.** {name} — `{format_time(sec)}`\n"
    
    await interaction.response.send_message(embed=discord.Embed(title=f"🏆 Топ {період.name}", description=res or "Пусто", color=0xf1c40f))

# --- 5. ЛОГІКА ПОДІЙ ---

@bot.event
async def on_voice_state_update(member, before, after):
    # Лог для відладки
    print(f"DEBUG: {member.name} {before.channel} -> {after.channel}")

    if member.id == bot.user.id and before.channel and not after.channel:
        if GLOBAL_SETTINGS["voice_guard"]:
            await asyncio.sleep(5)
            await join_voice_safe()

    if member.bot or not GLOBAL_SETTINGS["voice_stats"]: return
    
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
    msg = "📊 **Підсумки дня:**\n" + "\n".join([f"{i+1}. {bot.get_user(int(uid)).display_name} — {format_time(sec)}" for i, (uid, sec) in enumerate(top)])
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
            content = f"🎮 **Нова катка!**\n**Гравці:** {', '.join([m.display_name for m in players])}\n**Гра:** {game_name}"
            if isinstance(ch, discord.ForumChannel): await ch.create_thread(name=f"🎮 {game_name}", content=content)
            else: await ch.send(content)
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
    print(f'--- Midnight {GLOBAL_SETTINGS["version"]} ONLINE ---')
    await bot.tree.sync()
    if not daily_report.is_running(): daily_report.start()
    await asyncio.sleep(2)
    await join_voice_safe()

if __name__ == "__main__":
    keep_alive()
    bot.run("MTQ5MjY2MjU5NzM1NzQwNDIxMQ.GYOjct.FXboTEBC3CQDhARJM4MJSSQJGtVkhp6yQSAlks")
