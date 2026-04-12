import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
import os
import asyncio

# 1. Веб-сервер для Railway
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

# ID твого каналу (той самий, що був у тебе)
VOICE_ID = 1458906259922354277 

@bot.event
async def on_ready():
    print(f'Авторизовано як: {bot.user.name}')
    await join_voice()

async def join_voice():
    """Функція для входу в канал"""
    channel = bot.get_channel(VOICE_ID)
    if channel:
        # Перевіряємо, чи ми вже не там
        voice_client = discord.utils.get(bot.voice_clients, guild=channel.guild)
        if not voice_client:
            await channel.connect()
            print(f'Бот зайшов у канал: {channel.name}')

@bot.event
async def on_voice_state_update(member, before, after):
    # Якщо цей "member" — наш бот
    if member.id == bot.user.id:
        # Якщо канал "після" порожній, значить бота від'єднали
        if after.channel is None:
            print("Мене кікнули! Повертаюся назад...")
            await asyncio.sleep(1) # Невелика пауза, щоб Discord встиг оновити статус
            await join_voice()

# Запуск
keep_alive()

# Використовуй токен зі змінних оточення або встав свій
TOKEN = os.getenv("TOKEN") or "MTQ5MjY2MjU5NzM1NzQwNDIxMQ.GuWdHO.unpINiO1sHTWInyRrD83P2Dj4elDf-e0d9g1Fw"
bot.run(TOKEN)
