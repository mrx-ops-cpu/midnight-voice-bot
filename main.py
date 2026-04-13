import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask
from threading import Thread
import os
import asyncio
import random

# --- 1. ВЕБ-СЕРВЕР ---
app = Flask('')
@app.route('/')
def home(): return "MIDNIGHT SYSTEM ONLINE"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run, daemon=True); t.start()

# --- 2. НАЛАШТУВАННЯ ---
GLOBAL_SETTINGS = {
    "monitoring": True,   
    "voice_guard": True,  
    "version": "v2.3",
    "image_url": "https://cdn.discordapp.com/avatars/1492662597357404211/a_4bf48afaac3798695e46c007ce568803.gif?size=1024"
}

# Зберігаємо ID гравців, які вже анонсовані в поточній сесії
# Структура: { "Назва гри": [ID1, ID2, ID3] }
active_sessions = {}

VOICE_ID = 1458906259922354277 
GAMING_LOG_ID = 1493054931224105070 

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# --- 3. ЛОГІКА ГОЛОСУ ---
async def safe_join():
    if not GLOBAL_SETTINGS["voice_guard"]: return
    try:
        await bot.wait_until_ready()
        channel = bot.get_channel(VOICE_ID)
        if not channel: return
        vc = discord.utils.get(bot.voice_clients, guild=channel.guild)
        if not vc or not vc.is_connected():
            await channel.connect(reconnect=True, timeout=20)
    except Exception: pass

# --- 4. КОМАНДИ ---

@bot.tree.command(name="midnight_info", description="Системна інформація бота")
async def midnight_info(interaction: discord.Interaction):
    embed = discord.Embed(title="🌑 Midnight Bot | System Info", color=0x2b2d31)
    m_status = "🟢 Увімкнено" if GLOBAL_SETTINGS["monitoring"] else "🔴 Вимкнено"
    v_status = "🟢 Активний" if GLOBAL_SETTINGS["voice_guard"] else "🔴 Неактивний"
    embed.add_field(name="🎮 Моніторинг ігор", value=f"Статус: {m_status}", inline=False)
    embed.add_field(name="🎙️ Voice Guardian", value=f"Статус: {v_status}", inline=False)
    embed.add_field(name="🛠️ Керування", value="`/set_monitoring`, `/set_voice`, `/midnight_ping`")
    embed.set_thumbnail(url=GLOBAL_SETTINGS["image_url"])
    embed.set_footer(text=f"Midnight Bot {GLOBAL_SETTINGS['version']}")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="set_monitoring")
@app_commands.choices(стан=[app_commands.Choice(name="True", value="true"), app_commands.Choice(name="False", value="false")])
async def set_monitoring(interaction: discord.Interaction, стан: app_commands.Choice[str]):
    GLOBAL_SETTINGS["monitoring"] = (стан.value == "true")
    await interaction.response.send_message(f"📡 Моніторинг: {GLOBAL_SETTINGS['monitoring']}", ephemeral=True)

@bot.tree.command(name="set_voice")
@app_commands.choices(стан=[app_commands.Choice(name="True", value="true"), app_commands.Choice(name="False", value="false")])
async def set_voice(interaction: discord.Interaction, стан: app_commands.Choice[str]):
    GLOBAL_SETTINGS["voice_guard"] = (стан.value == "true")
    if not GLOBAL_SETTINGS["voice_guard"]:
        for vc in bot.voice_clients: await vc.disconnect(force=True)
    else: await safe_join()
    await interaction.response.send_message(f"🎙️ Voice Guardian: {GLOBAL_SETTINGS['voice_guard']}", ephemeral=True)

@bot.tree.command(name="midnight_ping")
async def midnight_ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"📡 {round(bot.latency * 1000)}ms", ephemeral=True)

# --- 5. ФІКС СПАМУ (SESSION CONTROL V2) ---

@bot.event
async def on_presence_update(before, after):
    if not GLOBAL_SETTINGS["monitoring"]: return
    
    # Перевіряємо, чи користувач САМЕ ЗАРАЗ почав грати
    was_playing = before.activity and before.activity.type == discord.ActivityType.playing
    is_playing = after.activity and after.activity.type == discord.ActivityType.playing
    
    if is_playing and not was_playing:
        game_name = after.activity.name
        guild = after.guild
        
        # Очищуємо сесію, якщо в ній нікого не залишилося
        if game_name in active_sessions:
            still_online = []
            for p_id in active_sessions[game_name]:
                m = guild.get_member(p_id)
                if m and m.activity and m.activity.name == game_name:
                    still_online.append(p_id)
            
            if still_online:
                # Якщо в цій грі ще є люди з минулого анонсу — нічого не пишемо
                active_sessions[game_name] = still_online
                return
            else:
                # Всі вийшли — видаляємо стару сесію
                del active_sessions[game_name]

        # Шукаємо всіх, хто зараз у цій грі
        current_players = [m for m in guild.members 
                          if m.activity and m.activity.type == discord.ActivityType.playing and m.activity.name == game_name]
        
        # Анонсуємо, якщо хоча б двоє (або один, якщо хочеш бачити кожного)
        if len(current_players) >= 2:
            active_sessions[game_name] = [m.id for m in current_players]
            
            channel = bot.get_channel(GAMING_LOG_ID)
            if not channel: return
            
            names = [m.display_name for m in current_players]
            greetings = ["О, вже збирається непогане паті!", "Бачу, намічається катка!", "Вдалого полювання!"]
            content = f"🎮 **{random.choice(greetings)}**\n**Гравці:** {', '.join(names)}\n**Гра:** {game_name}"
            
            if isinstance(channel, discord.ForumChannel):
                await channel.create_thread(name=f"🎮 {game_name}", content=content)
            else:
                await channel.send(content)

@bot.event
async def on_voice_state_update(member, before, after):
    if member.id == bot.user.id and before.channel and not after.channel:
        if GLOBAL_SETTINGS["voice_guard"]:
            await asyncio.sleep(5)
            await safe_join()

@bot.event
async def on_ready():
    print(f'--- Midnight {GLOBAL_SETTINGS["version"]} READY ---')
    await bot.tree.sync()
    asyncio.create_task(safe_join())

if __name__ == "__main__":
    keep_alive()
    bot.run("MTQ5MjY2MjU5NzM1NzQwNDIxMQ.GNy4wE.3L7h8eWVa2ZLCQwmKwikaBTPuvOm6denfCRcMI")
