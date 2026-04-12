import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask
from threading import Thread
import os
import asyncio

# 1. Веб-сервер
app = Flask('')

@app.route('/')
def home():
    return "MIDNIGHT BOT IS ONLINE"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# 2. Налаштування
intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.message_content = True 

bot = commands.Bot(command_prefix='!', intents=intents)

VOICE_ID = 1458906259922354277 

async def safe_join():
    await bot.wait_until_ready()
    channel = bot.get_channel(VOICE_ID)
    if not channel: return
    voice = discord.utils.get(bot.voice_clients, guild=channel.guild)
    if voice and voice.is_connected(): return
    try:
        await channel.connect(timeout=20.0, reconnect=True)
    except Exception as e: print(f"Error: {e}")

# Оновлена команда (без зайвого тексту)
@bot.tree.command(name="midnight_ping", description="Перевірка затримки бота")
async def midnight_ping(interaction: discord.Interaction):
    ping_ms = round(bot.latency * 1000)
    await interaction.response.send_message(f"🌑 **Midnight Bot**\n📡 **Затримка:** {ping_ms}мс")

@bot.event
async def on_ready():
    print(f'[+] Авторизовано як: {bot.user.name}')
    try:
        await bot.tree.sync()
        print("[+] Команди синхронізовано.")
    except Exception as e: print(f"Sync Error: {e}")
    bot.loop.create_task(safe_join())

@bot.event
async def on_voice_state_update(member, before, after):
    if member.id == bot.user.id and before.channel and not after.channel:
        await asyncio.sleep(10)
        await safe_join()

if __name__ == "__main__":
    keep_alive()
    TOKEN = os.getenv("TOKEN") or "MTQ5MjY2MjU5NzM1NzQwNDIxMQ.GuWdHO.unpINiO1sHTWInyRrD83P2Dj4elDf-e0d9g1Fw"
    bot.run(TOKEN)
