import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask
from threading import Thread
import os
import asyncio
import random

# 1. Веб-сервер для Railway
app = Flask('')
@app.route('/')
def home(): return "MIDNIGHT BOT IS ONLINE"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run); t.daemon = True; t.start()

# 2. Налаштування
intents = discord.Intents.default()
intents.voice_states = intents.guilds = intents.message_content = True 
intents.presences = intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# --- ГЛОБАЛЬНІ ЗМІННІ ---
VOICE_ID = 1458906259922354277 
GAMING_LOG_ID = 1493054931224105070 # Твій новий ID Форуму
gaming_stats_enabled = True

# --- СПИСОК ФРАЗ ДЛЯ ЖИВОГО СПІЛКУВАННЯ ---
GREETINGS = [
    "Бачу, тут намічається серйозна катка!",
    "Виявлено активність виживших у мережі.",
    "О, вже збирається непогане паті!",
    "Ніч стає цікавішою, коли є з ким пограти.",
    "Здається, хтось вирішив підкорити ладдер!",
    "Екіпаж готовий до вильоту?",
    "Сигнали Midnight Radar зафіксували рух!"
]

ADVICES = [
    "Може, зберете повне паті? 🔥",
    "Не забудьте зайти в голосовий канал! 🎙️",
    "Вдалого полювання! 🌑",
    "Покажіть їм, хто тут батя. 💪",
    "Час перемагати! 🏆",
    "Зв'язок у Midnight активовано."
]

async def safe_join():
    await bot.wait_until_ready()
    await asyncio.sleep(5)
    channel = bot.get_channel(VOICE_ID)
    if not channel: return
    voice = discord.utils.get(bot.voice_clients, guild=channel.guild)
    if voice and voice.is_connected(): return
    try:
        await channel.connect(timeout=20.0, reconnect=True, self_deaf=True)
        print("[+] Бот у войсі.")
    except Exception as e: print(f"Error: {e}")

# --- КОМАНДИ ---
@bot.tree.command(name="midnight_info", description="Функціонал та статус бота")
async def midnight_info(interaction: discord.Interaction):
    status_emoji = "🟢 Увімкнено" if gaming_stats_enabled else "🔴 Вимкнено"
    embed = discord.Embed(
        title="🌑 Midnight Bot | System Info", 
        description="Твій автономний помічник на сервері.",
        color=discord.Color.dark_gray()
    )
    embed.add_field(name="🎮 Форум «Хто в гру»", value=f"Статус моніторингу: {status_emoji}", inline=False)
    embed.add_field(name="🎙️ Voice Guardian", value="Бот цілодобово тримає зв'язок у войсі.", inline=False)
    embed.set_footer(text="Midnight Bot v1.7 | Developed for Midnight Server")
    if bot.user.avatar:
        embed.set_thumbnail(url=bot.user.avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="gaming_status", description="Увімкнути/вимкнути моніторинг ігор")
async def gaming_status(interaction: discord.Interaction, status: bool):
    global gaming_stats_enabled
    gaming_stats_enabled = status
    await interaction.response.send_message(f"🌑 Моніторинг ігор тепер: {'✅ Увімкнено' if status else '❌ Вимкнено'}")

# --- СИСТЕМА МОНІТОРИНГУ (ФОРУМ) ---
@bot.event
async def on_presence_update(before, after):
    if not gaming_stats_enabled or before.activity == after.activity:
        return

    if after.activity and after.activity.type
