import os
import json
from datetime import datetime, date, timedelta
from core import config

# ── Статистика (Stats) ───────────────────────────────────────
def load_stats():
    if os.path.exists(config.STATS_FILE):
        try:
            with open(config.STATS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k in ("total", "daily", "games", "streaks"):
                data.setdefault(k, {})
            return data
        except Exception as e: print(f"ERROR load_stats: {e}")
    return {"total": {}, "daily": {}, "games": {}, "streaks": {}}

def save_stats(data):
    try:
        with open(config.STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e: print(f"ERROR save_stats: {e}")

# ── Сесії (Войс та Ігри) ─────────────────────────────────────
def load_voice_sessions():
    if os.path.exists(config.SESSIONS_FILE):
        try:
            with open(config.SESSIONS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return {int(k): float(v) for k, v in raw.items()}
        except: pass
    return {}

def save_voice_sessions():
    try:
        with open(config.SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in config.voice_start_times.items()}, f)
    except Exception as e: print(f"ERROR save_voice_sessions: {e}")

def load_game_sessions():
    if os.path.exists(config.GAME_SESSIONS_FILE):
        try:
            with open(config.GAME_SESSIONS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return {int(k): v for k, v in raw.items()}
        except: pass
    return {}

def save_game_sessions():
    try:
        with open(config.GAME_SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in config.game_sessions.items()}, f)
    except Exception as e: print(f"ERROR save_game_sessions: {e}")

# ── ID Повідомлень (Live-віджети) ────────────────────────────
def load_message_ids():
    if os.path.exists(config.MSG_FILE):
        try:
            with open(config.MSG_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            config.live_message_id = d.get("live")
            config.fame_message_id = d.get("fame")
        except: pass

def save_message_ids():
    try:
        with open(config.MSG_FILE, "w", encoding="utf-8") as f:
            json.dump({"live": config.live_message_id, "fame": config.fame_message_id}, f)
    except Exception as e: print(f"ERROR save_message_ids: {e}")

# ── Логіка підрахунку часу та стриків ────────────────────────
def update_streak(uid):
    s = load_stats()
    today = date.today().isoformat()
    entry = s.setdefault("streaks", {}).get(str(uid), {"last_date": None, "count": 0})
    if entry["last_date"] == today: return
    
    yest = (date.today() - timedelta(days=1)).isoformat()
    entry["count"] = entry["count"] + 1 if entry["last_date"] == yest else 1
    entry["last_date"] = today
    
    s["streaks"][str(uid)] = entry
    save_stats(s)

def get_streak(uid):
    entry = load_stats().get("streaks", {}).get(str(uid), {})
    today = date.today().isoformat()
    yest  = (date.today() - timedelta(days=1)).isoformat()
    return entry.get("count", 0) if entry.get("last_date") in (today, yest) else 0

def add_voice_time(member_id, duration, game=None):
    if duration <= 0: return
    s = load_stats()
    uid = str(member_id)
    
    s["total"][uid] = s["total"].get(uid, 0) + duration
    s["daily"][uid] = s["daily"].get(uid, 0) + duration
    
    if game:
        s.setdefault("games", {}).setdefault(uid, {})[game] = s["games"][uid].get(game, 0) + duration
        
    save_stats(s)
    update_streak(uid)

def add_game_time_only(member_id, duration, game):
    if duration <= 0 or not game: return
    s = load_stats()
    uid = str(member_id)
    
    s.setdefault("games", {}).setdefault(uid, {})[game] = s["games"][uid].get(game, 0) + duration
    save_stats(s)
    update_streak(uid)

def get_current_session(user_id):
    if user_id in config.voice_start_times:
        return datetime.now().timestamp() - config.voice_start_times[user_id]
    return 0.0

def get_total_time(user_id):
    return load_stats()["total"].get(str(user_id), 0) + get_current_session(user_id)

def get_daily_time(user_id):
    return load_stats()["daily"].get(str(user_id), 0) + get_current_session(user_id)

def get_top_games(limit_games=3, limit_players=5):
    s = load_stats()
    gd = {}
    for uid, ug in s.get("games", {}).items():
        for game, sec in ug.items():
            if game not in gd: gd[game] = {"total": 0, "players": []}
            gd[game]["total"] += sec
            gd[game]["players"].append((uid, sec))
            
    sorted_g = sorted(gd.items(), key=lambda x: x[1]["total"], reverse=True)
    result = {}
    for game, data in sorted_g[:limit_games]:
        result[game] = {
            "players": sorted(data["players"], key=lambda x: x[1], reverse=True)[:limit_players],
            "total":   data["total"]
        }
    return result

def get_display_name(uid, guild, bot=None):
    try:
        m = guild.get_member(int(uid)) if guild else None
        if m: return m.display_name
        if bot:
            u = bot.get_user(int(uid))
            if u: return u.display_name
    except: pass
    return f"User {uid}"