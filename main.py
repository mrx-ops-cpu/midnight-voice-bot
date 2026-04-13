import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
import os
import asyncio
import random

# --- 1. ВЕБ-СЕРВЕР ---
app = Flask('')
@app.route('/')
def home(): return "MIDNIGHT BOT IS ONLINE"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run); t.daemon = True; t.start()

# --- 2. НАЛАШТУВАННЯ ---
intents = discord.Intents.default()
intents.voice_states = True 
intents.guilds = True
intents.message_content = True 
intents.presences = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

VOICE_ID = 1458906259922354277 
GAMING_LOG_ID = 1493054931224105070 
voice_welcome_enabled = True
gaming_stats_enabled = True

# --- 3. ЛОГІКА ПІДКЛЮЧЕННЯ (ВИПРАВЛЕНО 4006) ---
async def safe_join():
    try:
        await bot.wait_until_ready()
        await asyncio.sleep(5) # Даємо сесії стабілізуватися
        
        channel = bot.get_channel(VOICE_ID)
        if not channel: return

        # Видаляємо старі з'єднання, щоб уникнути конфліктів
        for vc in bot.voice_clients:
            if vc.guild.id == channel.guild.id:
                await vc.disconnect(force=True)
                await asyncio.sleep(2)

        # Підключаємося з параметрами, що ігнорують помилки сесії
        await channel.connect(reconnect=True, self_deaf=False)
        print(f"[+] Бот у войсі: {channel.name}")
    except Exception as e:
        print(f"Voice Error: {e}")

# --- 4. ПРИВІТАННЯ ТА МОНІТОРИНГ ---
@bot.event
async def on_voice_state_update(member, before, after):
    # Повернення бота
    if member.id == bot.user.id and before.channel and not after.channel:
        await asyncio.sleep(7)
        await safe_join()
        return

    # Голосове привітання
    if voice_welcome_enabled and after.channel and after.channel.id == VOICE_ID and member.id != bot.user.id:
        vc = discord.utils.get(bot.voice_clients, guild=member.guild)
        if vc and vc.is_connected():
            if os.path.exists("welcome.mp3"):
                try:
                    # Важливо: використовуємо FFmpegPCMAudio з явною вказівкою
                    if vc.is_playing(): vc.stop()
                    
                    # Створюємо аудіо-джерело
                    source = discord.FFmpegPCMAudio("welcome.mp3", options="-loglevel panic")
                    vc.play(source)
                    print(f"[!] Звук відтворено для {member.display_name}")
                except Exception as e:
                    print(f"Audio Play Error: {e}")
            else:
                print("Файл welcome.mp3 не знайдено!")

# --- 5. МОНІТОРИНГ ІГОР ---
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
            content = f"🎮 **Нова катка!**\nГравці: {', '.join(players + [after.display_name])}\nГра: {game_name}"
            if isinstance(channel, discord.ForumChannel):
                await channel.create_thread(name=f"🎮 {game_name}", content=content)
            else:
                await channel.send(content)

# --- КОМАНДИ ---
@bot.tree.command(name="voice_status", description="Керування звуком")
async def voice_status(interaction: discord.Interaction, status: bool):
    global voice_welcome_enabled
    voice_welcome_enabled = status
    await interaction.response.send_message(f"Голосове привітання: {'✅ ВКЛ' if status else '❌ ВИКЛ'}")

@bot.event
async def on_ready():
    print(f'[+] {bot.user.name} Онлайн!')
    await bot.tree.sync()
    asyncio.create_task(safe_join())

if __name__ == "__main__":
    keep_alive()
    # Твій токен
    bot.run("MTQ5MjY2MjU5NzM1NzQwNDIxMQ.GNy4wE.3L7h8eWVa2ZLCQwmKwikaBTPuvOm6denfCRcMI")
