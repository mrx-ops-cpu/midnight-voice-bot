import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
import os
import asyncio

# --- ВЕБ-СЕРВЕР ---
app = Flask('')
@app.route('/')
def home(): return "MIDNIGHT ONLINE"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run); t.daemon = True; t.start()

# --- НАЛАШТУВАННЯ ---
intents = discord.Intents.default()
intents.voice_states = intents.guilds = intents.message_content = True 
intents.presences = intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

VOICE_ID = 1458906259922354277 
voice_welcome_enabled = True

async def safe_join():
    try:
        await bot.wait_until_ready()
        channel = bot.get_channel(VOICE_ID)
        if not channel: return

        # Якщо бот вже десь підключений у цій гільдії - відключаємо для чистої сесії
        existing_vc = discord.utils.get(bot.voice_clients, guild=channel.guild)
        if existing_vc:
            await existing_vc.disconnect(force=True)
            await asyncio.sleep(2)

        # Заходимо з великим таймаутом
        await channel.connect(reconnect=True, self_deaf=False)
        print(f"[+] Бот стабільно сів у канал")
    except Exception as e:
        print(f"[-] Помилка входу: {e}")

@bot.event
async def on_voice_state_update(member, before, after):
    if member.id == bot.user.id and before.channel and not after.channel:
        await asyncio.sleep(5)
        await safe_join()
        return

    # Логіка привітання
    if voice_welcome_enabled and after.channel and after.channel.id == VOICE_ID and member.id != bot.user.id:
        vc = discord.utils.get(bot.voice_clients, guild=member.guild)
        
        # Чекаємо 2 секунди, щоб голос юзера стабілізувався
        await asyncio.sleep(2)
        
        if vc and vc.is_connected():
            if os.path.exists("welcome.mp3"):
                try:
                    if vc.is_playing(): vc.stop()
                    
                    # Використовуємо налаштування для кращої сумісності
                    options = "-loglevel panic -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
                    source = discord.FFmpegPCMAudio("welcome.mp3", before_options=options)
                    
                    vc.play(source)
                    print(f"[!] Звук пішов для {member.display_name}")
                except Exception as e:
                    print(f"[-] Помилка програвання: {e}")

@bot.event
async def on_ready():
    print(f'[+] {bot.user.name} готовий!')
    await bot.tree.sync()
    asyncio.create_task(safe_join())

if __name__ == "__main__":
    keep_alive()
    bot.run("MTQ5MjY2MjU5NzM1NzQwNDIxMQ.GNy4wE.3L7h8eWVa2ZLCQwmKwikaBTPuvOm6denfCRcMI")
