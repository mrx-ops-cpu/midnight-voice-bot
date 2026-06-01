import sqlite3
import json
import os
from datetime import datetime, timezone
from core import config

def get_db():
    conn = sqlite3.connect(config.SQLITE_DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS voice_stats (uid TEXT PRIMARY KEY, total_time REAL, daily_time REAL)")
        c.execute("CREATE TABLE IF NOT EXISTS streaks (uid TEXT, type TEXT, last_date TEXT, count INTEGER, PRIMARY KEY (uid, type))")
        c.execute("CREATE TABLE IF NOT EXISTS games (uid TEXT, game TEXT, time REAL, PRIMARY KEY (uid, game))")
        c.execute("CREATE TABLE IF NOT EXISTS history (date_str TEXT PRIMARY KEY, total_time REAL)")
        c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        conn.commit()
        
    migrate_from_json()

def migrate_from_json():
    # Only migrate if the stats file exists and we haven't migrated yet
    if not os.path.exists(config.STATS_FILE):
        return
        
    backup_file = config.STATS_FILE + ".backup"
    if os.path.exists(backup_file):
        return # Already migrated
        
    print("Migrating voice_stats.json to SQLite...")
    try:
        with open(config.STATS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        with get_db() as conn:
            c = conn.cursor()
            
            # Migrate voice_stats (total and daily)
            total = data.get("total", {})
            daily = data.get("daily", {})
            all_uids = set(list(total.keys()) + list(daily.keys()))
            for uid in all_uids:
                t = float(total.get(uid, 0))
                d = float(daily.get(uid, 0))
                c.execute("INSERT OR REPLACE INTO voice_stats (uid, total_time, daily_time) VALUES (?, ?, ?)", (uid, t, d))
                
            # Migrate streaks (voice)
            for uid, streak_data in data.get("streaks", {}).items():
                ld = streak_data.get("last_date")
                count = streak_data.get("count", 0)
                c.execute("INSERT OR REPLACE INTO streaks (uid, type, last_date, count) VALUES (?, 'voice', ?, ?)", (uid, ld, count))
                
            # Migrate fame_streaks
            for uid, streak_data in data.get("fame_streaks", {}).items():
                ld = streak_data.get("last_date")
                count = streak_data.get("count", 0)
                c.execute("INSERT OR REPLACE INTO streaks (uid, type, last_date, count) VALUES (?, 'fame', ?, ?)", (uid, ld, count))
                
            # Migrate games
            for uid, user_games in data.get("games", {}).items():
                if isinstance(user_games, dict):
                    for game_name, time_sec in user_games.items():
                        c.execute("INSERT OR REPLACE INTO games (uid, game, time) VALUES (?, ?, ?)", (uid, game_name, float(time_sec)))
                        
            # Migrate history
            for date_str, time_sec in data.get("history", {}).items():
                c.execute("INSERT OR REPLACE INTO history (date_str, total_time) VALUES (?, ?)", (date_str, float(time_sec)))
                
            conn.commit()
            
        # Rename original to backup
        os.rename(config.STATS_FILE, backup_file)
        print("Migration complete!")
    except Exception as e:
        print(f"Error during migration: {e}")

def load_stats_sqlite():
    data = {"total": {}, "daily": {}, "games": {}, "streaks": {}, "fame_streaks": {}, "history": {}}
    try:
        with get_db() as conn:
            c = conn.cursor()
            
            for row in c.execute("SELECT * FROM voice_stats"):
                data["total"][row["uid"]] = row["total_time"]
                if row["daily_time"] > 0:
                    data["daily"][row["uid"]] = row["daily_time"]
                    
            for row in c.execute("SELECT * FROM streaks"):
                if row["type"] == "voice":
                    data["streaks"][row["uid"]] = {"last_date": row["last_date"], "count": row["count"]}
                elif row["type"] == "fame":
                    data["fame_streaks"][row["uid"]] = {"last_date": row["last_date"], "count": row["count"]}
                    
            for row in c.execute("SELECT * FROM games"):
                uid = row["uid"]
                if uid not in data["games"]:
                    data["games"][uid] = {}
                data["games"][uid][row["game"]] = row["time"]
                
            for row in c.execute("SELECT * FROM history"):
                data["history"][row["date_str"]] = row["total_time"]
                
        return data
    except Exception as e:
        print(f"ERROR load_stats_sqlite: {e}")
        return {"total": {}, "daily": {}, "games": {}, "streaks": {}, "fame_streaks": {}, "history": {}}

def save_stats_sqlite(data):
    try:
        with get_db() as conn:
            c = conn.cursor()
            
            # Voice stats
            total = data.get("total", {})
            daily = data.get("daily", {})
            all_uids = set(list(total.keys()) + list(daily.keys()))
            for uid in all_uids:
                t = float(total.get(uid, 0))
                d = float(daily.get(uid, 0))
                c.execute("INSERT OR REPLACE INTO voice_stats (uid, total_time, daily_time) VALUES (?, ?, ?)", (uid, t, d))
                
            # Streaks
            for uid, streak_data in data.get("streaks", {}).items():
                ld = streak_data.get("last_date")
                count = streak_data.get("count", 0)
                c.execute("INSERT OR REPLACE INTO streaks (uid, type, last_date, count) VALUES (?, 'voice', ?, ?)", (uid, ld, count))
                
            for uid, streak_data in data.get("fame_streaks", {}).items():
                ld = streak_data.get("last_date")
                count = streak_data.get("count", 0)
                c.execute("INSERT OR REPLACE INTO streaks (uid, type, last_date, count) VALUES (?, 'fame', ?, ?)", (uid, ld, count))
                
            # Games
            for uid, user_games in data.get("games", {}).items():
                if isinstance(user_games, dict):
                    for game_name, time_sec in user_games.items():
                        c.execute("INSERT OR REPLACE INTO games (uid, game, time) VALUES (?, ?, ?)", (uid, game_name, float(time_sec)))
                        
            # History
            # Delete old history that isn't in data anymore
            c.execute("DELETE FROM history")
            for date_str, time_sec in data.get("history", {}).items():
                c.execute("INSERT INTO history (date_str, total_time) VALUES (?, ?)", (date_str, float(time_sec)))
                
            conn.commit()
    except Exception as e:
        print(f"ERROR save_stats_sqlite: {e}")
