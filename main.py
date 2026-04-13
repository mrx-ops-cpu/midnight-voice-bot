import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
import os
import asyncio
import random

# --- 1. ВЕБ-СЕРВЕР ДЛЯ ПІДТРИМКИ ОНЛАЙНУ ---
app = Flask('')
@app.route('/')
def home(): return "MIDNIGHT SYSTEM ONLINE"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run, daemon=True); t.start()

# --- 2. НАЛАШТУВАННЯ БОТА ---
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# Твої ID
VOICE_ID = 1458906259922354277 
GAMING_LOG_ID = 1493054931224105070 

# --- 3. ФУНКЦІЯ АВТО-ПІДКЛЮЧЕННЯ В ГОЛОС ---
async def safe_join():
    try:
        await bot.wait_until_ready()
        await asyncio.sleep(5) # Пауза для стабілізації з'єднання Railway
        
        channel = bot.get_channel(VOICE_ID)
        if not channel:
            print(f"[-] Канал {VOICE_ID} не знайдено!")
            return

        # Перевіряємо, чи ми вже в каналі
        guild = channel.guild
        vc = discord.utils.get(bot.voice_clients, guild=guild)

        if vc and vc.is_connected():
            if vc.channel.id == VOICE_ID:
                return # Вже на місці
            await vc.disconnect(force=True)

        await channel.connect(reconnect=True, timeout=30)
        print(f"[+] MIDNIGHT зайняв пост у каналі: {channel.name}")
    except Exception as e:
        print(f"[-] Помилка авто-входу: {e}")

# --- 4. МОНІТОРИНГ ІГОР ТА ФОРУМ ---
@bot.event
async def on_presence_update(before, after):
    if before.activity == after.activity: return
    
    if after.activity and after.activity.type == discord.ActivityType.playing:
        game_name = after.activity.name
        channel = bot.get_channel(GAMING_LOG_ID)
        if not channel: return
        
        players = [m.display_name for m in after.guild.members 
                   if m.id != after.id and any(act.name == game_name for act in m.activities if act.type == discord.ActivityType.playing)]
        
        # Створюємо лог, якщо в гру грає більше однієї людини
        if players:
            greetings = ["Нова катка!", "Паті збирається!", "Виявлено активність!", "Вдалого полювання!"]
            content = f"🎮 **{random.choice(greetings)}**\nГравці: {', '.join(players + [after.display_name])}\nГра: **{game_name}**"
            
            if isinstance(channel, discord.ForumChannel):
                await channel.create_thread(name=f"🎮 {game_name}", content=content)
            else:
                await channel.send(content)

# --- 5. КОНТРОЛЬ ПРИСУТНОСТІ В ГОЛОСІ ---
@bot.event
async def on_voice_state_update(member, before, after):
    # Якщо хтось вимкнув бота або він сам вилетів
    if member.id == bot.user.id and before.channel and not after.channel:
        print("[!] Бот був відключений. Повертаюсь на пост через 5 секунд...")
        await asyncio.sleep(5)
        await safe_join()

# --- 6. СТАРТ ТА КОМАНДИ ---
@bot.tree.command(name="status", description="Статус систем Midnight")
async def status(interaction: discord.Interaction):
    embed = discord.Embed(title="🌑 Midnight Control Panel", color=0x2f3136)
    embed.add_field(name="🌐 Мережа", value="✅ Online", inline=True)
    embed.add_field(name="🎮 Форум", value="✅ Active", inline=True)
    embed.add_field(name="🎙️ Голос", value="✅ Connected", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.event
async def on_ready():
    print(f'[+] {bot.user.name} активований!')
    await bot.tree.sync()
    asyncio.create_task(safe_join())

if __name__ == "__main__":
    keep_alive()
    bot.run("MTQ5MjY2MjU5NzM1NzQwNDIxMQ.GNy4wE.3L7h8eWVa2ZLCQwmKwikaBTPuvOm6denfCRcMI")
