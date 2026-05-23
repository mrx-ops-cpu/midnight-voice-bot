import discord
from discord.ext import commands
from discord import app_commands
import asyncio

from core.mafia import MafiaGame, Role
from core import database

active_games = {} # guild_id -> MafiaGame

class JoinView(discord.ui.View):
    def __init__(self, game):
        super().__init__(timeout=None)
        self.game = game

    @discord.ui.button(label="Приєднатися", style=discord.ButtonStyle.green, custom_id="join_mafia")
    async def join_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.game.add_player(interaction.user):
            embed = interaction.message.embeds[0]
            players_text = "\n".join([f"- {p.display_name}" for p in self.game.get_alive_players()])
            embed.description = f"**Гравці ({len(self.game.players)}/10):**\n{players_text}"
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("Ви вже у грі!", ephemeral=True)

    @discord.ui.button(label="Почати", style=discord.ButtonStyle.red, custom_id="start_mafia")
    async def start_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.game.creator_id:
            return await interaction.response.send_message("Тільки творець може почати гру!", ephemeral=True)
        if len(self.game.players) < 4:
            return await interaction.response.send_message("Мінімум 4 гравці!", ephemeral=True)

        self.game.assign_roles()
        
        # Mute everyone if they are in VC
        if interaction.user.voice and interaction.user.voice.channel:
            vc = interaction.user.voice.channel
            for p_id, p_info in self.game.players.items():
                member = vc.guild.get_member(p_id)
                if member and member in vc.members:
                    try: await member.edit(mute=True)
                    except: pass

        # Send DMs
        for p_id, p_info in self.game.players.items():
            user = p_info["user"]
            role = p_info["role"]
            try:
                await user.send(f"🕵️ Ваша роль у цій грі: **{role}**. Нікому не кажіть!")
            except: pass

        embed = discord.Embed(title="🌙 Ніч 1", description="Місто засинає. Мафія виходить на полювання...", color=0x2b2d31)
        await interaction.response.edit_message(embed=embed, view=None)
        
        # Wait for night actions (Simplified: just wait 15 seconds for now)
        await asyncio.sleep(15)
        
        events, dead = self.game.process_night()
        
        # Unmute
        if interaction.user.voice and interaction.user.voice.channel:
            vc = interaction.user.voice.channel
            for p_id, p_info in self.game.players.items():
                if p_info["alive"]:
                    member = vc.guild.get_member(p_id)
                    if member and member in vc.members:
                        try: await member.edit(mute=False)
                        except: pass

        embed = discord.Embed(title="☀️ День 1", description="\n".join(events) + "\n\nЧас обговорити та проголосувати!", color=0x2b2d31)
        await interaction.message.edit(embed=embed, view=VoteView(self.game))

class VoteView(discord.ui.View):
    def __init__(self, game):
        super().__init__(timeout=None)
        self.game = game
        self.voted = set()

    @discord.ui.button(label="Завершити день", style=discord.ButtonStyle.blurple, custom_id="end_day")
    async def end_day_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in self.game.players or not self.game.players[interaction.user.id]["alive"]:
            return await interaction.response.send_message("Ви не живий гравець!", ephemeral=True)
            
        executed, event = self.game.process_day_votes()
        embed = interaction.message.embeds[0]
        embed.title = "🌙 Наступна ніч"
        embed.description = event + "\n\nМісто знову засинає..."
        
        win = self.game.check_win_condition()
        if win:
            embed.title = "🏆 Гра закінчена!"
            embed.description += f"\n\n**Перемогли: {win}**"
            await interaction.response.edit_message(embed=embed, view=None)
            del active_games[interaction.guild.id]
        else:
            await interaction.response.edit_message(embed=embed, view=None)

class MafiaCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="mafia", description="Створити кімнату для гри в Мафію")
    async def mafia(self, interaction: discord.Interaction):
        if interaction.guild.id in active_games:
            return await interaction.response.send_message("Гра вже йде на цьому сервері!", ephemeral=True)
            
        game = MafiaGame(interaction.guild.id, interaction.channel_id, interaction.user.id)
        active_games[interaction.guild.id] = game
        
        embed = discord.Embed(title="🕵️ Збираємось на Мафію!", description="Натисніть кнопку, щоб приєднатися.", color=0x2b2d31)
        await interaction.response.send_message(embed=embed, view=JoinView(game))

    @app_commands.command(name="mafia_stats", description="Подивитися свою статистику в грі Мафія")
    async def mafia_stats(self, interaction: discord.Interaction):
        stats = database.load_mafia_stats()
        user_id = str(interaction.user.id)
        
        if user_id not in stats:
            return await interaction.response.send_message("Ви ще не грали в Мафію!", ephemeral=True)
            
        user_stats = stats[user_id]
        games_played = user_stats.get("games_played", 0)
        wins = user_stats.get("wins", 0)
        winrate = round((wins / games_played * 100) if games_played > 0 else 0, 1)
        
        embed = discord.Embed(title=f"📊 Статистика Мафії: {interaction.user.display_name}", color=0x2b2d31)
        embed.add_field(name="Зіграно ігор", value=str(games_played), inline=True)
        embed.add_field(name="Перемог", value=str(wins), inline=True)
        embed.add_field(name="Вінрейт", value=f"{winrate}%", inline=True)
        
        roles_text = ""
        for role, count in user_stats.get("roles", {}).items():
            roles_text += f"**{role}:** {count} разів\n"
            
        if roles_text:
            embed.add_field(name="Улюблені ролі", value=roles_text, inline=False)
            
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="mafia_top", description="Топ-10 найкращих гравців у Мафію")
    async def mafia_top(self, interaction: discord.Interaction):
        stats = database.load_mafia_stats()
        if not stats:
            return await interaction.response.send_message("Ще ніхто не грав у Мафію!", ephemeral=True)
            
        sorted_players = sorted(stats.items(), key=lambda x: x[1].get("wins", 0), reverse=True)[:10]
        
        embed = discord.Embed(title="🏆 Топ-10 гравців у Мафію", color=0xffd700)
        
        for i, (uid, data) in enumerate(sorted_players, 1):
            wins = data.get("wins", 0)
            games = data.get("games_played", 0)
            member = interaction.guild.get_member(int(uid))
            name = member.display_name if member else f"Гравець {uid}"
            
            embed.add_field(name=f"{i}. {name}", value=f"Перемог: **{wins}** (Ігор: {games})", inline=False)
            
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(MafiaCog(bot))
