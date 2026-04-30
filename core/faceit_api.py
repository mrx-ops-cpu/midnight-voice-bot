import aiohttp
import os

FACEIT_API_KEY = os.environ.get("FACEIT_API_KEY")
HEADERS = {"Authorization": f"Bearer {FACEIT_API_KEY}"} if FACEIT_API_KEY else {}
BASE_URL = "https://open.faceit.com/data/v4"

async def get_profile(nickname: str) -> dict:
    if not FACEIT_API_KEY:
        return {"elo": "N/A", "level": "N/A", "kd": "N/A", "winrate": "N/A"}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/players?nickname={nickname}", headers=HEADERS) as resp:
            if resp.status != 200:
                return {"elo": "N/A", "level": "N/A", "kd": "N/A", "winrate": "N/A"}
            
            data = await resp.json()
            player_id = data.get("player_id")
            games = data.get("games", {})
            cs2_data = games.get("cs2", games.get("csgo", {}))
            elo = cs2_data.get("faceit_elo", "N/A")
            level = cs2_data.get("skill_level", "N/A")
            
        async with session.get(f"{BASE_URL}/players/{player_id}/stats/cs2", headers=HEADERS) as stats_resp:
            if stats_resp.status != 200:
                return {"elo": elo, "level": level, "kd": "N/A", "winrate": "N/A"}
            
            stats_data = await stats_resp.json()
            lifetime = stats_data.get("lifetime", {})
            
            return {
                "elo": elo,
                "level": level,
                "kd": lifetime.get("Average K/D Ratio", "N/A"),
                "winrate": lifetime.get("Win Rate %", "N/A")
            }

async def get_last_match(nickname: str) -> dict:
    if not FACEIT_API_KEY:
        return {"score": "N/A", "kd": "N/A", "elo_diff": "N/A"}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/players?nickname={nickname}", headers=HEADERS) as resp:
            if resp.status != 200:
                return {"score": "N/A", "kd": "N/A", "elo_diff": "N/A"}
            
            data = await resp.json()
            player_id = data.get("player_id")

        async with session.get(f"{BASE_URL}/players/{player_id}/history?game=cs2&offset=0&limit=1", headers=HEADERS) as hist_resp:
            if hist_resp.status != 200:
                return {"score": "N/A", "kd": "N/A", "elo_diff": "N/A"}
            
            hist_data = await hist_resp.json()
            items = hist_data.get("items", [])
            
            if not items:
                return {"score": "N/A", "kd": "N/A", "elo_diff": "N/A"}
            
            match_id = items[0].get("match_id")

        async with session.get(f"{BASE_URL}/matches/{match_id}/stats", headers=HEADERS) as stats_resp:
            if stats_resp.status != 200:
                return {"score": "N/A", "kd": "N/A", "elo_diff": "N/A"}
            
            match_stats = await stats_resp.json()
            rounds = match_stats.get("rounds", [])
            
            if not rounds:
                return {"score": "N/A", "kd": "N/A", "elo_diff": "N/A"}
            
            round_data = rounds[0]
            score = round_data.get("round_stats", {}).get("Score", "N/A")
            
            player_kd = "N/A"
            for team in round_data.get("teams", []):
                for player in team.get("players", []):
                    if player.get("player_id") == player_id:
                        player_kd = player.get("player_stats", {}).get("K/D Ratio", "N/A")
                        break
            
            return {
                "score": score,
                "kd": player_kd,
                "elo_diff": "N/A" 
            }