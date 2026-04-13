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

# 2. Налаштування (Додано Presences та Members для відстеження ігор)
intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.message_content = True 
intents.presences = True  # Бачити у що грають
intents.members = True    # Бачити нікнейми на сервері

bot = commands.Bot(command_prefix='!', intents=intents)

# ID Твоїх каналів
VOICE_ID = 1458906259922354277 
GAMING_LOG_ID = 1493042941709783170 # Канал для сповіщень про ігри

async def safe_join():
    """Логіка входу в голосовий канал"""
    await bot.wait_until_ready()
    channel = bot.get_channel(VOICE_ID)
    if not channel: return
    voice = discord.utils.get(bot.voice_clients, guild=channel.guild)
    if voice and voice.is_connected(): return
    try:
        await channel.connect(timeout=20.0, reconnect=True)
        print(f"[+] Бот зайшов у войс.")
    except Exception as e: print(f"Error: {e}")

@bot.tree.command(name="midnight_ping", description="Перевірка затримки бота")
async def midnight_ping(interaction: discord.Interaction):
    ping_ms = round(bot.latency * 1000)
    await interaction.response.send_message(f"🌑 **Midnight Bot**\n📡 **Затримка:** {ping_ms}мс")

# --- СИСТЕМА МОНІТОРИНГУ ІГОР ---
@bot.event
async def on_presence_update(before, after):
    # Перевіряємо, чи змінилася саме активність
    if before.activity == after.activity:
        return

    # Якщо користувач запустив гру (ActivityType.playing)
    if after.activity and after.activity.type == discord.ActivityType.playing:
        game_name = after.activity.name
        guild = after.guild
        channel = bot.get_channel(GAMING_LOG_ID)
        
        if not channel:
            return

        # Шукаємо інших учасників сервера, які грають у ту саму гру
        players_in_game = []
        for member in guild.members:
            if member.id != after.id: # Не рахуємо того, хто щойно запустив
                for act in member.activities:
                    if act.type == discord.ActivityType.playing and act.name == game_name:
                        players_in_game.append(member.display_name)
        
        # Якщо в грі вже є хоча б один інший гравець
        if len(players_in_game) > 0:
            # Складаємо список імен: ті хто вже був + той хто щойно зайшов
            all_players = players_in_game + [after.display_name]
            names_list = ", ".join(all_players)
            
            # Повідомлення без тегів (@), просто імена
            msg = f"🎮 **Збір на катку!**\nБачу, що **{names_list}** зараз у **{game_name}**.\nМоже, зберете повне паті? 🔥"
            
            await channel.send(msg)

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

# 3. Запуск
if __name__ == "__main__":
    keep_alive()
    # TOKEN з Railway або твій старий
    TOKEN = os.getenv("TOKEN") or "MTQ5MjY2MjU5NzM1NzQwNDIxMQ.GuWdHO.unpINiO1sHTWInyRrD83P2Dj4elDf-e0d9g1Fw"
    
    try:
        bot.run(TOKEN)
    except Exception as e:
        print(f"[-] Помилка запуску: {e}")
