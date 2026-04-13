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

# --- 2. НАЛАШТУВАННЯ ТА ПРАПОРЦІ ---
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# Глобальні статуси
CONFIG = {
    "monitoring": True,
    "voice": True,
    "version": "v1.8",
    "image_url": "https://i.imgur.com/Ваша_Картинка.png" # Заміни на реальне посилання
}

VOICE_ID = 1458906259922354277 
GAMING_LOG_ID = 1493054931224105070 

# --- 3. ЛОГІКА ГОЛОСУ ---
async def safe_join():
    if not CONFIG["voice"]: return
    try:
        await bot.wait_until_ready()
        channel = bot.get_channel(VOICE_ID)
        if not channel: return
        
        vc = discord.utils.get(bot.voice_clients, guild=channel.guild)
        if not vc or not vc.is_connected():
            await channel.connect(reconnect=True)
    except Exception as e:
        print(f"[-] Помилка голосу: {e}")

# --- 4. КОМАНДИ (STYLISH) ---

@bot.tree.command(name="midnight_info", description="Системна інформація бота")
async def midnight_info(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🌑 Midnight Bot | System Info",
        description="Твій автономний помічник на сервері Midnight.",
        color=0x2b2d31
    )
    
    # Моніторинг ігор
    m_emoji = "🟢 Увімкнено" if CONFIG["monitoring"] else "🔴 Вимкнено"
    embed.add_field(
        name="🎮 Моніторинг ігор",
        value=f"Сповіщає про збори на катку.\n**Статус:** {m_emoji}",
        inline=False
    )
    
    # Voice Guardian
    v_emoji = "🟢 Активний" if CONFIG["voice"] else "🔴 Неактивний"
    embed.add_field(
        name="🎙️ Voice Guardian",
        value=f"Цілодобова присутність у голосовому каналі.\n**Статус:** {v_emoji}",
        inline=False
    )
    
    # Керування
    embed.add_field(
        name="🛠️ Керування",
        value=(
            "`/gaming_status` — змінити статус моніторингу.\n"
            "`/voice_status` — змінити статус присутності.\n"
            "`/midnight_ping` — затримка мережі."
        ),
        inline=False
    )
    
    embed.set_thumbnail(url=CONFIG["image_url"])
    embed.set_footer(text=f"Midnight Bot {CONFIG['version']} | Стан: Стабільний")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="gaming_status", description="Увімкнути/Вимкнути моніторинг")
async def gaming_status(interaction: discord.Interaction):
    CONFIG["monitoring"] = not CONFIG["monitoring"]
    state = "активовано" if CONFIG["monitoring"] else "деактивовано"
    await interaction.response.send_message(f"✅ Моніторинг ігор **{state}**.", ephemeral=True)

@bot.tree.command(name="voice_status", description="Увімкнути/Вимкнути присутність у войсі")
async def voice_status(interaction: discord.Interaction):
    CONFIG["voice"] = not CONFIG["voice"]
    if not CONFIG["voice"]:
        for vc in bot.voice_clients: await vc.disconnect()
    else:
        await safe_join()
    await interaction.response.send_message(f"✅ Voice Guardian **{'увімкнено' if CONFIG['voice'] else 'вимкнено'}**.", ephemeral=True)

@bot.tree.command(name="midnight_ping", description="Перевірити пінг")
async def midnight_ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"📡 Затримка мережі: **{round(bot.latency * 1000)}ms**", ephemeral=True)

# --- 5. ПОДІЇ ---

@bot.event
async def on_presence_update(before, after):
    if not CONFIG["monitoring"]: return
    if before.activity == after.activity: return
    
    if after.activity and after.activity.type == discord.ActivityType.playing:
        game_name = after.activity.name
        channel = bot.get_channel(GAMING_LOG_ID)
        
        players = [m.display_name for m in after.guild.members 
                   if m.id != after.id and any(act.name == game_name for act in m.activities if act.type == discord.ActivityType.playing)]
        
        if players:
            all_players = players + [after.display_name]
            content = f"🎮 **Виявлено активність у {game_name}!**\n**Гравці:** {', '.join(all_players)}"
            
            if isinstance(channel, discord.ForumChannel):
                await channel.create_thread(name=f"🎮 {game_name}", content=content)
            else:
                await channel.send(content)

@bot.event
async def on_voice_state_update(member, before, after):
    if member.id == bot.user.id and before.channel and not after.channel and CONFIG["voice"]:
        await asyncio.sleep(5)
        await safe_join()

@bot.event
async def on_ready():
    print(f'[+] Midnight {CONFIG["version"]} завантажено!')
    await bot.tree.sync()
    asyncio.create_task(safe_join())

if __name__ == "__main__":
    keep_alive()
    bot.run("ТВІЙ_ТОКЕН")
