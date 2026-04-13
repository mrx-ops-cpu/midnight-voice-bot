import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
import os
import asyncio
import random

# --- 1. ВЕБ-СЕРВЕР ДЛЯ RAILWAY ---
app = Flask('')
@app.route('/')
def home(): return "MIDNIGHT SYSTEM IS ONLINE"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run); t.daemon = True; t.start()

# --- 2. НАЛАШТУВАННЯ ТА ІНТЕНТИ ---
intents = discord.Intents.default()
intents.voice_states = True 
intents.guilds = True
intents.message_content = True 
intents.presences = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Твої ID каналів
VOICE_ID = 1458906259922354277 
GAMING_LOG_ID = 1493054931224105070 

# Глобальні змінні керування
voice_welcome_enabled = True
gaming_stats_enabled = True

# Текстові бази
GREETINGS = ["Бачу, тут намічається серйозна катка!", "Виявлено активність у мережі.", "О, вже збирається непогане паті!"]

# --- 3. СТАБІЛЬНЕ ПІДКЛЮЧЕННЯ ДО ГОЛОСУ ---
async def safe_join():
    try:
        await bot.wait_until_ready()
        channel = bot.get_channel(VOICE_ID)
        if not channel: return

        # Видаляємо всі існуючі "зависші" з'єднання бота
        for vc in bot.voice_clients:
            await vc.disconnect(force=True)
        
        await asyncio.sleep(2)
        
        # Підключаємося з великим таймаутом та авто-реконектом
        await channel.connect(reconnect=True, timeout=30, self_deaf=False)
        print(f"[+] Бот успішно зайняв позицію у каналі: {channel.name}")
    except Exception as e:
        print(f"[-] Помилка входу у войс: {e}")

# --- 4. ОБРОБНИК ГОЛОСОВИХ ПОДІЙ ---
@bot.event
async def on_voice_state_update(member, before, after):
    # Якщо бота викинули - він повертається
    if member.id == bot.user.id and before.channel and not after.channel:
        await asyncio.sleep(5)
        await safe_join()
        return

    # Голосове привітання welcome.mp3
    if voice_welcome_enabled and after.channel and after.channel.id == VOICE_ID and member.id != bot.user.id:
        vc = discord.utils.get(bot.voice_clients, guild=member.guild)
        
        # Чекаємо 3 секунди, поки Discord стабілізує потік юзера
        await asyncio.sleep(3)
        
        if vc and vc.is_connected():
            if os.path.exists("welcome.mp3"):
                try:
                    if vc.is_playing(): vc.stop()
                    
                    # Налаштування для "пробивання" через сервери Railway
                    ffmpeg_opts = {
                        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                        'options': '-vn -loglevel panic'
                    }
                    
                    source = discord.FFmpegPCMAudio("welcome.mp3", **ffmpeg_opts)
                    vc.play(source)
                    print(f"[!] Звук відправлено для гравця: {member.display_name}")
                except Exception as e:
                    print(f"[-] Помилка аудіо: {e}")
            else:
                print("[-] Файл welcome.mp3 не знайдено у репозиторії!")

# --- 5. МОНІТОРИНГ ІГОР ТА ФОРУМ ---
@bot.event
async def on_presence_update(before, after):
    if not gaming_stats_enabled or before.activity == after.activity: return
    
    if after.activity and after.activity.type == discord.ActivityType.playing:
        game_name = after.activity.name
        channel = bot.get_channel(GAMING_LOG_ID)
        if not channel: return
        
        # Пошук інших гравців у цю ж гру
        players = [m.display_name for m in after.guild.members 
                   if m.id != after.id and any(act.name == game_name for act in m.activities if act.type == discord.ActivityType.playing)]
        
        if players:
            content = f"🎮 **{random.choice(GREETINGS)}**\nГравці: {', '.join(players + [after.display_name])}\nГра: {game_name}"
            if isinstance(channel, discord.ForumChannel):
                await channel.create_thread(name=f"🎮 {game_name}", content=content)
            else:
                await channel.send(content)

# --- 6. КОМАНДИ КЕРУВАННЯ ---
@bot.tree.command(name="voice_status", description="Увімкнути/вимкнути звук")
async def voice_status(interaction: discord.Interaction, status: bool):
    global voice_welcome_enabled
    voice_welcome_enabled = status
    state = "✅ УВІМКНЕНО" if status else "❌ ВИМКНЕНО"
    await interaction.response.send_message(f"🌑 **Midnight System**\nГолосове привітання: **{state}**")

@bot.tree.command(name="midnight_info", description="Статус систем")
async def midnight_info(interaction: discord.Interaction):
    v_status = "🟢 Активне" if voice_welcome_enabled else "🔴 Вимкнене"
    g_status = "🟢 Працює" if gaming_stats_enabled else "🔴 Пауза"
    embed = discord.Embed(title="🌑 Midnight Bot | System Info", color=discord.Color.dark_gray())
    embed.add_field(name="🎙️ Голос", value=v_status, inline=True)
    embed.add_field(name="🎮 Геймінг", value=g_status, inline=True)
    embed.set_footer(text="v1.9.9 | Стан: Стабільний")
    await interaction.response.send_message(embed=embed)

# --- ЗАПУСК ---
@bot.event
async def on_ready():
    print(f'[+] {bot.user.name} Онлайн та готовий!')
    await bot.tree.sync()
    asyncio.create_task(safe_join())

if __name__ == "__main__":
    keep_alive()
    # Твій актуальний токен
    TOKEN = "MTQ5MjY2MjU5NzM1NzQwNDIxMQ.GNy4wE.3L7h8eWVa2ZLCQwmKwikaBTPuvOm6denfCRcMI"
    bot.run(TOKEN)
