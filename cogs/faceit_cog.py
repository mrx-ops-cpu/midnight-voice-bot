import discord
from discord.ext import commands, tasks
from discord import app_commands
import io
import time

from core import database, config
from core.faceit_api import FaceitAPI
from core.image_gen import generate_dashboard_banner, generate_profile_card, generate_compare_card, generate_active_players_banner

class CompareSelect(discord.ui.Select):
    def __init__(self, bot, author_id, author_nickname):
        self.bot = bot
        self.api = FaceitAPI()
        self.author_id = author_id
        self.author_nickname = author_nickname
        
        users = database.load_faceit_users()
        options = []
        for uid, nick in users.items():
            if str(uid) != str(author_id):
                options.append(discord.SelectOption(label=nick, description="Порівняти з " + nick, value=nick))
                
        if not options:
            options.append(discord.SelectOption(label="Немає інших гравців", value="none"))
            
        super().__init__(placeholder="Оберіть гравця для порівняння...", options=options[:25])

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            return await interaction.response.send_message("❌ На сервері більше немає прив'язаних гравців.", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        target_nick = self.values[0]
        
        # Завантажуємо дані автора
        p1_data = await self.api.get_player_by_nickname(self.author_nickname)
        p1_stats = await self.api.get_player_stats(p1_data.get("player_id")) if p1_data and 'error' not in p1_data else {}
        
        # Завантажуємо дані цілі
        p2_data = await self.api.get_player_by_nickname(target_nick)
        p2_stats = await self.api.get_player_stats(p2_data.get("player_id")) if p2_data and 'error' not in p2_data else {}
        
        img_bytes = await generate_compare_card(self.author_nickname, p1_data, p1_stats, target_nick, p2_data, p2_stats)
        file = discord.File(fp=img_bytes, filename="compare.png")
        
        await interaction.followup.send(file=file, ephemeral=True)


class CompareView(discord.ui.View):
    def __init__(self, bot, author_id, author_nickname):
        super().__init__(timeout=60)
        self.add_item(CompareSelect(bot, author_id, author_nickname))


class FaceitButtons(discord.ui.View):
    def __init__(self, bot, cog):
        super().__init__(timeout=None)
        self.bot = bot
        self.cog = cog
        self.api = FaceitAPI()

    @discord.ui.button(label="Мій Профіль", style=discord.ButtonStyle.primary, custom_id="faceit_btn_profile")
    async def btn_profile(self, interaction: discord.Interaction, button: discord.ui.Button):
        users = database.load_faceit_users()
        nickname = users.get(str(interaction.user.id))
        
        if not nickname:
            return await interaction.response.send_message("❌ Ви ще не прив'язали акаунт! Використайте `/faceit_link`.", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        player_data = await self.api.get_player_by_nickname(nickname)
        if not player_data or 'error' in player_data:
            return await interaction.followup.send("❌ Помилка завантаження профілю.", ephemeral=True)
            
        player_id = player_data.get("player_id")
        stats_data = await self.api.get_player_stats(player_id)
        
        match_stats_str = "Немає інформації про останній матч."
        history = await self.api.get_player_history(player_id, limit=1)
        if history and "items" in history and history["items"]:
            last_match = history["items"][0]
            match_id = last_match.get("match_id")
            detailed = await self.api.get_match_stats(match_id)
            if detailed and "rounds" in detailed and detailed["rounds"]:
                rnd = detailed["rounds"][0]
                map_name = rnd.get("round_stats", {}).get("Map", "Unknown")
                score = rnd.get("round_stats", {}).get("Score", "")
                
                teams = rnd.get("teams", [])
                for team in teams:
                    for p in team.get("players", []):
                        if p.get("player_id") == player_id:
                            p_stats = p.get("player_stats", {})
                            kills = p_stats.get("Kills", "0")
                            deaths = p_stats.get("Deaths", "0")
                            kd = p_stats.get("K/D Ratio", "0")
                            hs = p_stats.get("Headshots %", "0")
                            res = "Перемога" if p_stats.get("Result") == "1" else "Поразка"
                            match_stats_str = f"{res} на {map_name} [{score}]\nKills: {kills} | Deaths: {deaths} | K/D: {kd} | HS: {hs}%"
                            break

        img_bytes = await generate_profile_card(nickname, player_data, stats_data, match_stats_str)
        file = discord.File(fp=img_bytes, filename="profile.png")
        
        await interaction.followup.send(file=file, ephemeral=True)

    @discord.ui.button(label="Порівняти", style=discord.ButtonStyle.secondary, custom_id="faceit_btn_compare")
    async def btn_compare(self, interaction: discord.Interaction, button: discord.ui.Button):
        users = database.load_faceit_users()
        nickname = users.get(str(interaction.user.id))
        if not nickname:
            return await interaction.response.send_message("❌ Ви ще не прив'язали акаунт! Використайте `/faceit_link`.", ephemeral=True)
            
        view = CompareView(self.bot, interaction.user.id, nickname)
        await interaction.response.send_message("👥 Оберіть гравця для порівняння:", view=view, ephemeral=True)

    @discord.ui.button(label="Оновити Дашборд", style=discord.ButtonStyle.secondary, custom_id="faceit_btn_refresh")
    async def btn_refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.cog.update_dashboard()


class FaceitCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api = FaceitAPI()
        self.dashboard_task.start()
        self.live_task.start()

    def cog_unload(self):
        self.dashboard_task.cancel()
        self.live_task.cancel()

    @app_commands.command(name="faceit_link", description="Прив'язати свій FaceIT акаунт")
    @app_commands.describe(nickname="Ваш нікнейм на FaceIT")
    async def faceit_link(self, interaction: discord.Interaction, nickname: str):
        await interaction.response.defer(ephemeral=True)
        
        player_data = await self.api.get_player_by_nickname(nickname)
        if not player_data or 'error' in player_data:
            return await interaction.followup.send(f"❌ Гравець `{nickname}` не знайдений на FaceIT!", ephemeral=True)
            
        users = database.load_faceit_users()
        users[str(interaction.user.id)] = nickname
        database.save_faceit_users(users)
        
        await interaction.followup.send(f"✅ Ваш акаунт успішно прив'язано до **{nickname}**!", ephemeral=True)
        await self.update_dashboard()

    @app_commands.command(name="faceit_unlink", description="[АДМІН] Видалити гравця з FaceIT дашборду")
    @app_commands.describe(user="Користувач Discord, якого треба відв'язати")
    async def faceit_unlink(self, interaction: discord.Interaction, user: discord.Member):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Тільки адмін може це зробити!", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        users = database.load_faceit_users()
        uid_str = str(user.id)
        
        if uid_str in users:
            nickname = users.pop(uid_str)
            database.save_faceit_users(users)
            await interaction.followup.send(f"✅ Користувача {user.mention} (FaceIT: **{nickname}**) успішно відв'язано!", ephemeral=True)
            await self.update_dashboard()
        else:
            await interaction.followup.send(f"❌ Користувач {user.mention} не має прив'язаного FaceIT акаунта.", ephemeral=True)

    @app_commands.command(name="faceit_remove_nick", description="[АДМІН] Видалити гравця за нікнеймом FaceIT")
    @app_commands.describe(nickname="Нікнейм на FaceIT")
    async def faceit_remove_nick(self, interaction: discord.Interaction, nickname: str):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Тільки адмін може це зробити!", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        users = database.load_faceit_users()
        
        found_uid = None
        for uid, nick in users.items():
            if nick.lower() == nickname.lower():
                found_uid = uid
                break
                
        if found_uid:
            del users[found_uid]
            database.save_faceit_users(users)
            await interaction.followup.send(f"✅ Нікнейм **{nickname}** успішно видалено з бази!", ephemeral=True)
            await self.update_dashboard()
        else:
            await interaction.followup.send(f"❌ Нікнейм **{nickname}** не знайдено в базі.", ephemeral=True)

    @app_commands.command(name="setfaceitchannel", description="[АДМІН] Обрати канал для FaceIT Dashboard")
    @app_commands.describe(channel="Текстовий канал")
    async def setfaceitchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Тільки адмін може це зробити!", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        
        msg_top = await channel.send("⏳ Генерую Дашборд...")
        msg_live = await channel.send("⏳ Завантаження активних матчів...")
        
        dash_data = {
            "channel_id": channel.id,
            "msg_top_id": msg_top.id,
            "msg_live_id": msg_live.id
        }
        database.save_faceit_dashboard(dash_data)
        
        await interaction.followup.send(f"✅ FaceIT Dashboard успішно встановлено в {channel.mention}!", ephemeral=True)
        await self.update_dashboard()
        await self.update_live()

    @tasks.loop(minutes=10)
    async def dashboard_task(self):
        await self.update_dashboard()

    @dashboard_task.before_loop
    async def before_dashboard_task(self):
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=2)
    async def live_task(self):
        await self.update_live()

    @live_task.before_loop
    async def before_live_task(self):
        await self.bot.wait_until_ready()

    async def update_dashboard(self):
        dash_data = database.load_faceit_dashboard()
        if not dash_data: return
        
        channel_id = dash_data.get("channel_id")
        msg_top_id = dash_data.get("msg_top_id")
        
        if not channel_id or not msg_top_id: return
        channel = self.bot.get_channel(channel_id)
        if not channel: return
        
        users = database.load_faceit_users()
        if not users: return
        
        top_players = []
        
        for uid, nickname in users.items():
            player_data = await self.api.get_player_by_nickname(nickname)
            if player_data and 'error' not in player_data:
                player_id = player_data.get("player_id")
                games = player_data.get("games", {})
                cs2 = games.get("cs2", {})
                elo = cs2.get("faceit_elo", 0)
                level = cs2.get("skill_level", 1)
                
                stats_data = await self.api.get_player_stats(player_id)
                
                top_players.append({
                    "nickname": nickname,
                    "elo": elo,
                    "level": level,
                    "stats_data": stats_data,
                    "avatar": player_data.get("avatar", "")
                })
        
        top_players = sorted(top_players, key=lambda x: x["elo"], reverse=True)[:10]
        
        img_top = await generate_dashboard_banner(top_players)
        
        try:
            msg_top = await channel.fetch_message(msg_top_id)
            file_top = discord.File(fp=img_top, filename="dashboard.png")
            await msg_top.edit(content="", attachments=[file_top], view=FaceitButtons(self.bot, self))
        except Exception as e:
            print(f"FaceIT top edit error: {e}")

    async def update_live(self):
        dash_data = database.load_faceit_dashboard()
        if not dash_data: return
        
        channel_id = dash_data.get("channel_id")
        msg_live_id = dash_data.get("msg_live_id")
        
        if not channel_id or not msg_live_id: return
        channel = self.bot.get_channel(channel_id)
        if not channel: return
        
        users = database.load_faceit_users()
        if not users: return
        
        # Collect player IDs and their data
        player_map = {}  # player_id -> {nickname, avatar, elo, level}
        for uid, nickname in users.items():
            player_data = await self.api.get_player_by_nickname(nickname)
            if player_data and 'error' not in player_data:
                pid = player_data.get("player_id")
                games = player_data.get("games", {})
                cs2 = games.get("cs2", {})
                player_map[pid] = {
                    "nickname": nickname,
                    "avatar": player_data.get("avatar", ""),
                    "elo": cs2.get("faceit_elo", 0),
                    "level": cs2.get("skill_level", 1)
                }
        
        # Check each player's latest match
        active_match_ids = {}  # match_id -> list of our player_ids in that match
        for pid in player_map:
            history = await self.api.get_player_history(pid, limit=1)
            if history and "items" in history and history["items"]:
                last_match = history["items"][0]
                match_id = last_match.get("match_id")
                status = last_match.get("status", "").lower()
                
                # Check if the match is not finished
                finished_at = last_match.get("finished_at", 0)
                started_at = last_match.get("started_at", 0)
                
                now_ts = int(time.time())
                
                # Match is active if status is not finished, or if it started recently and has no finish time
                is_active = False
                if status in ("ongoing", "ready", "configuring", "voting", "captain_pick"):
                    is_active = True
                elif status != "finished" and finished_at == 0 and started_at > 0:
                    is_active = True
                
                if is_active:
                    if match_id not in active_match_ids:
                        active_match_ids[match_id] = []
                    active_match_ids[match_id].append(pid)
        
        # Build match details for active matches
        active_matches = []
        for match_id, pids in active_match_ids.items():
            match_details = await self.api.get_match_details(match_id)
            if not match_details or match_details.get("error"):
                continue
            
            map_name = "Unknown"
            voting = match_details.get("voting", {})
            if voting and "map" in voting and "pick" in voting["map"]:
                picks = voting["map"]["pick"]
                if picks:
                    map_name = picks[0] if isinstance(picks, list) else str(picks)
            
            configured = match_details.get("configured_at", 0)
            status = match_details.get("status", "unknown")
            
            # Find which team our players are on
            players_info = []
            teams = match_details.get("teams", {})
            for faction_key, faction in teams.items():
                team_name = faction.get("name", faction_key)
                roster = faction.get("roster", [])
                for r in roster:
                    rpid = r.get("player_id", "")
                    if rpid in pids:
                        pdata = player_map.get(rpid, {})
                        players_info.append({
                            "nickname": pdata.get("nickname", "Unknown"),
                            "avatar": pdata.get("avatar", ""),
                            "team": team_name,
                            "elo": pdata.get("elo", 0),
                            "level": pdata.get("level", 1)
                        })
            
            active_matches.append({
                "match_id": match_id,
                "map": map_name,
                "status": status,
                "score": "",
                "players": players_info
            })
        
        # Generate image
        img_live = await generate_active_players_banner(active_matches)
        
        try:
            msg_live = await channel.fetch_message(msg_live_id)
            file_live = discord.File(fp=img_live, filename="live.png")
            await msg_live.edit(content="", attachments=[file_live])
        except Exception as e:
            print(f"FaceIT live edit error: {e}")


async def setup(bot):
    await bot.add_cog(FaceitCog(bot))
