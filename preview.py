import asyncio
import sys
import os

# Patch env so faceit_api doesn't crash on import
os.environ.setdefault("FACEIT_API_KEY", "dummy")

from core.image_gen import generate_dashboard_banner, generate_active_players_banner

async def main():
    # Mock dashboard data
    top_players = [
        {"nickname": "FlliX32", "elo": 1722, "level": 8, "avatar": "", "stats_data": {"lifetime": {"Average K/D Ratio": "1.17", "Win Rate %": "51", "Recent Results": ["1","1","1","0","1"]}}},
        {"nickname": "LS-life", "elo": 1111, "level": 4, "avatar": "", "stats_data": {"lifetime": {"Average K/D Ratio": "1.09", "Win Rate %": "48", "Recent Results": ["0","0","1","0","0"]}}},
        {"nickname": "MrX2023", "elo": 930, "level": 3, "avatar": "", "stats_data": {"lifetime": {"Average K/D Ratio": "1.02", "Win Rate %": "46", "Recent Results": ["1","0","1","0","1"]}}},
        {"nickname": "ItsMa1ny", "elo": 884, "level": 2, "avatar": "", "stats_data": {"lifetime": {"Average K/D Ratio": "0.94", "Win Rate %": "47", "Recent Results": ["0","1","0","0","1"]}}},
    ]
    
    img_dash = await generate_dashboard_banner(top_players)
    with open("preview_dashboard.png", "wb") as f:
        f.write(img_dash.read())
    print("Saved preview_dashboard.png")

    # Mock LIVE data - 2 players in party + 1 player solo in another match
    active = [
        {
            "match_id": "abc123",
            "map": "de_mirage",
            "status": "ongoing",
            "score": "",
            "players": [
                {"nickname": "FlliX32", "avatar": "", "team": "Team Alpha", "elo": 1722, "level": 8},
                {"nickname": "MrX2023", "avatar": "", "team": "Team Alpha", "elo": 930, "level": 3},
            ]
        },
        {
            "match_id": "def456",
            "map": "de_inferno",
            "status": "voting",
            "score": "",
            "players": [
                {"nickname": "LS-life", "avatar": "", "team": "Team Beta", "elo": 1111, "level": 4},
                {"nickname": "ItsMa1ny", "avatar": "", "team": "Team Beta", "elo": 884, "level": 2},
            ]
        }
    ]
    
    img_live = await generate_active_players_banner(active)
    with open("preview_live.png", "wb") as f:
        f.write(img_live.read())
    print("Saved preview_live.png")

    # Mock LIVE empty
    img_empty = await generate_active_players_banner([])
    with open("preview_live_empty.png", "wb") as f:
        f.write(img_empty.read())
    print("Saved preview_live_empty.png")

asyncio.run(main())
