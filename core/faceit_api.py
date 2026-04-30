async def get_profile(nickname: str) -> dict:
    return {
        "elo": 2150,
        "level": 10,
        "kd": 1.25,
        "winrate": 55
    }

async def get_last_match(nickname: str) -> dict:
    return {
        "score": "13-10",
        "kd": 1.45,
        "elo_diff": "+25"
    }