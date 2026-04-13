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
    "version": "v2.1",
    "image_url": "https://cdn.discordapp.com/avatars/1492662597357404211/a_4bf48afaac3798695e46c007ce568803.gif?size=1024"
}

# Словник для збереження часу останнього повідомлення по кожній грі
game_cooldowns = {} 

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
            print(f"[+] Midnight зайняв позицію у каналі")
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
    embed.add_field(name="🎮 Моніторинг ігор", value=f"**Статус:** {m_status}", inline=False)
    
    v_status = "🟢 Активний" if GLOBAL_SETTINGS["voice_guard"] else "🔴 Неактивний"
    embed.add_field(name="🎙️ Voice Guardian", value=f"**Статус:** {v_status}", inline=False)
    
    embed.set_thumbnail(url=GLOBAL_SETTINGS["image_url"])
    embed.set_footer(text=f"Midnight Bot {GLOBAL_SETTINGS['version']} | Стан: Стабільний")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="set_monitoring", description="Встановити статус моніторингу")
@app_commands.describe(стан="Увімкнути або Вимкнути")
@app_commands.choices(стан=[
    app_commands.Choice(name="True (Увімкнути)", value="true"),
    app_commands.Choice(name="False (Вимкнути)", value="false")
])
async def set_monitoring(interaction: discord.Interaction, стан: app_commands.Choice[str]):
    GLOBAL_SETTINGS["monitoring"] = (стан.value == "true")
    await interaction.response.send_message(f"📡 Моніторинг: **{GLOBAL_SETTINGS['monitoring']}**", ephemeral=True)

@bot.tree.command(name="set_voice", description="Встановити статус Voice Guardian")
@app_commands.describe(стан="Увімкнути або Вимкнути")
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
    await interaction.response.send_message(f"🎙️ Voice Guardian: **{GLOBAL_SETTINGS['voice_guard']}**", ephemeral=True)

# --- 5. ОБРОБКА ПОДІЙ (МОНІТОРИНГ З КУЛДАУНОМ 1 ГОДИНА) ---

@bot.event
async def on_presence_update(before, after):
    if not GLOBAL_SETTINGS["monitoring"]: return
    if before.activity == after.activity: return
    
    if after.activity and after.activity.type == discord.ActivityType.playing:
        game_name = after.activity.name
        current_time = asyncio.get_event_loop().time()
        
        # --- ПЕРЕВІРКА КУЛДАУНУ (3600 секунд = 1 година) ---
        last_announced = game_cooldowns.get(game_name, 0)
        if current_time - last_announced < 3600:
            return # Ще не пройшла година, виходимо
            
        channel = bot.get_channel(GAMING_LOG_ID)
        if not channel: return
        
        players = [m.display_name for m in after.guild.members 
                   if m.id != after.id and any(act.name == game_name for act in m.activities if act.type == discord.ActivityType.playing)]
        
        if players:
            # Оновлюємо час останнього анонсу
            game_cooldowns[game_name] = current_time
            
            greetings = ["О, вже збирається непогане паті!", "Бачу, тут намічається катка!", "Вдалого полювання!"]
            all_players = players + [after.display_name]
            content = f"🎮 **{random.choice(greetings)}**\n**Гравці:** {', '.join(all_players)}\n**Гра:** {game_name}"
            
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
    print(f'--- Midnight {GLOBAL_SETTINGS["version"]} ONLINE (Anti-Spam 1h) ---')
    await bot.tree.sync()
    asyncio.create_task(safe_join())

if __name__ == "__main__":
    keep_alive()
    bot.run("MTQ5MjY2MjU5NzM1NzQwNDIxMQ.GNy4wE.3L7h8eWVa2ZLCQwmKwikaBTPuvOm6denfCRcMI")
