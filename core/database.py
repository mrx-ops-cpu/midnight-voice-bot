import os
import json
from datetime import datetime, date, timedelta
from core import config

def load_stats():
    if os.path.exists(config.STATS_FILE):
        try:
            with open(config.STATS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k in ("total", "daily", "games", "streaks", "history"):
                data.setdefault(k, {})
            return data
        except Exception as e: print(f"ERROR load_stats: {e}")
    return {"total": {}, "daily": {}, "games": {}, "streaks": {}, "history": {}}

def save_stats(data):
    try:
        tmp_file = config.STATS_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_file, config.STATS_FILE)
    except Exception as e: print(f"ERROR save_stats: {e}")

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
        tmp_file = config.SESSIONS_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in config.voice_start_times.items()}, f)
        os.replace(tmp_file, config.SESSIONS_FILE)
    except Exception as e: print(f"ERROR save_voice_sessions: {e}")

def load_game_sessions():
    if os.path.exists(config.GAME_SESSIONS_FILE):
        try:
            with open(config.GAME_SESSIONS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            
            migrated = {}
            for k, v in raw.items():
                if isinstance(v, dict) and "game" in v:
                    migrated[int(k)] = {v["game"]: {"start_time": v["start_time"], "session_start": v.get("session_start", v["start_time"])}}
                else:
                    migrated[int(k)] = v
            return migrated
        except: pass
    return {}

def save_game_sessions():
    try:
        tmp_file = config.GAME_SESSIONS_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in config.game_sessions.items()}, f)
        os.replace(tmp_file, config.GAME_SESSIONS_FILE)
    except Exception as e: print(f"ERROR save_game_sessions: {e}")

def load_active_rooms():
    if os.path.exists(config.ROOMS_FILE):
        try:
            with open(config.ROOMS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {}

def save_active_rooms():
    try:
        tmp_file = config.ROOMS_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(config.active_rooms, f, ensure_ascii=False)
        os.replace(tmp_file, config.ROOMS_FILE)
    except Exception as e: print(f"ERROR save_rooms: {e}")

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
        tmp_file = config.MSG_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump({"live": config.live_message_id, "fame": config.fame_message_id}, f)
        os.replace(tmp_file, config.MSG_FILE)
    except Exception as e: print(f"ERROR save_message_ids: {e}")

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

def add_voice_time_only(member_id, duration):
    if duration <= 0: return
    s = load_stats()
    uid = str(member_id)
    
    try:
        current_total = float(s["total"].get(uid, 0))
        current_daily = float(s["daily"].get(uid, 0))
    except:
        current_total, current_daily = 0.0, 0.0
        
    s["total"][uid] = current_total + duration
    s["daily"][uid] = current_daily + duration
    save_stats(s)
    update_streak(uid)

def add_game_time_only(member_id, duration, game):
    if duration <= 0 or not game: return
    s = load_stats()
    uid = str(member_id)
    
    if "games" not in s or not isinstance(s["games"], dict):
        s["games"] = {}
    if uid not in s["games"] or not isinstance(s["games"][uid], dict):
        s["games"][uid] = {}
        
    try:
        current_game_time = float(s["games"][uid].get(game, 0))
    except:
        current_game_time = 0.0
        
    s["games"][uid][game] = current_game_time + duration
    save_stats(s)
    update_streak(uid)

def get_unsaved_voice_time(user_id):
    if user_id in config.voice_start_times:
        last_save = config.voice_last_save.get(user_id, config.voice_start_times[user_id])
        return datetime.now().timestamp() - last_save
    return 0.0

def get_total_time(user_id):
    return load_stats()["total"].get(str(user_id), 0) + get_unsaved_voice_time(user_id)

def get_daily_time(user_id):
    return load_stats()["daily"].get(str(user_id), 0) + get_unsaved_voice_time(user_id)

def get_current_session(user_id):
    if user_id in config.voice_start_times:
        return datetime.now().timestamp() - config.voice_start_times[user_id]
    return 0.0

def get_display_name(uid, guild, bot=None):
    try:
        m = guild.get_member(int(uid)) if guild else None
        if m: return m.display_name
        if bot:
            u = bot.get_user(int(uid))
            if u: return u.display_name
    except: pass
    return f"User {uid}"

def normalize_game_name(game_name):
    if not game_name: 
        return game_name
    lower_name = game_name.lower()
    gta_aliases = ["gta", "grand theft auto", "rage mp", "rage multiplayer", "ragemp", "fivem", "altv"]
    if any(alias in lower_name for alias in gta_aliases):
        return "GTA V"
    return game_name

def get_top_games(limit_games=10, limit_players=3):
    s = load_stats()
    gd = {}
    
    games_data = s.get("games", {})
    if not isinstance(games_data, dict): 
        games_data = {}
    
    for uid, ug in games_data.items():
        if not isinstance(ug, dict): continue
        
        for game, sec in ug.items():
            try:
                sec = float(sec)
            except: continue
            
            norm_game = normalize_game_name(game)
            if norm_game not in gd:
                gd[norm_game] = {"total": 0, "players": {}}
                
            gd[norm_game]["total"] += sec
            
            uid_str = str(uid)
            current_player_sec = gd[norm_game]["players"].get(uid_str, 0)
            gd[norm_game]["players"][uid_str] = current_player_sec + sec

    now = datetime.now().timestamp()
    
    for uid, user_sessions in config.game_sessions.items():
        if not isinstance(user_sessions, dict): continue
        
        for game, sess in user_sessions.items():
            if not isinstance(sess, dict) or "start_time" not in sess: continue
            
            norm_game = normalize_game_name(game)
            dur = now - sess.get("start_time", now) 
            
            if norm_game not in gd:
                gd[norm_game] = {"total": 0, "players": {}}
            gd[norm_game]["total"] += dur
            
            uid_str = str(uid)
            current_player_sec = gd[norm_game]["players"].get(uid_str, 0)
            gd[norm_game]["players"][uid_str] = current_player_sec + dur
            
    sorted_g = sorted(gd.items(), key=lambda x: x[1]["total"], reverse=True)
    result = {}
    
    for game, data in sorted_g[:limit_games]:
        sorted_players = sorted(data["players"].items(), key=lambda x: x[1], reverse=True)[:limit_players]
        result[game] = {
            "players": sorted_players,
            "total":   data["total"]
        }
    return result