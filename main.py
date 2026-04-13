import discord
from discord.ext import commands
from discord import app_commands
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
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# 2. Налаштування (Intents)
intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.message_content = True 
intents.presences = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# --- ГЛОБАЛЬНІ ЗМІННІ ТА ID ---
VOICE_ID = 1458906259922354277 
GAMING_LOG_ID = 1493042941709783170 
gaming_stats_enabled = True  # Статус системи ігор

async def safe_join():
    """Логіка входу в голосовий канал з паузою для стабілізації"""
    await bot.wait_until_ready()
    await asyncio.sleep(5)
    channel = bot.get_channel(VOICE_ID)
    if not channel: return
    
    voice = discord.utils.get(bot.voice_clients, guild=channel.guild)
    if voice and voice.is_connected(): return
    
    try:
        await channel.connect(timeout=20.0, reconnect=True, self_deaf=True)
        print(f"[+] Бот успішно закріпився у войсі.")
    except Exception as e: 
        print(f"[-] Помилка входу: {e}")

# --- СЛЕШ-КОМАНДИ ---

@bot.tree.command(name="midnight_info", description="Показати функціонал та статус бота")
async def midnight_info(interaction: discord.Interaction):
    """Красива картка з інформацією про бота"""
    status_emoji = "🟢 Увімкнено" if gaming_stats_enabled else "🔴 Вимкнено"
    
    embed = discord.Embed(
        title="🌑 Midnight Bot | System Info",
        description="Твій автономний помічник на сервері Midnight.",
        color=discord.Color.dark_gray()
    )
    
    embed.add_field(
        name="🎮 Моніторинг ігор", 
        value=f"Сповіщає про збори на катку.\n**Статус:** {status_emoji}", 
        inline=False
    )
    
    embed.add_field(
        name="🎙️ Voice Guardian", 
        value="Цілодобова присутність у голосовому каналі.", 
        inline=False
    )
    
    embed.add_field(
        name="🛠️ Керування", 
        value="`/gaming_status` — змінити статус моніторингу.\n`/midnight_ping` — затримка мережі.", 
        inline=False
    )
    
    embed.set_footer(text=f"Midnight Bot v1.5 | Стан: Стабільний")
    if bot.user.avatar:
        embed.set_thumbnail(url=bot.user.avatar.url)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="gaming_status", description="Увімкнути/вимкнути сповіщення про ігри")
@app_commands.describe(status="True - увімкнути, False - вимкнути")
async def gaming_status(interaction: discord.Interaction, status: bool):
    """Команда для ввімкнення/вимкнення сповіщень"""
    global gaming_stats_enabled
    gaming_stats_enabled = status
    state = "✅ УВІМКНЕНО" if status else "❌ ВИМКНЕНО"
    await interaction.response.send_message(f"🌑 **Midnight System**\nМоніторинг ігор тепер: **{state}**")

@bot.tree.command(name="midnight_ping", description="Перевірка затримки бота")
async def midnight_ping(interaction: discord.Interaction):
    ping_ms = round(bot.latency * 1000)
    await interaction.response.send_message(f"🌑 **Midnight Bot**\n📡 **Затримка:** {ping_ms}мс")

# --- СИСТЕМА МОНІТОРИНГУ ІГОР ---
@bot.event
async def on_presence_update(before, after):
    # Якщо функцію вимкнено через команду — ігноруємо
    if not gaming_stats_enabled:
        return

    # Перевіряємо тільки зміну гри
    if before.activity == after.activity:
        return

    # Якщо хтось запустив гру
    if after.activity and after.activity.type == discord.ActivityType.playing:
        game_name = after.activity.name
        guild = after.guild
        channel = bot.get_channel(GAMING_LOG_ID)
        
        if not channel: return

        # Шукаємо інших гравців у цю ж гру
        players_in_game = []
        for member in guild.members:
            if member.id != after.id:
                for act in member.activities:
                    if act.type == discord.ActivityType.playing and act.name == game_name:
                        players_in_game.append(member.display_name)
        
        # Якщо паті знайдено (мінімум 2 людини)
        if len(players_in_game) > 0:
            all_players = players_in_game + [after.display_name]
            names_list = ", ".join(all_players)
            
            msg = f"🎮 **Збір на катку!**\nБачу, що **{names_list}** зараз у **{game_name}**.\nМоже, зберете повне паті? 🔥"
            await channel.send(msg)

# --- СИСТЕМНІ ПОДІЇ ---
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
    """Перепідключення, якщо бота викинуло з войсу"""
    if member.id == bot.user.id and before.channel and not after.channel:
        await asyncio.sleep(10)
        await safe_join()

# 3. Запуск
if __name__ == "__main__":
    keep_alive()
    # TOKEN береться з секретів Railway або вставляється сюди
    TOKEN = os.getenv("TOKEN") or "MTQ5MjY2MjU5NzM1NzQwNDIxMQ.GuWdHO.unpINiO1sHTWInyRrD83P2Dj4elDf-e0d9g1Fw"
    bot.run(TOKEN)
