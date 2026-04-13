import discord
from discord.ext import commands
from discord import app_commands
from flask import Flask
from threading import Thread
import os
import asyncio
import random

# --- 1. ВЕБ-СЕРВЕР ДЛЯ RAILWAY ---
app = Flask('')
@app.route('/')
def home(): return "MIDNIGHT SYSTEM ONLINE"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run, daemon=True); t.start()

# --- 2. ГОЛОВНІ НАЛАШТУВАННЯ ---
GLOBAL_SETTINGS = {
    "monitoring": True,   
    "voice_guard": True,  
    "version": "v2.2",
    "image_url": "https://cdn.discordapp.com/avatars/1492662597357404211/a_4bf48afaac3798695e46c007ce568803.gif?size=1024"
}

# Зберігаємо активні сесії: { "Назва гри": [ID_гравця1, ID_гравця2...] }
active_sessions = {}

VOICE_ID = 1458906259922354277 
GAMING_LOG_ID = 1493054931224105070 

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# --- 3. ЛОГІКА ГОЛОСУ ---
async def safe_join():
    if not GLOBAL_SETTINGS["voice_guard"]: return
    try:
        await bot.wait_until_ready()
        channel = bot.get_channel(VOICE_ID)
        if not channel: return
        vc = discord.utils.get(bot.voice_clients, guild=channel.guild)
        if not vc or not vc.is_connected():
            await channel.connect(reconnect=True, timeout=20)
    except Exception as e:
        print(f"[-] Помилка входу: {e}")

# --- 4. КОМАНДИ КЕРУВАННЯ ---

@bot.tree.command(name="midnight_info", description="Системна інформація бота")
async def midnight_info(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🌑 Midnight Bot | System Info",
        description="Твій автономний помічник на сервері Midnight.",
        color=0x2b2d31
    )
    
    m_status = "🟢 Увімкнено" if GLOBAL_SETTINGS["monitoring"] else "🔴 Вимкнено"
    embed.add_field(name="🎮 Моніторинг ігор", value=f"Сповіщає про збори на катку.\n**Статус:** {m_status}", inline=False)
    
    v_status = "🟢 Активний" if GLOBAL_SETTINGS["voice_guard"] else "🔴 Неактивний"
    embed.add_field(name="🎙️ Voice Guardian", value=f"Цілодобова присутність у голосовому каналі.\n**Статус:** {v_status}", inline=False)
    
    embed.add_field(
        name="🛠️ Керування",
        value="`/set_monitoring` — статус ігор\n`/set_voice` — статус войсу\n`/midnight_ping` — пінг",
        inline=False
    )
    
    embed.set_thumbnail(url=GLOBAL_SETTINGS["image_url"])
    embed.set_footer(text=f"Midnight Bot {GLOBAL_SETTINGS['version']} | Стан: Стабільний")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="set_monitoring", description="Встановити статус моніторингу")
@app_commands.describe(стан="True або False")
@app_commands.choices(стан=[
    app_commands.Choice(name="True (Увімкнути)", value="true"),
    app_commands.Choice(name="False (Вимкнути)", value="false")
])
async def set_monitoring(interaction: discord.Interaction, стан: app_commands.Choice[str]):
    GLOBAL_SETTINGS["monitoring"] = (стан.value == "true")
    await interaction.response.send_message(f"📡 Моніторинг встановлено на **{GLOBAL_SETTINGS['monitoring']}**.", ephemeral=True)

@bot.tree.command(name="set_voice", description="Встановити статус Voice Guardian")
@app_commands.describe(стан="True або False")
@app_commands.choices(стан=[
    app_commands.Choice(name="True (Активувати)", value="true"),
    app_commands.Choice(name="False (Деактивувати)", value="false")
])
async def set_voice(interaction: discord.Interaction, стан: app_commands.Choice[str]):
    GLOBAL_SETTINGS["voice_guard"] = (стан.value == "true")
    if not GLOBAL_SETTINGS["voice_guard"]:
        for vc in bot.voice_clients: await vc.disconnect(force=True)
    else:
        await safe_join()
    await interaction.response.send_message(f"🎙️ Voice Guardian: **{GLOBAL_SETTINGS['voice_guard']}**.", ephemeral=True)

@bot.tree.command(name="midnight_ping", description="Перевірити затримку")
async def midnight_ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"📡 Затримка: **{round(bot.latency * 1000)}ms**", ephemeral=True)

# --- 5. ОБРОБКА ПОДІЙ (SESSION CONTROL) ---

@bot.event
async def on_presence_update(before, after):
    if not GLOBAL_SETTINGS["monitoring"]: return
    if before.activity == after.activity: return
    
    # Якщо гравець почав грати
    if after.activity and after.activity.type == discord.ActivityType.playing:
        game_name = after.activity.name
        guild = after.guild
        
        # 1. Перевіряємо, чи є вже активна сесія для цієї гри
        if game_name in active_sessions:
            last_player_ids = active_sessions[game_name]
            
            # Перевіряємо, чи хоч один гравець з минулого списку ще в цій грі
            still_playing = False
            for p_id in last_player_ids:
                member = guild.get_member(p_id)
                if member and member.activity and member.activity.name == game_name:
                    still_playing = True
                    break
            
            # Якщо хтось ще грає — ігноруємо, щоб не спамити
            if still_playing:
                return 

        # 2. Якщо сесії немає або вона закінчилася — шукаємо, чи є компанія
        current_players = [m for m in guild.members 
                          if m.activity and m.activity.type == discord.ActivityType.playing and m.activity.name == game_name]
        
        if len(current_players) >= 2: # Мінімум двоє для анонсу
            # Зберігаємо ID всіх, хто зараз грає, як нову сесію
            active_sessions[game_name] = [m.id for m in current_players]
            
            channel = bot.get_channel(GAMING_LOG_ID)
            if not channel: return
            
            names = [m.display_name for m in current_players]
            greetings = ["О, вже збирається непогане паті!", "Бачу, тут намічається катка!", "Вдалого полювання!"]
            content = f"🎮 **{random.choice(greetings)}**\n**Гравці:** {', '.join(names)}\n**Гра:** {game_name}"
            
            if isinstance(channel, discord.ForumChannel):
                await channel.create_thread(name=f"🎮 {game_name}", content=content)
            else:
                await channel.send(content)

@bot.event
async def on_voice_state_update(member, before, after):
    if member.id == bot.user.id and before.channel and not after.channel:
        if GLOBAL_SETTINGS["voice_guard"]:
            await asyncio.sleep(5)
            await safe_join()

@bot.event
async def on_ready():
    print(f'--- Midnight {GLOBAL_SETTINGS["version"]} | Session Control Active ---')
    await bot.tree.sync()
    asyncio.create_task(safe_join())

if __name__ == "__main__":
    keep_alive()
    bot.run("MTQ5MjY2MjU5NzM1NzQwNDIxMQ.GNy4wE.3L7h8eWVa2ZLCQwmKwikaBTPuvOm6denfCRcMI")
