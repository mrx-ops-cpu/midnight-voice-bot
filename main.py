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
    "version": "v2.7",
    "image_url": "https://cdn.discordapp.com/avatars/1492662597357404211/a_4bf48afaac3798695e46c007ce568803.gif?size=1024"
}

active_sessions = {}
pending_announcements = set() 

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
    embed.add_field(name="🎮 Моніторинг ігор", value=f"Статус: {m_status}\n(Анонс від 3-х гравців)", inline=False)
    embed.add_field(name="🎙️ Voice Guardian", value=f"Статус: {v_status}", inline=False)
    embed.add_field(name="🛠️ Керування", value="`/set_monitoring`, `/set_voice`, `/midnight_ping`", inline=False)
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

# --- 5. МОНІТОРИНГ (ВІД 3 ГРАВЦІВ) ---

async def announce_game(guild_id, game_name):
    await asyncio.sleep(30) # Затримка 30 секунд
    
    guild = bot.get_guild(guild_id)
    if not guild: 
        pending_announcements.discard(game_name)
        return

    # Збираємо гравців на момент закінчення 30-секундної паузи
    current_players = [m for m in guild.members 
                       if m.activity and m.activity.type == discord.ActivityType.playing and m.activity.name == game_name]
    
    # ТУТ ЗМІНЕНО: тепер мінімум 3 гравці
    if len(current_players) >= 3:
        active_sessions[game_name] = [m.id for m in current_players]
        channel = bot.get_channel(GAMING_LOG_ID)
        
        if channel:
            names = [m.display_name for m in current_players]
            greetings = ["О, вже збирається потужне паті!", "Бачу, намічається серйозна катка!", "Вдалого полювання, команда!"]
            content = f"🎮 **{random.choice(greetings)}**\n**Гравці:** {', '.join(names)}\n**Гра:** {game_name}"
            
            try:
                if isinstance(channel, discord.ForumChannel):
                    await channel.create_thread(name=f"🎮 {game_name}", content=content)
                else:
                    await channel.send(content)
            except Exception as e:
                print(f"Error: {e}")
    
    pending_announcements.discard(game_name)

@bot.event
async def on_presence_update(before, after):
    if not GLOBAL_SETTINGS["monitoring"]: return
    
    is_playing = after.activity and after.activity.type == discord.ActivityType.playing
    was_playing = before.activity and before.activity.type == discord.ActivityType.playing
    
    if is_playing and not was_playing:
        game_name = after.activity.name
        
        if game_name in pending_announcements:
            return

        if game_name in active_sessions:
            still_online = [p_id for p_id in active_sessions[game_name] 
                            if (m := after.guild.get_member(p_id)) and m.activity and m.activity.name == game_name]
            if still_online:
                active_sessions[game_name] = still_online
                return
            else:
                del active_sessions[game_name]

        pending_announcements.add(game_name)
        asyncio.create_task(announce_game(after.guild.id, game_name))

@bot.event
async def on_voice_state_update(member, before, after):
    if member.id == bot.user.id and before.channel and not after.channel:
        if GLOBAL_SETTINGS["voice_guard"]:
            await asyncio.sleep(5)
            await safe_join()

@bot.event
async def on_ready():
    print(f'--- Midnight {GLOBAL_SETTINGS["version"]} | Min Players: 3 | 30s Delay ---')
    await bot.tree.sync()
    asyncio.create_task(safe_join())

if __name__ == "__main__":
    keep_alive()
    bot.run("MTQ5MjY2MjU5NzM1NzQwNDIxMQ.GNy4wE.3L7h8eWVa2ZLCQwmKwikaBTPuvOm6denfCRcMI")
