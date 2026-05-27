import discord
from discord.ext import commands, tasks
from discord import app_commands
import io

from core import database, config
from core.faceit_api import FaceitAPI
from core.image_gen import generate_top_banner, generate_active_matches_banner, generate_profile_card

class FaceitButtons(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot
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
        
        img_bytes = await generate_profile_card(nickname, player_data, stats_data)
        file = discord.File(fp=img_bytes, filename="profile.png")
        
        await interaction.followup.send(file=file, ephemeral=True)


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
        
        # Відправляємо два стартових повідомлення
        msg_top = await channel.send("⏳ Генерую ТОП гравців...")
        msg_active = await channel.send("⏳ Генерую Активні матчі...")
        
        dash_data = {
            "channel_id": channel.id,
            "msg_top_id": msg_top.id,
            "msg_active_id": msg_active.id
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
        msg_active_id = dash_data.get("msg_active_id")
        
        if not channel_id: return
        channel = self.bot.get_channel(channel_id)
        if not channel: return
        
        users = database.load_faceit_users()
        if not users: return
        
        top_players = []
        active_matches = []
        
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
                
                # Check recent history for match
                player_id = player_data.get("player_id")
                history = await self.api.get_player_history(player_id, limit=1)
                if history and "items" in history and history["items"]:
                    last_match = history["items"][0]
                    # We approximate ongoing match if status is somehow not CANCELLED or FINISHED, 
                    # but usually history only shows finished. We will just show last match status.
                    status = last_match.get("status", "UNKNOWN")
                    # If it's finished, maybe we ignore it for "active", but let's show recent if no active
                    active_matches.append({
                        "nickname": nickname,
                        "match_status": status
                    })
        
        # Sort top players
        top_players = sorted(top_players, key=lambda x: x["elo"], reverse=True)[:10]
        
        # Generate images
        img_top = await generate_top_banner(top_players)
        img_active = await generate_active_matches_banner(active_matches[:5])
        
        try:
            msg_top = await channel.fetch_message(msg_top_id)
            file_top = discord.File(fp=img_top, filename="top.png")
            await msg_top.edit(content="", attachments=[file_top])
        except Exception as e:
            print(f"FaceIT top edit error: {e}")
            
        try:
            msg_active = await channel.fetch_message(msg_active_id)
            file_active = discord.File(fp=img_active, filename="active.png")
            await msg_active.edit(content="", attachments=[file_active], view=FaceitButtons(self.bot))
        except Exception as e:
            print(f"FaceIT active edit error: {e}")


async def setup(bot):
    await bot.add_cog(FaceitCog(bot))
    bot.add_view(FaceitButtons(bot))
