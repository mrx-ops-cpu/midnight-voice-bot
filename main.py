import discord
from discord.ext import commands
import os
import asyncio
from datetime import datetime
from threading import Thread
from flask import Flask, render_template

# Імпортуємо наші модулі
from core import config, database, utils

# ── Ініціалізація Бота ───────────────────────────────────────
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents, chunk_guilds_at_startup=True)

# ── Налаштування Flask (Web Dashboard) ───────────────────────
# Вказуємо Flask шукати шаблони в папці templates
app = Flask(__name__, template_folder="templates")

@app.route('/')
def home():
    # Збираємо дані для дашборду
    voice_online = len(config.voice_start_times)
    
    games = []
    for name, data in config.active_games.items():
        dur = int(datetime.now().timestamp() - data["start_time"])
        games.append({
            "name": name,
            "time": utils.format_time(dur),
            "players": ", ".join(data["players"])
        })
        
    # Топ користувачів
    s = database.load_stats()
    total = dict(s.get("total", {}))
    for uid, start in config.voice_start_times.items():
        k = str(uid)
        total[k] = total.get(k, 0) + (datetime.now().timestamp() - start)
        
    top_users = []
    for uid, sec in sorted(total.items(), key=lambda x: x[1], reverse=True)[:5]:
        name = database.get_display_name(uid, None, bot)
        top_users.append((name, utils.format_time(sec)))
        
    # Демо-дані для графіка (можна пізніше прив'язати до реальної бази)
    chart_labels = ["Пн", "Вв", "Ср", "Чт", "Пт", "Сб", "Нд"]
    chart_data = [12, 19, 15, 25, 22, 30, 28]

    return render_template('dashboard.html', 
                           voice_online=voice_online, 
                           games=games, 
                           top_users=top_users,
                           chart_labels=chart_labels,
                           chart_data=chart_data)

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, use_reloader=False)

def keep_alive():
    Thread(target=run_flask, daemon=True).start()

# ── Запуск Бота та Cogs ──────────────────────────────────────
INITIAL_EXTENSIONS = [
    'cogs.events',
    'cogs.commands',
    'cogs.tasks'
]

@bot.event
async def on_ready():
    print(f'\n--- Midnight {config.GLOBAL_SETTINGS["version"]} ONLINE ---')
    print(f'--- FFmpeg: {utils.FFMPEG_PATH} ---')
    
    database.load_message_ids()
    
    # Синхронізуємо слеш-команди з Discord
    await bot.tree.sync()
    
    # Відновлюємо сесії з файлів бази (якщо бот перезапускався)
    saved_gs = database.load_game_sessions()
    saved_vs = database.load_voice_sessions()
    config.active_games.clear()
    config.game_sessions.clear()

    # Пробігаємось по серверах і шукаємо, хто зараз у войсі чи грає
    for guild in bot.guilds:
        for member in guild.members:
            if member.bot: continue
            
            # Шукаємо гру
            act = next((a for a in member.activities if hasattr(a, 'name') and a.name and not isinstance(a, discord.CustomActivity) and a.name != "Spotify"), None)
            game = act.name if act else None
            
            if game and config.GLOBAL_SETTINGS["monitoring"]:
                if member.id in saved_gs and saved_gs[member.id].get("game") == game:
                    config.game_sessions[member.id] = saved_gs[member.id]
                else:
                    config.game_sessions[member.id] = {"game": game, "start_time": datetime.now().timestamp()}
                    
                if game not in config.active_games:
                    config.active_games[game] = {"players": [member.display_name], "start_time": datetime.now().timestamp()}
                elif member.display_name not in config.active_games[game]["players"]:
                    config.active_games[game]["players"].append(member.display_name)

        # Шукаємо людей у войсі
        for channel in guild.voice_channels:
            for member in channel.members:
                if member.bot: continue
                config.voice_start_times[member.id] = saved_vs.get(str(member.id), datetime.now().timestamp())

        # Оновлюємо віджети
        bot.loop.create_task(utils.update_fame_message(guild, bot))
        bot.loop.create_task(utils.update_live_message(guild, bot))

    database.save_voice_sessions()
    database.save_game_sessions()

    # Підключаємось до войсу (Войс-гард)
    await asyncio.sleep(2)
    await utils.join_voice_safe(bot)
    
    print(f"READY: {len(config.voice_start_times)} у войсі | {len(config.active_games)} ігор")

async def main():
    # Запускаємо веб-сервер
    keep_alive()
    
    # Завантажуємо коги (модулі)
    for extension in INITIAL_EXTENSIONS:
        try:
            await bot.load_extension(extension)
            print(f"✅ Модуль завантажено: {extension}")
        except Exception as e:
            print(f"❌ Помилка завантаження {extension}: {e}")

    # Отримуємо токен
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        print("⚠️ УВАГА: DISCORD_TOKEN не знайдено в оточенні!")
        # Тільки для тестів на ПК. На хостингу використовуй Secrets/ENV!
        token = "ТВІЙ_ТОКЕН_БОТА_ТУТ" 
    
    await bot.start(token)

if __name__ == "__main__":
    # Запуск асинхронного лупу
    asyncio.run(main())