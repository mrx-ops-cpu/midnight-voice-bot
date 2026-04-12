import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
import os
import asyncio

# 1. Веб-сервер (Railway потребує прив'язки до динамічного порту)
app = Flask('')

@app.route('/')
def home():
    return "MIDNIGHT BOT IS ONLINE"

def run():
    # Railway передає порт через змінну оточення PORT
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True # Потік завершиться разом із програмою
    t.start()

# 2. Налаштування бота
intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.message_content = True 

bot = commands.Bot(command_prefix='!', intents=intents)

# Твій ID каналу
VOICE_ID = 1458906259922354277 

async def safe_join():
    """Безпечне підключення до каналу"""
    await bot.wait_until_ready()
    channel = bot.get_channel(VOICE_ID)
    
    if not channel:
        print(f"[-] Помилка: Канал {VOICE_ID} не знайдено.")
        return

    # Перевірка: чи бот уже підключений
    voice = discord.utils.get(bot.voice_clients, guild=channel.guild)
    if voice and voice.is_connected():
        print(f"[!] Бот уже в каналі {channel.name}.")
        return

    try:
        print(f"[*] Намагаюся зайти в {channel.name}...")
        await channel.connect(timeout=20.0, reconnect=True)
        print(f"[+] Успішно! Бот у войсі.")
    except Exception as e:
        print(f"[-] Не вдалося зайти: {e}")

@bot.event
async def on_ready():
    print(f'[+] Авторизовано як: {bot.user.name}')
    # Створюємо задачу на вхід окремо від основного потоку
    bot.loop.create_task(safe_join())

@bot.event
async def on_voice_state_update(member, before, after):
    # Якщо нашого бота вигнали з каналу
    if member.id == bot.user.id and before.channel is not None and after.channel is None:
        print("[!] Мене кікнули! Почекаю 10 секунд і повернуся...")
        await asyncio.sleep(10)
        await safe_join()

# 3. Запуск
if __name__ == "__main__":
    keep_alive()
    
    # Пріоритет на TOKEN із налаштувань Railway
    TOKEN = os.getenv("TOKEN") or "MTQ5MjY2MjU5NzM1NzQwNDIxMQ.GuWdHO.unpINiO1sHTWInyRrD83P2Dj4elDf-e0d9g1Fw"
    
    try:
        bot.run(TOKEN)
    except discord.errors.HTTPException as e:
        if e.status == 429:
            print("!!! КРИТИЧНО: Discord заблокував IP (Rate Limit). ТРЕБА ПАУЗА 30 ХВИЛИН !!!")
        else:
            print(f"[-] Помилка Discord: {e}")
