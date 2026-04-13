import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
import os
import asyncio
import random
import shutil

# --- 1. ВЕБ-СЕРВЕР ДЛЯ RAILWAY ---
app = Flask('')
@app.route('/')
def home(): return "MIDNIGHT SYSTEM ONLINE"

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

# Твої ID
VOICE_ID = 1458906259922354277 
GAMING_LOG_ID = 1493054931224105070 

# Змінні керування
voice_welcome_enabled = True
gaming_stats_enabled = True

# --- 3. СТАБІЛЬНИЙ ВХІД У ВОЙС ---
async def safe_join():
    try:
        await bot.wait_until_ready()
        print("[...] Очікування 10 секунд для стабілізації мережі Railway...")
        await asyncio.sleep(10) # Фікс помилки 4006
        
        channel = bot.get_channel(VOICE_ID)
        if not channel: return

        for vc in bot.voice_clients:
            await vc.disconnect(force=True)
        
        await asyncio.sleep(2)
        await channel.connect(reconnect=True, timeout=60, self_deaf=False)
        print(f"[+] Бот стабільно зайшов у канал: {channel.name}")
    except Exception as e:
        print(f"[-] Помилка входу: {e}")

# --- 4. ПРИВІТАННЯ (ЗВУК) ---
@bot.event
async def on_voice_state_update(member, before, after):
    if member.id == bot.user.id and before.channel and not after.channel:
        await asyncio.sleep(5); await safe_join(); return

    if voice_welcome_enabled and after.channel and after.channel.id == VOICE_ID and member.id != bot.user.id:
        vc = discord.utils.get(bot.voice_clients, guild=member.guild)
        await asyncio.sleep(2)
        
        if vc and vc.is_connected():
            if os.path.exists("welcome.mp3"):
                try:
                    if vc.is_playing(): vc.stop()
                    
                    exe_path = shutil.which("ffmpeg")
                    if not exe_path:
                        print("[-] FFmpeg не знайдено в системі!")
                        return

                    source = discord.FFmpegPCMAudio(
                        "welcome.mp3", 
                        executable=exe_path,
                        before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
                    )
                    vc.play(source)
                    print(f"[!] ЗВУК ПІШОВ ДЛЯ: {member.display_name}")
                except Exception as e:
                    print(f"[-] Помилка аудіо: {e}")

# --- 5. МОНІТОРИНГ ІГОР ---
@bot.event
async def on_presence_update(before, after):
    if not gaming_stats_enabled or before.activity == after.activity: return
    if after.activity and after.activity.type == discord.ActivityType.playing:
        game_name = after.activity.name
        channel = bot.get_channel(GAMING_LOG_ID)
        if not channel: return
        
        players = [m.display_name for m in after.guild.members 
                   if m.id != after.id and any(act.name == game_name for act in m.activities if act.type == discord.ActivityType.playing)]
        
        if players:
            greetings = ["О, збирається непогане паті!", "Виявлено нову катку!", "Вдалого полювання!"]
            content = f"🎮 **{random.choice(greetings)}**\nГравці: {', '.join(players + [after.display_name])}\nГра: {game_name}"
            if isinstance(channel, discord.ForumChannel):
                await channel.create_thread(name=f"🎮 {game_name}", content=content)
            else
