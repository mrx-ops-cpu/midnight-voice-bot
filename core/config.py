import os
from datetime import datetime, timezone

# ── Головні налаштування ──────────────────────────────────────
GLOBAL_SETTINGS = {
    "monitoring":  True,
    "voice_guard": True,
    "voice_stats": True,
    "version":     "v4.3.0 (Modular)",
    "image_url":   "https://cdn.discordapp.com/avatars/1492662597357404211/a_4bf48afaac3798695e46c007ce568803.gif?size=1024",
    "start_time":  datetime.now(timezone.utc)
}

# ── Хардкод ID (Бажано пізніше винести в .env) ───────────────
VOICE_ID          = 1458906259922354277
GAMING_LOG_ID     = 1493054931224105070
GAMING_MONITOR_ID = 1495833786741424178

# ── Словник ігор (Короткі назви) ─────────────────────────────
SHORT_TITLES = {
    "Dota 2":"👑 Дота","Counter-Strike 2":"🔫 КС","CS2":"🔫 КС",
    "League of Legends":"⚔️ ЛоЛ","Valorant":"🎯 Вало","Minecraft":"⛏️ Майн",
    "GTA V":"🚗 ГТА","Grand Theft Auto V":"🚗 ГТА","Grand Theft Auto V Legacy":"🚗 ГТА",
    "Apex Legends":"🏆 Апекс","EA Sports FC 26":"⚽ Футбол","EA Sports FC 25":"⚽ Футбол",
    "FIFA 23":"⚽ Футбол","FIFA 24":"⚽ Футбол","RADMIR CRMP":"🚔 Радмір",
    "Fortnite":"🪂 Форт","Rocket League":"🚀 РЛ","World of Warcraft":"🧙 ВоВ",
    "Call of Duty":"🪖 КоД","Among Us":"🕵️ Амонг","Rust":"🪓 Раст",
    "PUBG":"🎯 ПАБГ","PUBG: BATTLEGROUNDS":"🎯 ПАБГ",
    "Majestic RP":"🏙️ Маєстік","ARC Raiders":"🤖 АРК",
    "Way of the Hunter":"🦌 Мисливець","Project Zomboid":"🧟 Зомбоїд",
    "World of Warships":"⚓ Кораблі","Arena Breakout: Infinite":"🪖 Арена",
    "Far Cry 6":"🌴 ФарКрай","Metro: Last Light Redux":"🚇 Метро",
}

# ── Шляхи до файлів (База Даних JSON) ────────────────────────
DATA_DIR           = "/app/data"
STATS_FILE         = os.path.join(DATA_DIR, "voice_stats.json")
SESSIONS_FILE      = os.path.join(DATA_DIR, "active_sessions.json")
GAME_SESSIONS_FILE = os.path.join(DATA_DIR, "game_sessions.json")
MSG_FILE           = os.path.join(DATA_DIR, "message_ids.json")

# Створюємо папку, якщо її немає
os.makedirs(DATA_DIR, exist_ok=True)

# ── RAM Стан (Оперативна пам'ять бота) ───────────────────────
voice_start_times = {}   # {user_id: timestamp}
game_sessions     = {}   # {user_id: {"game": str, "start_time": float}}
active_games      = {}   # {game_name: {"players": [...], "start_time": float}}

live_message_id   = None
fame_message_id   = None

SAY_LIMIT         = 3
say_usage         = {}   # {user_id: [timestamp, ...]}