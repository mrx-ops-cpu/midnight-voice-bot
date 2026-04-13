import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask
from threading import Thread
import os
import asyncio
import random

# --- 1. ВЕБ-СЕРВЕР (Для Railway) ---
app = Flask('')

@app.route('/')
def home():
    return "MIDNIGHT BOT IS ONLINE"

def run():
    # Railway автоматично дає PORT, якщо ні — ставимо 8080
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- 2. НАЛАШТУВАННЯ БОТА ---
intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.message_content = True 
intents.presences = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# --- ГЛОБАЛЬНІ ЗМІННІ ---
VOICE_ID = 1458906259922354277 
GAMING_LOG_ID = 1493054931224105070 
gaming_stats_enabled = True

GREETINGS = [
    "Бачу, тут намічається серйозна катка!",
    "Виявлено активність виживших у мережі.",
    "О, вже збирається непогане паті!",
    "Ніч стає цікавішою, коли є з ким пограти.",
    "Здається, хтось вирішив підкорити ладдер!",
    "Сигнали Midnight Radar зафіксували рух!"
]

ADVICES = [
    "Може, зберете повне паті? 🔥",
    "Не забудьте зайти в голосовий канал! 🎙️",
    "Вдалого полювання! 🌑",
    "Покажіть їм, хто тут батя. 💪",
    "Час перемагати! 🏆"
]

# --- ФУНКЦІЯ ПІДКЛЮЧЕННЯ ---
async def safe_join():
    """Безпечний вхід у голосовий канал"""
    try:
        await bot.wait_until_ready()
        await asyncio.sleep(5)
        channel = bot.get_channel(VOICE_ID)
        if not channel:
            print("[-] Канал не знайдено.")
            return
            
        voice = discord.utils.get(bot.voice_clients, guild=channel.guild)
        if voice and voice.is_connected():
            return
            
        await channel.connect(timeout=20.0, reconnect=True, self_deaf=True)
        print(f"[+] Бот зайшов у войс: {channel.name}")
    except Exception as e:
        print(f"[-] Помилка підключення до войсу: {e}")

# --- СЛЕШ-КОМАНДИ ---
@bot.tree.command(name="midnight_info", description="Функціонал та статус бота")
async def midnight_info(interaction: discord.Interaction):
    status_emoji = "🟢 Увімкнено" if gaming_stats_enabled else "🔴 Вимкнено"
    embed = discord.Embed(title="🌑 Midnight Bot | System Info", color=discord.Color.dark_gray())
    embed.add_field(name="🎮 Форум «Хто в гру»", value=f"Статус: {status_emoji}", inline=False)
    embed.add_field(name="🎙️ Voice Guardian", value="Бот тримає зв'язок у голосовому каналі.", inline=False)
    embed.set_footer(text="Midnight Bot v1.8")
    if bot.user.avatar:
        embed.set_thumbnail(url=bot.user.avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="gaming_status", description="Увімкнути/вимкнути моніторинг ігор")
async def gaming_status(interaction: discord.Interaction, status: bool):
    global gaming_stats_enabled
    gaming_stats_enabled = status
    await interaction.response.send_message(f"🌑 Моніторинг ігор: {'✅ Увімкнено' if status else '❌ Вимкнено'}")

# --- МОНІТОРИНГ ІГОР ---
@bot.event
async def on_presence_update(before, after):
    if not gaming_stats_enabled or before.activity == after.activity:
        return

    if after.activity and after.activity.type == discord.ActivityType.playing:
        game_name = after.activity.name
        channel = bot.get_channel(GAMING_LOG_ID)
        if not channel: return

        players = []
        for member in after.guild.members:
            if member.id != after.id:
                for act in member.activities:
                    if act.type == discord.ActivityType.playing and act.name == game_name:
                        players.append(member.display_name)
        
        if players:
            all_players = players + [after.display_name]
            content = f"🎮 **{random.choice(GREETINGS)}**\n\nБачу, що **{', '.join(all_players)}** зараз у **{game_name}**.\n{random.choice(ADVICES)}"

            try:
                if isinstance(channel, discord.ForumChannel):
                    await channel.create_thread(name=f"🎮 {game_name}", content=content)
                else:
                    await channel.send(content)
            except Exception as e:
                print(f"[-] Помилка відправки в канал: {e}")

# --- ПЕРЕПІДКЛЮЧЕННЯ ---
@bot.event
async def on_voice_state_update(member, before, after):
    # Якщо бота викинули з каналу
    if member.id == bot.user.id and before.channel and not after.channel:
        print("[!] Бота відключено від войсу. Повертаюсь...")
        await asyncio.sleep(10)
        await safe_join()

@bot.event
async def on_ready():
    print(f'[+] Авторизовано: {bot.user.name}')
    try:
        await bot.tree.sync()
        print("[+] Команди синхронізовано.")
    except Exception as e:
        print(f"[-] Sync error: {e}")
    
    # Запуск входу у войс
    asyncio.create_task(safe_join())

# --- ЗАПУСК ---
if __name__ == "__main__":
    keep_alive()
    # TOKEN краще тримати в Variables на Railway
    TOKEN = os.getenv("TOKEN") or "MTQ5MjY2MjU5NzM1NzQwNDIxMQ.GuWdHO.unpINiO1sHTWInyRrD83P2Dj4elDf-e0d9g1Fw"
    bot.run(TOKEN)
