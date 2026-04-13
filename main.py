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

# Налаштування модулів (True = Увімкнено)
CONFIG = {
    "voice_active": True,
    "forum_active": True,
    "monitoring_active": True
}

VOICE_ID = 1458906259922354277 
GAMING_LOG_ID = 1493054931224105070 

# --- 3. ЛОГІКА ГОЛОСУ ---
async def safe_join():
    if not CONFIG["voice_active"]: return
    try:
        await bot.wait_until_ready()
        channel = bot.get_channel(VOICE_ID)
        if not channel: return
        
        vc = discord.utils.get(bot.voice_clients, guild=channel.guild)
        if not vc or not vc.is_connected():
            await channel.connect(reconnect=True)
            print(f"[+] MIDNIGHT зайшов у голос")
    except Exception as e:
        print(f"[-] Помилка голосу: {e}")

# --- 4. КОМАНДИ КЕРУВАННЯ ---

@bot.tree.command(name="status", description="Панель керування Midnight")
async def status(interaction: discord.Interaction):
    embed = discord.Embed(title="🌑 Midnight Control Center", color=0x2b2d31)
    
    # Формуємо статус модулів
    v_status = "✅ АКТИВНО" if CONFIG["voice_active"] else "❌ ВИМКНЕНО"
    f_status = "✅ АКТИВНО" if CONFIG["forum_active"] else "❌ ВИМКНЕНО"
    m_status = "✅ АКТИВНО" if CONFIG["monitoring_active"] else "❌ ВИМКНЕНО"

    embed.add_field(name="🎙️ Авто-Голос", value=v_status, inline=True)
    embed.add_field(name="📂 Форум-Лог", value=f_status, inline=True)
    embed.add_field(name="📡 Моніторинг", value=m_status, inline=True)
    
    embed.set_footer(text="Використовуйте /toggle для налаштування")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="toggle_voice", description="Вкл/Викл авто-вхід у голос")
async def toggle_voice(interaction: discord.Interaction):
    CONFIG["voice_active"] = not CONFIG["voice_active"]
    state = "увімкнено" if CONFIG["voice_active"] else "вимкнено"
    
    if not CONFIG["voice_active"]:
        for vc in bot.voice_clients: await vc.disconnect()
        
    await interaction.response.send_message(f"🎙️ Модуль голосу **{state}**.")

@bot.tree.command(name="toggle_forum", description="Вкл/Викл логування ігор")
async def toggle_forum(interaction: discord.Interaction):
    CONFIG["forum_active"] = not CONFIG["forum_active"]
    state = "увімкнено" if CONFIG["forum_active"] else "вимкнено"
    await interaction.response.send_message(f"📂 Модуль форуму **{state}**.")

@bot.tree.command(name="help", description="Список усіх команд")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="📜 Команди Midnight", color=0x3498db)
    commands_list = (
        "**/status** - Стан системи та модулів\n"
        "**/toggle_voice** - Керування авто-входом у войс\n"
        "**/toggle_forum** - Керування створенням гілок\n"
        "**/help** - Це повідомлення"
    )
    embed.description = commands_list
    await interaction.response.send_message(embed=embed)

# --- 5. ПОДІЇ ---

@bot.event
async def on_presence_update(before, after):
    if not CONFIG["forum_active"]: return
    if before.activity == after.activity: return
    
    if after.activity and after.activity.type == discord.ActivityType.playing:
        game_name = after.activity.name
        channel = bot.get_channel(GAMING_LOG_ID)
        
        players = [m.display_name for m in after.guild.members 
                   if m.id != after.id and any(act.name == game_name for act in m.activities if act.type == discord.ActivityType.playing)]
        
        if players:
            greetings = ["Нова катка!", "Паті збирається!", "Вдалого полювання!"]
            content = f"🎮 **{random.choice(greetings)}**\nГравці: {', '.join(players + [after.display_name])}\nГра: **{game_name}**"
            
            if isinstance(channel, discord.ForumChannel):
                await channel.create_thread(name=f"🎮 {game_name}", content=content)
            else:
                await channel.send(content)

@bot.event
async def on_voice_state_update(member, before, after):
    if member.id == bot.user.id and before.channel and not after.channel and CONFIG["voice_active"]:
        await asyncio.sleep(5)
        await safe_join()

@bot.event
async def on_ready():
    print(f'[+] {bot.user.name} Онлайн!')
    await bot.tree.sync()
    asyncio.create_task(safe_join())

if __name__ == "__main__":
    keep_alive()
    bot.run("MTQ5MjY2MjU5NzM1NzQwNDIxMQ.GNy4wE.3L7h8eWVa2ZLCQwmKwikaBTPuvOm6denfCRcMI")
