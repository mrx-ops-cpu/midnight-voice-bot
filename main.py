import discord
from discord.ext import commands
from flask import Flask
from threading import Thread
import os
import asyncio

# --- ВЕБ-СЕРВЕР ---
app = Flask('')
@app.route('/')
def home(): return "MIDNIGHT BOT IS ONLINE"

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
voice_welcome_enabled = True  # Змінна для керування звуком

async def safe_join():
    try:
        await bot.wait_until_ready()
        channel = bot.get_channel(VOICE_ID)
        if not channel: return
        voice = discord.utils.get(bot.voice_clients, guild=channel.guild)
        if not voice or not voice.is_connected():
            await channel.connect(reconnect=True, self_deaf=False)
            print("[+] Бот підключився до каналу")
    except Exception as e: print(f"Voice Error: {e}")

# --- КОМАНДИ КЕРУВАННЯ ---
@bot.tree.command(name="voice_status", description="Увімкнути/вимкнути голосове привітання")
async def voice_status(interaction: discord.Interaction, status: bool):
    global voice_welcome_enabled
    voice_welcome_enabled = status
    state = "✅ УВІМКНЕНО" if status else "❌ ВИМКНЕНО"
    await interaction.response.send_message(f"🌑 **Midnight System**\nГолосове привітання тепер: **{state}**")

@bot.tree.command(name="midnight_info", description="Статус бота")
async def midnight_info(interaction: discord.Interaction):
    v_status = "🟢 Активне" if voice_welcome_enabled else "🔴 Вимкнене"
    embed = discord.Embed(
        title="🌑 Midnight Bot | System Info", 
        description="Твій автономний помічник на сервері.", 
        color=discord.Color.dark_gray()
    )
    embed.add_field(name="🎙️ Voice Guardian", value=f"Авто-привітання: **{v_status}**", inline=False)
    embed.add_field(name="🛠️ Керування", value="`/voice_status` — змінити режим звуку.", inline=False)
    embed.set_footer(text="Midnight Bot v1.9.1 | Стан: Стабільний")
    if bot.user.avatar: embed.set_thumbnail(url=bot.user.avatar.url)
    await interaction.response.send_message(embed=embed)

# --- ГОЛОСОВЕ ПРИВІТАННЯ ---
@bot.event
async def on_voice_state_update(member, before, after):
    # 1. Повернення бота
    if member.id == bot.user.id and before.channel and not after.channel:
        await asyncio.sleep(5)
        await safe_join()
        return

    # 2. Перевірка: чи увімкнено звук та чи зайшов користувач
    if voice_welcome_enabled and after.channel and after.channel.id == VOICE_ID and member.id != bot.user.id:
        vc = discord.utils.get(bot.voice_clients, guild=member.guild)
        if vc and vc.is_connected():
            if os.path.exists("welcome.mp3"):
                try:
                    if vc.is_playing(): vc.stop()
                    vc.play(discord.FFmpegPCMAudio("welcome.mp3"))
                except Exception as e: print(f"Audio Error: {e}")
            else:
                print("Файл welcome.mp3 не знайдено!")

@bot.event
async def on_ready():
    print(f'[+] Бот готовий: {bot.user.name}')
    await bot.tree.sync()
    asyncio.create_task(safe_join())

if __name__ == "__main__":
    keep_alive()
    TOKEN = "MTQ5MjY2MjU5NzM1NzQwNDIxMQ.GNy4wE.3L7h8eWVa2ZLCQwmKwikaBTPuvOm6denfCRcMI"
    bot.run(TOKEN)
