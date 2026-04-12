import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
import os
import asyncio

# 1. Веб-сервер для Railway (щоб бот не засинав)
app = Flask('')

@app.route('/')
def home():
    return "MIDNIGHT BOT IS ONLINE"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# 2. Налаштування бота
intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True 

bot = commands.Bot(command_prefix='!', intents=intents)

# ID твого каналу
VOICE_ID = 1458906259922354277 

@bot.event
async def on_ready():
    print(f'Авторизовано як: {bot.user.name}')
    await join_voice()

async def join_voice():
    """Безпечна функція входу в канал з перевірками"""
    channel = bot.get_channel(VOICE_ID)
    if not channel:
        print(f"Помилка: Канал з ID {VOICE_ID} не знайдено.")
        return

    # Перевіряємо права бота на вхід
    permissions = channel.permissions_for(channel.guild.me)
    if not permissions.connect or not permissions.speak:
        print(f"Помилка: У бота немає прав на вхід або розмови в каналі {channel.name}!")
        return

    try:
        voice_client = discord.utils.get(bot.voice_clients, guild=channel.guild)
        if not voice_client:
            await channel.connect(timeout=20.0, reconnect=True)
            print(f'Бот успішно зайшов у канал: {channel.name}')
    except Exception as e:
        print(f"Не вдалося підключитися: {e}")

@bot.event
async def on_voice_state_update(member, before, after):
    # Якщо бот помітив, що він більше не в каналі
    if member.id == bot.user.id and after.channel is None:
        print("Мене від'єднали. Чекаю 10 секунд перед повторним входом...")
        
        # БЕЗПЕЧНА ЗАЙТРИМКА
        await asyncio.sleep(10) 
        
        await join_voice()

# Запуск веб-сервера
keep_alive()

# Токен (Railway автоматично підтягне його, якщо він є у Variables)
TOKEN = os.getenv("TOKEN") or "MTQ5MjY2MjU5NzM1NzQwNDIxMQ.GuWdHO.unpINiO1sHTWInyRrD83P2Dj4elDf-e0d9g1Fw"

try:
    bot.run(TOKEN)
except discord.errors.HTTPException as e:
    if e.status == 429:
        print("КРИТИЧНО: Discord заблокував запити (Rate Limit). Потрібно вимкнути бота на 30-60 хв!")
    else:
        raise e
