import aiohttp
import os

class FaceitAPI:
    def __init__(self):
        self.api_key = os.environ.get("FACEIT_API_KEY")
        self.base_url = "https://open.faceit.com/data/v4"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        }

    async def _get(self, endpoint, params=None):
        if not self.api_key:
            print("ERROR: FACEIT_API_KEY is not set.")
            return None
        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(f"{self.base_url}{endpoint}", params=params) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    elif resp.status == 404:
                        return {"error": "Not found"}
                    else:
                        print(f"FaceIT API error: {resp.status} - {await resp.text()}")
                        return None
        except Exception as e:
            print(f"FaceIT API exception: {e}")
            return None

    async def get_player_by_nickname(self, nickname):
        return await self._get("/players", params={"nickname": nickname})

    async def get_player_stats(self, player_id):
        return await self._get(f"/players/{player_id}/stats/cs2")

    async def get_player_history(self, player_id, limit=5):
        return await self._get(f"/players/{player_id}/history", params={"game": "cs2", "offset": 0, "limit": limit})
