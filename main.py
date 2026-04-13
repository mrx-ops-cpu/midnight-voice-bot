import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask
from threading import Thread
import os
import asyncio
import random

# --- 1. ВЕБ-СЕРВЕР (Для стабільності на Railway) ---
app = Flask('')
@app.route('/')
def home(): return "MIDNIGHT BOT IS ONLINE"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run); t.daemon = True; t.start()

# --- 2. НАЛАШТУВАННЯ БОТА ---
intents = discord.Intents.default()
intents.voice_states = intents.guilds = intents.message_content = True 
intents.presences = intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Глобальні змінні
VOICE_ID = 1458906259922354277 
GAMING_LOG_ID = 1493054931224105070 
gaming_stats_enabled = True

GREETINGS = ["Бачу, тут намічається серйозна катка!", "Виявлено активність у мережі.", "О, вже збирається непогане паті!"]
ADVICES = ["Може, зберете повне паті? 🔥", "Не забудьте зайти в голосовий канал! 🎙️", "Вдалого полювання! 🌑"]

# --- ПЕРЕВІРКА ГОЛОСОВОГО КАНАЛУ ---
async def safe_join():
    try:
        await bot.wait_until_ready()
        await asyncio.sleep(5)
        channel = bot.get_channel(VOICE_ID)
        if not channel: return
        voice = discord.utils.get(bot.voice_clients, guild=channel.guild)
        if voice and voice.is_connected(): return
        await channel.connect(timeout=20.0, reconnect=True, self_deaf=False)
        print(f"[+] Бот зайшов у войс: {channel.name}")
    except Exception as e: print(f"Voice Error: {e}")

# --- КОМАНДИ (КЛАСИЧНИЙ ДИЗАЙН v1.5) ---
@bot.tree.command(name="midnight_info", description="Показати функціонал та статус бота")
async def midnight_info(interaction: discord.Interaction):
    status_emoji = "🟢 Увімкнено" if gaming_stats_enabled else "🔴 Вимкнено"
    embed = discord.Embed(
        title="🌑 Midnight Bot | System Info", 
        description="Твій автономний помічник на сервері Midnight.", 
        color=discord.Color.dark_gray()
    )
    embed.add_field(name="🎮 Моніторинг ігор", value=f"Сповіщає про збори на катку.\n**Статус:** {status_emoji}", inline=False)
    embed.add_field(name="🎙️ Voice Guardian", value="Цілодобова присутність у голосовому каналі.", inline=False)
    embed.add_field(name="🛠️ Керування", value="`/gaming_status` — змінити статус моніторингу.\n`/midnight_ping` — затримка мережі.", inline=False)
    embed.set_footer(text="Midnight Bot v1.8 | Стан: Стабільний")
    if bot.user.avatar: embed.set_thumbnail(url=bot.user.avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="gaming_status", description="Увімкнути/вимкнути моніторинг ігор")
async def gaming_status(interaction: discord.Interaction, status: bool):
    global gaming_stats_enabled
    gaming_stats_enabled = status
    await interaction.response.send_message(f"🌑 **Midnight System**\nМоніторинг ігор тепер: **{'✅ УВІМКНЕНО' if status else '❌ ВИМКНЕНО'}**")

@bot.tree.command(name="midnight_ping", description="Перевірка затримки")
async def midnight_ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🌑 **Midnight Bot**\n📡 **Затримка:** {round(bot.latency * 1000)}мс")

# --- МОНІТОРИНГ ТА ФОРУМ ---
@bot.event
async def on_presence_update(before, after):
    if not gaming_stats_enabled or before.activity == after.activity: return
    if after.activity and after.activity.type == discord.ActivityType.playing:
        game_name = after.activity.name
        channel = bot.get_channel(GAMING_LOG_ID)
        if not channel: return
        players = [m.display_name for m in after.guild.members if m.id != after.id 
                   for act in m.activities if act.type == discord.ActivityType.playing and act.name == game_name]
        if players:
            content = f"🎮 **{random.choice(GREETINGS)}**\n\nБачу, що **{', '.join(players + [after.display_name])}** зараз у **{game_name}**.\n{random.choice(ADVICES)}"
            try:
                if isinstance(channel, discord.ForumChannel):
                    await channel.create_thread(name=f"🎮 {game_name}", content=content)
                else:
                    await channel.send(content)
            except Exception as e: print(f"Forum Error: {e}")

@bot.event
async def on_voice_state_update(member, before, after):
    if member.id == bot.user.id and before.channel and not after.channel:
        await asyncio.sleep(10)
        await safe_join()

@bot.event
async def on_ready():
    print(f'[+] Авторизовано як: {bot.user.name}')
    await bot.tree.sync()
    asyncio.create_task(safe_join())

# --- ЗАПУСК ---
if __name__ == "__main__":
    keep_alive()
    # Твій новий токен
    TOKEN = "MTQ5MjY2MjU5NzM1NzQwNDIxMQ.GNy4wE.3L7h8eWVa2ZLCQwmKwikaBTPuvOm6denfCRcMI"
    bot.run(TOKEN)
