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
# Використовуємо Intents.all(), щоб точно бачити статуси ігор та список учасників
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

# ID твого форуму або текстового каналу
GAMING_LOG_ID = 1493054931224105070 

# --- 3. МОНІТОРИНГ ІГОР ТА ФОРУМ ---
@bot.event
async def on_presence_update(before, after):
    # Перевіряємо, чи змінилася саме активність (гра)
    if before.activity == after.activity: return
    
    # Якщо користувач почав грати
    if after.activity and after.activity.type == discord.ActivityType.playing:
        game_name = after.activity.name
        channel = bot.get_channel(GAMING_LOG_ID)
        
        if not channel:
            print(f"[-] Канал {GAMING_LOG_ID} не знайдено!")
            return
        
        # Шукаємо, хто ще з учасників зараз грає в ту саму гру
        other_players = [
            m.display_name for m in after.guild.members 
            if m.id != after.id and any(
                act.name == game_name for act in m.activities 
                if act.type == discord.ActivityType.playing
            )
        ]
        
        # Якщо знайшли компанію (мінімум двоє грають в одне і те ж)
        if other_players:
            greetings = [
                "Бачу, тут намічається серйозна катка!", 
                "О, вже збирається непогане паті!", 
                "Виявлено активність у мережі.",
                "Вдалого полювання, сталкери!"
            ]
            
            all_players = other_players + [after.display_name]
            content = f"🎮 **{random.choice(greetings)}**\n\n**Гравці:** {', '.join(all_players)}\n**Гра:** {game_name}"
            
            try:
                # ЛОГІКА ФОРУМУ: якщо це форум, створюємо нову гілку (Thread)
                if isinstance(channel, discord.ForumChannel):
                    # Перевіряємо, чи вже є відкрита гілка з такою назвою, щоб не спамити
                    await channel.create_thread(name=f"🎮 {game_name}", content=content)
                    print(f"[+] Створено гілку форуму для {game_name}")
                else:
                    # Якщо це звичайний текстовий канал — просто надсилаємо повідомлення
                    await channel.send(content)
                    print(f"[+] Надіслано лог гри у текстовий канал")
            except Exception as e:
                print(f"[-] Помилка при створенні гілки/повідомлення: {e}")

# --- 4. КОМАНДА СТАТУСУ ---
@bot.tree.command(name="midnight_info", description="Перевірити стан систем")
async def midnight_info(interaction: discord.Interaction):
    embed = discord.Embed(title="🌑 Midnight System Control", color=0x2f3136)
    embed.add_field(name="🌐 Сервер", value="✅ Railway Online", inline=True)
    embed.add_field(name="📊 Моніторинг", value="✅ Active", inline=True)
    embed.set_footer(text="Система готова до роботи")
    await interaction.response.send_message(embed=embed)

@bot.event
async def on_ready():
    print(f'---')
    print(f'[+] {bot.user.name} успішно активований!')
    print(f'[+] Моніторинг форуму: УВІМКНЕНО')
    print(f'---')
    await bot.tree.sync()

if __name__ == "__main__":
    keep_alive()
    # Встав свій токен сюди
    bot.run("MTQ5MjY2MjU5NzM1NzQwNDIxMQ.GNy4wE.3L7h8eWVa2ZLCQwmKwikaBTPuvOm6denfCRcMI")
