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
def home(): return "MIDNIGHT SYSTEM ONLINE"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run, daemon=True); t.start()

# --- 2. НАЛАШТУВАННЯ БОТА ---
intents = discord.Intents.default()
intents.guilds = True
intents.message_content = True 
intents.presences = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Твій ID каналу для логів ігор
GAMING_LOG_ID = 1493054931224105070 

# --- 3. МОНІТОРИНГ ІГОР ---
@bot.event
async def on_presence_update(before, after):
    # Ігноруємо зміни, які не стосуються активності
    if before.activity == after.activity: return
    
    # Перевіряємо, чи користувач почав грати
    if after.activity and after.activity.type == discord.ActivityType.playing:
        game_name = after.activity.name
        channel = bot.get_channel(GAMING_LOG_ID)
        if not channel: return
        
        # Шукаємо інших гравців у ту ж саму гру на сервері
        players = [m.display_name for m in after.guild.members 
                   if m.id != after.id and any(act.name == game_name for act in m.activities if act.type == discord.ActivityType.playing)]
        
        if players:
            greetings = [
                "Бачу, тут намічається серйозна катка!", 
                "О, вже збирається непогане паті!", 
                "Виявлено активність у мережі.",
                "Вдалого полювання!"
            ]
            content = f"🎮 **{random.choice(greetings)}**\nГравці: {', '.join(players + [after.display_name])}\nГра: **{game_name}**"
            
            # Якщо канал — форум, створюємо гілку, якщо звичайний — просто пишемо
            if isinstance(channel, discord.ForumChannel):
                await channel.create_thread(name=f"🎮 {game_name}", content=content)
            else:
                await channel.send(content)

# --- 4. КОМАНДИ ---
@bot.tree.command(name="midnight_info", description="Статус систем")
async def midnight_info(interaction: discord.Interaction):
    embed = discord.Embed(title="🌑 Midnight System", color=0x2f3136)
    embed.add_field(name="🌐 Статус", value="✅ Онлайн", inline=True)
    embed.add_field(name="🎮 Моніторинг", value="✅ Активний", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.event
async def on_ready():
    print(f'[+] {bot.user.name} увійшов у систему!')
    await bot.tree.sync()

if __name__ == "__main__":
    keep_alive()
    bot.run("MTQ5MjY2MjU5NzM1NzQwNDIxMQ.GNy4wE.3L7h8eWVa2ZLCQwmKwikaBTPuvOm6denfCRcMI")
