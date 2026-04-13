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

# --- 2. ГОЛОВНІ НАЛАШТУВАННЯ (TRUE/FALSE) ---
# Змінюй ці значення тут, щоб увімкнути/вимкнути функції за замовчуванням
GLOBAL_SETTINGS = {
    "monitoring": True,   # Моніторинг ігор та створення гілок у форумі
    "voice_guard": True,  # Цілодобове перебування у голосовому каналі
    "auto_reconnect": True # Автоматичне повернення, якщо бота вигнали
}

BOT_VERSION = "v1.9"
# Сюди встав посилання на картинку MN (з Discord або хостингу)
IMAGE_URL = "https://i.imgur.com/Ваша_Картинка.png" 

VOICE_ID = 1458906259922354277 
GAMING_LOG_ID = 1493054931224105070 

# --- 3. ІНІЦІАЛІЗАЦІЯ БОТА ---
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# --- 4. ЛОГІКА ГОЛОСУ ---
async def safe_join():
    if not GLOBAL_SETTINGS["voice_guard"]: return
    try:
        await bot.wait_until_ready()
        channel = bot.get_channel(VOICE_ID)
        if not channel: return
        
        # Перевірка поточного підключення
        vc = discord.utils.get(bot.voice_clients, guild=channel.guild)
        if not vc or not vc.is_connected():
            await channel.connect(reconnect=True, timeout=20)
            print(f"[+] Midnight зайшов у канал")
    except Exception as e:
        print(f"[-] Помилка входу: {e}")

# --- 5. СТИЛЬНІ СЛЕШ-КОМАНДИ ---

@bot.tree.command(name="midnight_info", description="Показати статус систем")
async def midnight_info(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🌑 Midnight Bot | System Info",
        description="Твій автономний помічник на сервері Midnight.",
        color=0x2b2d31
    )
    
    # Стан моніторингу
    m_status = "🟢 Увімкнено" if GLOBAL_SETTINGS["monitoring"] else "🔴 Вимкнено"
    embed.add_field(
        name="🎮 Моніторинг ігор",
        value=f"Сповіщає про збори на катку.\n**Статус:** {m_status}",
        inline=False
    )
    
    # Стан Voice Guardian
    v_status = "🟢 Активний" if GLOBAL_SETTINGS["voice_guard"] else "🔴 Неактивний"
    embed.add_field(
        name="🎙️ Voice Guardian",
        value=f"Цілодобова присутність у голосовому каналі.\n**Статус:** {v_status}",
        inline=False
    )
    
    embed.add_field(
        name="🛠️ Керування (Перемикачі)",
        value="`/toggle_monitoring` — змінити стан ігор\n`/toggle_voice` — змінити стан войсу",
        inline=False
    )
    
    if IMAGE_URL.startswith("http"):
        embed.set_thumbnail(url=IMAGE_URL)
        
    embed.set_footer(text=f"Midnight Bot {BOT_VERSION} | Стан: Стабільний")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="toggle_monitoring", description="Увімкнути/Вимкнути лог ігор")
async def toggle_monitoring(interaction: discord.Interaction):
    GLOBAL_SETTINGS["monitoring"] = not GLOBAL_SETTINGS["monitoring"]
    state = "УВІМКНЕНО" if GLOBAL_SETTINGS["monitoring"] else "ВИМКНЕНО"
    await interaction.response.send_message(f"📡 Модуль моніторингу тепер **{state}**.", ephemeral=True)

@bot.tree.command(name="toggle_voice", description="Увімкнути/Вимкнути Voice Guardian")
async def toggle_voice(interaction: discord.Interaction):
    GLOBAL_SETTINGS["voice_guard"] = not GLOBAL_SETTINGS["voice_guard"]
    state = "АКТИВОВАНО" if GLOBAL_SETTINGS["voice_guard"] else "ДЕАКТИВОВАНО"
    
    if not GLOBAL_SETTINGS["voice_guard"]:
        for vc in bot.voice_clients: await vc.disconnect(force=True)
    else:
        await safe_join()
        
    await interaction.response.send_message(f"🎙️ Voice Guardian тепер **{state}**.", ephemeral=True)

# --- 6. ОБРОБКА ПОДІЙ ---

@bot.event
async def on_presence_update(before, after):
    if not GLOBAL_SETTINGS["monitoring"]: return
    if before.activity == after.activity: return
    
    if after.activity and after.activity.type == discord.ActivityType.playing:
        game_name = after.activity.name
        channel = bot.get_channel(GAMING_LOG_ID)
        
        # Логіка паті: шукаємо інших гравців у ту саму гру
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
    # Якщо бота вибили, а Voice Guardian увімкнено — повертаємося
    if member.id == bot.user.id and before.channel and not after.channel:
        if GLOBAL_SETTINGS["voice_guard"] and GLOBAL_SETTINGS["auto_reconnect"]:
            print("[!] Виявлено відключення. Перезапуск Voice Guardian...")
            await asyncio.sleep(5)
            await safe_join()

@bot.event
async def on_ready():
    print(f'--- MIDNIGHT SYSTEM {BOT_VERSION} ---')
    print(f'[+] Бот: {bot.user.name}')
    print(f'[+] Моніторинг: {GLOBAL_SETTINGS["monitoring"]}')
    print(f'[+] Voice Guardian: {GLOBAL_SETTINGS["voice_guard"]}')
    await bot.tree.sync()
    asyncio.create_task(safe_join())

if __name__ == "__main__":
    keep_alive()
    # Встав свій токен нижче
    bot.run("MTQ5MjY2MjU5NzM1NzQwNDIxMQ.GNy4wE.3L7h8eWVa2ZLCQwmKwikaBTPuvOm6denfCRcMI")
