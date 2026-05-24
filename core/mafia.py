import random

class Role:
    MAFIA = "Мафія"
    CITIZEN = "Мирний житель"
    DOCTOR = "Лікар"
    SHERIFF = "Комісар"

class MafiaGame:
    def __init__(self, guild_id, channel_id, creator_id):
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.creator_id = creator_id
        self.players = {} # user_id -> {"user": discord.Member, "role": str, "alive": bool, "original_name": str}
        self.state = "LOBBY" # LOBBY, NIGHT, DAY
        self.day_count = 0
        
        # Actions for the current night
        self.night_actions = {
            "kill": None,
            "heal": None,
            "check": None
        }
        
        # Track how many night actions we're waiting for
        self.night_actions_received = 0
        self.night_actions_expected = 0
        self.night_event = None  # asyncio.Event to signal night is done
        
        self.day_votes = {} # user_id -> voted_for_user_id
        
        self.main_message_id = None

    def add_player(self, user):
        if user.id not in self.players:
            self.players[user.id] = {"user": user, "role": None, "alive": True}
            return True
        return False

    def remove_player(self, user_id):
        if user_id in self.players:
            del self.players[user_id]
            return True
        return False

    def assign_roles(self):
        player_ids = list(self.players.keys())
        random.shuffle(player_ids)
        count = len(player_ids)
        
        # 2 мафії тільки від 10 гравців
        mafia_count = 2 if count >= 10 else 1
        doctor_count = 1
        sheriff_count = 1 if count >= 5 else 0
        
        roles = []
        roles.extend([Role.MAFIA] * mafia_count)
        roles.extend([Role.DOCTOR] * doctor_count)
        roles.extend([Role.SHERIFF] * sheriff_count)
        
        while len(roles) < count:
            roles.append(Role.CITIZEN)
            
        random.shuffle(roles)
        for pid, role in zip(player_ids, roles):
            self.players[pid]["role"] = role

    def get_alive_players(self):
        return [p["user"] for p in self.players.values() if p["alive"]]

    def get_players_by_role(self, role):
        return [p_id for p_id, p in self.players.items() if p["role"] == role and p["alive"]]

    def count_expected_night_actions(self):
        """Count how many night actions we expect (mafia + doctor + sheriff if alive)."""
        count = 0
        for p in self.players.values():
            if not p["alive"]:
                continue
            if p["role"] in (Role.MAFIA, Role.DOCTOR, Role.SHERIFF):
                count += 1
        return count

    def check_win_condition(self):
        alive = [p for p in self.players.values() if p["alive"]]
        mafia_alive = [p for p in alive if p["role"] == Role.MAFIA]
        citizens_alive = [p for p in alive if p["role"] != Role.MAFIA]
        
        if len(mafia_alive) == 0:
            return "МИРНІ ЖИТЕЛІ 🏘️"
        if len(mafia_alive) >= len(citizens_alive):
            return "МАФІЯ 🔫"
        return None

    def process_night(self):
        self.day_count += 1
        killed_id = self.night_actions.get("kill")
        healed_id = self.night_actions.get("heal")
        
        events = []
        dead_person = None
        
        if self.day_count == 1:
            # Перша ніч — ніч знайомств, ніхто не гине
            events.append("🌙 Перша ніч — ніч знайомств. Мафія лише придивляється до своїх жертв, ніхто не гине.")
        else:
            if killed_id:
                if killed_id != healed_id:
                    self.players[killed_id]["alive"] = False
                    user = self.players[killed_id]["user"]
                    role = self.players[killed_id]["role"]
                    dead_person = killed_id
                    events.append(f"💀 Вночі мафія безжалісно вбила **{user.display_name}**. Його роль була: **{role}**.")
                else:
                    events.append("💉 Вночі мафія стріляла, але Лікар майстерно врятував жертву! Ніхто не помер.")
            else:
                events.append("😴 Тиха ніч. Мафія вирішила нікого не вбивати (або проспала).")
            
        self.night_actions = {"kill": None, "heal": None, "check": None}
        self.night_actions_received = 0
        return events, dead_person

    def process_day_votes(self):
        if not self.day_votes:
            return None, "Ніхто не проголосував. Усі розійшлися по домівках."
            
        vote_counts = {}
        for target in self.day_votes.values():
            vote_counts[target] = vote_counts.get(target, 0) + 1
            
        max_votes = max(vote_counts.values())
        candidates = [t for t, c in vote_counts.items() if c == max_votes]
        
        if len(candidates) > 1:
            self.day_votes = {}
            return None, "⚖️ Голоси розділилися порівну! Суд зайшов у глухий кут, нікого не стратили."
            
        executed_id = candidates[0]
        self.players[executed_id]["alive"] = False
        user = self.players[executed_id]["user"]
        role = self.players[executed_id]["role"]
        
        self.day_votes = {}
        return executed_id, f"⚖️ Місто проголосувало! На шибеницю відправляється **{user.display_name}**. Після перевірки документів виявилося, що це **{role}**."
