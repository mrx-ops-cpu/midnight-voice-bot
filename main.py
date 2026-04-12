import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
import os
import asyncio

# 1. Веб-сервер (щоб Railway не "гасив" бота)
app = Flask('')

@app.route('/')
def home():
    return "MIDNIGHT BOT IS ONLINE"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# 2. Налаштування
intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.message_content = True 

bot = commands.Bot(command_prefix='!', intents=intents)

# ID твого каналу
VOICE_ID = 1458906259922354277 

async def safe_join():
    """Функція безпечного входу з перевірками"""
    await bot.wait_until_ready()
    channel = bot.get_channel(VOICE_ID)
    
    if not channel:
        print(f"[-] Канал {VOICE_ID} не знайдено. Перевір ID!")
        return

    # Перевіряємо, чи ми вже не підключені до цього сервера
    voice = discord.utils.get(bot.voice_clients, guild=channel.guild)
    
    if voice and voice.is_connected():
        print(f"[!] Бот уже в каналі {channel.name}, повторний вхід не потрібен.")
        return

    try:
        print(f"[*] Спроба зайти в канал {channel.name}...")
        await channel.connect(timeout=20.0, reconnect=True)
        print(f"[+] Успішно підключено!")
    except Exception as e:
        print(f"[-] Помилка при вході: {e}")

@bot.event
async def on_ready():
    print(f'[+] Бот авторизований як: {bot.user.name}')
    # Запускаємо вхід як окрему задачу, щоб не блокувати бота
    bot.loop.create_task(safe_join())

@bot.event
async def on_voice_state_update(member, before, after):
    # Якщо хтось (або помилка) викинули саме нашого бота
    if member.id == bot.user.id and before.channel is not None and after.channel is None:
        print("[!] Мене від'єднали! Чекаю 10 секунд для безпеки...")
        await asyncio.sleep(10)
        await safe_join()

# Запуск
keep_alive()

TOKEN = os.getenv("TOKEN") or "MTQ5MjY2MjU5NzM1NzQwNDIxMQ.GuWdHO.unpINiO1sHTWInyRrD83P2Dj4elDf-e0d9g1Fw"

try:
    bot.run(TOKEN)
except discord.errors.HTTPException as e:
    if e.status == 429:
        print("!!! КРИТИЧНО: Discord заблокував IP (Rate Limit). ВИМКНИ БОТА НА 30 ХВИЛИН !!!")
    else:
        print(f"Помилка HTTP: {e}")
