import discord
from discord.ext import commands, tasks
from discord import app_commands
import io

from core import database, config
from core.faceit_api import FaceitAPI
from core.image_gen import generate_dashboard_banner, generate_profile_card

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
        
        # Отримуємо детальну статистику останнього матчу
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
                            res = "✅ Перемога" if p_stats.get("Result") == "1" else "❌ Поразка"
                            match_stats_str = f"{res} на {map_name} [{score}]\nKills: {kills} | Deaths: {deaths} | K/D: {kd} | HS: {hs}%"
                            break

        img_bytes = await generate_profile_card(nickname, player_data, stats_data, match_stats_str)
        file = discord.File(fp=img_bytes, filename="profile.png")
        
        await interaction.followup.send(file=file, ephemeral=True)

    @discord.ui.button(label="Оновити Дашборд", style=discord.ButtonStyle.secondary, custom_id="faceit_btn_refresh")
    async def btn_refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await self.cog.update_dashboard()
        await interaction.followup.send("✅ Дашборд оновлено!", ephemeral=True)


class FaceitCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api = FaceitAPI()
        self.dashboard_task.start()

    def cog_unload(self):
        self.dashboard_task.cancel()

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

    @app_commands.command(name="setfaceitchannel", description="[АДМІН] Обрати канал для FaceIT Dashboard")
    @app_commands.describe(channel="Текстовий канал")
    async def setfaceitchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Тільки адмін може це зробити!", ephemeral=True)
            
        await interaction.response.defer(ephemeral=True)
        
        msg_top = await channel.send("⏳ Генерую Дашборд...")
        
        dash_data = {
            "channel_id": channel.id,
            "msg_top_id": msg_top.id
        }
        database.save_faceit_dashboard(dash_data)
        
        await interaction.followup.send(f"✅ FaceIT Dashboard успішно встановлено в {channel.mention}!", ephemeral=True)
        await self.update_dashboard()

    @tasks.loop(minutes=10)
    async def dashboard_task(self):
        await self.update_dashboard()

    @dashboard_task.before_loop
    async def before_dashboard_task(self):
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
                games = player_data.get("games", {})
                cs2 = games.get("cs2", {})
                elo = cs2.get("faceit_elo", 0)
                level = cs2.get("skill_level", 1)
                
                top_players.append({
                    "nickname": nickname,
                    "elo": elo,
                    "level": level
                })
        
        # Sort top players
        top_players = sorted(top_players, key=lambda x: x["elo"], reverse=True)[:10]
        
        # Generate image
        img_top = await generate_dashboard_banner(top_players)
        
        try:
            msg_top = await channel.fetch_message(msg_top_id)
            file_top = discord.File(fp=img_top, filename="dashboard.png")
            await msg_top.edit(content="", attachments=[file_top], view=FaceitButtons(self.bot, self))
        except Exception as e:
            print(f"FaceIT top edit error: {e}")


async def setup(bot):
    await bot.add_cog(FaceitCog(bot))
