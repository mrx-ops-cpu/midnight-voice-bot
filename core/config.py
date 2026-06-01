import os
from datetime import datetime, timezone

GLOBAL_SETTINGS = {
    "monitoring":  True,
    "voice_guard": True,
    "voice_stats": True,
    "version":     "v4.4.11",
    "image_url":   "https://cdn.discordapp.com/avatars/1492662597357404211/a_4bf48afaac3798695e46c007ce568803.gif?size=1024",
    "start_time":  datetime.now(timezone.utc)
}

VOICE_ID          = 1458906259922354277
GAMING_LOG_ID     = 1493054931224105070
GAMING_MONITOR_ID = 1495833786741424178
MODERATOR_ROLE_ID = 1374867014732087307
OWNER_ID          = 954088092183171184

DATA_DIR           = "/app/data"
STATS_FILE         = os.path.join(DATA_DIR, "voice_stats.json")
SESSIONS_FILE      = os.path.join(DATA_DIR, "active_sessions.json")
GAME_SESSIONS_FILE = os.path.join(DATA_DIR, "game_sessions.json")
ROOMS_FILE         = os.path.join(DATA_DIR, "active_rooms.json")
MSG_FILE           = os.path.join(DATA_DIR, "message_ids.json")
FACEIT_FILE        = os.path.join(DATA_DIR, "faceit_users.json")
FACEIT_DASHBOARD_FILE = os.path.join(DATA_DIR, "faceit_dashboard.json")
BOT_VOICE_FILE     = os.path.join(DATA_DIR, "bot_voice.json")
MONITOR_CHANNEL_FILE = os.path.join(DATA_DIR, "monitor_channel.json")
HIDDEN_GAMES_FILE  = os.path.join(DATA_DIR, "hidden_games.json")
SQLITE_DB_FILE     = os.path.join(DATA_DIR, "midnight.db")

os.makedirs(DATA_DIR, exist_ok=True)

voice_start_times = {}
voice_last_save   = {}
game_sessions     = {}
active_rooms      = {}

live_message_id     = None
fame_voice_msg_id   = None
fame_streaks_msg_id = None
fame_games_msg_id   = None
fame_games_2_msg_id = None
fame_games_3_msg_id = None

last_live_hash         = None
last_fame_voice_hash   = None
last_fame_streaks_hash = None
last_fame_games_hash   = None
last_fame_games_2_hash = None
last_fame_games_3_hash = None

SAY_LIMIT         = 1000
say_usage         = {}
