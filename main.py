import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
import os
import asyncio
import random

# --- ВЕБ-СЕРВЕР ---
app = Flask('')
@app.route('/')
def home(): return "MIDNIGHT SYSTEM IS READY"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run, daemon=True); t.start()

# --- КОНФІГУРАЦІЯ БОТА ---
intents = discord.Intents.default()
intents.voice_states = True 
intents.guilds = True
intents.message_content = True 
intents.presences = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Твої налаштування
VOICE_ID = 1458906259922354277 
GAMING_LOG_ID = 1493054931224105070 
voice_welcome_enabled = True

# --- ЛОГІКА ГОЛОСУ ---
async def safe_join():
    try:
        await bot.wait_until_ready()
        await asyncio.sleep(5) # Пауза для стабілізації мережі
        channel = bot.get_channel(VOICE_ID)
        if not channel: return

        for vc in bot.voice_clients:
            await vc.disconnect(force=True)
        
        await asyncio.sleep(2)
        await channel.connect(reconnect=True)
        print(f"[+] Бот зайняв позицію у каналі")
    except Exception as e:
        print(f"[-] Помилка підключення: {e}")

@bot.event
async def on_voice_state_update(member, before, after):
    # Авто-повернення бота
    if member.id == bot.user.id and before.channel and not after.channel:
        await asyncio.sleep(5)
        await safe_join()
        return

    # Привітання звуком
    if voice_welcome_enabled and after.channel and after.channel.id == VOICE_ID and member.id != bot.user.id:
        vc = discord.utils.get(bot.voice_clients, guild=member.guild)
        if vc and vc.is_connected():
            if os.path.exists("welcome.mp3"):
                try:
                    if vc.is_playing(): vc.stop()
                    # FFmpeg у Docker завжди доступний просто за назвою
                    vc.play(discord.FFmpegPCMAudio("welcome.mp3"))
                    print(f"[!] Звук відтворено для: {member.display_name}")
                except Exception as e:
                    print(f"[-] Помилка аудіо: {e}")

# --- МОНІТОРИНГ ІГОР ---
@bot.event
async def on_presence_update(before, after):
    if before.activity == after.activity: return
    if after.activity and after.activity.type == discord.ActivityType.playing:
        game_name = after.activity.name
        channel = bot.get_channel(GAMING_LOG_ID)
        if not channel: return
        
        players = [m.display_name for m in after.guild.members 
                   if m.id != after.id and any(act.name == game_name for act in m.activities if act.type == discord.ActivityType.playing)]
        
        if players:
            content = f"🎮 **Нова катка!**\nГравці: {', '.join(players + [after.display_name])}\nГра: {game_name}"
            if isinstance(channel, discord.ForumChannel):
                await channel.create_thread(name=f"🎮 {game_name}", content=content)
            else:
                await channel.send(content)

@bot.event
async def on_ready():
    print(f'[+] {bot.user.name} Онлайн!')
    await bot.tree.sync()
    asyncio.create_task(safe_join())

if __name__ == "__main__":
    keep_alive()
    bot.run("MTQ5MjY2MjU5NzM1NzQwNDIxMQ.GNy4wE.3L7h8eWVa2ZLCQwmKwikaBTPuvOm6denfCRcMI")
