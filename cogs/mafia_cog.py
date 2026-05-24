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

    @discord.ui.button(label="Вийти", style=discord.ButtonStyle.gray, custom_id="leave_mafia")
    async def leave_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.game.remove_player(interaction.user.id):
            embed = interaction.message.embeds[0]
            players_text = "\n".join([f"- {p.display_name}" for p in self.game.get_alive_players()])
            if not players_text: players_text = "Немає гравців"
            embed.description = f"**Гравці ({len(self.game.players)}/10):**\n{players_text}"
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("Ви не приєднані до гри!", ephemeral=True)

    @discord.ui.button(label="Скасувати", style=discord.ButtonStyle.danger, custom_id="cancel_mafia")
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.game.creator_id and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Тільки творець або адмін може скасувати гру!", ephemeral=True)
            
        if interaction.guild.id in active_games:
            del active_games[interaction.guild.id]
        embed = discord.Embed(title="🛑 Гру скасовано", description="Збір гравців скасовано.", color=0xed4245)
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="Почати", style=discord.ButtonStyle.red, custom_id="start_mafia")
    async def start_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.game.creator_id:
            return await interaction.response.send_message("Тільки творець може почати гру!", ephemeral=True)
        if len(self.game.players) < 4:
            return await interaction.response.send_message("Мінімум 4 гравці!", ephemeral=True)

        await interaction.response.defer()

        self.game.assign_roles()
        
        # Mute everyone if they are in VC
        if interaction.user.voice and interaction.user.voice.channel:
            vc = interaction.user.voice.channel
            for p_id, p_info in self.game.players.items():
                member = vc.guild.get_member(p_id)
                if member and member in vc.members:
                    try: await member.edit(mute=True)
                    except: pass

        # Send DMs and change Nicknames
        for p_id, p_info in self.game.players.items():
            user = p_info["user"]
            role = p_info["role"]
            member = interaction.guild.get_member(p_id)
            if member:
                p_info["original_name"] = member.display_name
                try: await member.edit(nick=f"🕵️ {member.display_name}")
                except: pass
            try:
                await user.send(f"🕵️ Ваша роль у цій грі: **{role}**. Нікому не кажіть!")
            except: pass

        embed = discord.Embed(title="🌙 Ніч 1", description="Місто засинає. Мафія виходить на полювання...", color=0x2b2d31)
        await interaction.message.edit(embed=embed, view=None)
        
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

        options = []
        for p in self.game.get_alive_players():
            options.append(discord.SelectOption(label=p.display_name, value=str(p.id)))
            
        if options:
            select = discord.ui.Select(placeholder="Оберіть, кого стратити", options=options, custom_id="mafia_vote_select")
            select.callback = self.vote_callback
            self.add_item(select)

    async def vote_callback(self, interaction: discord.Interaction):
        if interaction.user.id not in self.game.players or not self.game.players[interaction.user.id]["alive"]:
            return await interaction.response.send_message("Тільки живі гравці можуть голосувати!", ephemeral=True)
            
        target_id = int(interaction.data["values"][0])
        self.game.day_votes[interaction.user.id] = target_id
        await interaction.response.send_message("Ваш голос зараховано!", ephemeral=True)

    @discord.ui.button(label="Завершити день", style=discord.ButtonStyle.blurple, custom_id="end_day")
    async def end_day_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in self.game.players or not self.game.players[interaction.user.id]["alive"]:
            return await interaction.response.send_message("Ви не живий гравець!", ephemeral=True)
            
        alive_players = self.game.get_alive_players()
        if len(self.game.day_votes) < len(alive_players):
            return await interaction.response.send_message(f"Ще не всі проголосували! ({len(self.game.day_votes)}/{len(alive_players)})", ephemeral=True)
            
        await interaction.response.defer()
        
        executed, event = self.game.process_day_votes()
        embed = interaction.message.embeds[0]
        
        win = self.game.check_win_condition()
        if win:
            embed.title = "🏆 Гра закінчена!"
            embed.description = event + f"\n\n**Перемогли: {win}**"
            await interaction.message.edit(embed=embed, view=None)
            
            # Restore names and unmute
            for p_id, p_info in self.game.players.items():
                member = interaction.guild.get_member(p_id)
                if member:
                    orig_name = p_info.get("original_name")
                    in_vc = member.voice and member.voice.channel
                    try: 
                        if in_vc: await member.edit(mute=False, nick=orig_name)
                        else: await member.edit(nick=orig_name)
                    except: pass
                    
            del active_games[interaction.guild.id]
            return
            
        # Якщо гра не закінчилася — починається НІЧ
        embed.title = f"🌙 Ніч {self.game.day_count + 1}"
        embed.description = event + "\n\nМісто знову засинає. Мафія виходить на полювання..."
        await interaction.message.edit(embed=embed, view=None)
        
        # Mute everyone for the night
        if interaction.user.voice and interaction.user.voice.channel:
            vc = interaction.user.voice.channel
            for p_id, p_info in self.game.players.items():
                if p_info["alive"]:
                    member = vc.guild.get_member(p_id)
                    if member and member in vc.members:
                        try: await member.edit(mute=True)
                        except: pass
                        
        await asyncio.sleep(15)
        
        night_events, dead = self.game.process_night()
        
        win = self.game.check_win_condition()
        if win:
            embed.title = "🏆 Гра закінчена!"
            embed.description = "\n".join(night_events) + f"\n\n**Перемогли: {win}**"
            await interaction.message.edit(embed=embed, view=None)
            
            # Restore names and unmute
            for p_id, p_info in self.game.players.items():
                member = interaction.guild.get_member(p_id)
                if member:
                    orig_name = p_info.get("original_name")
                    in_vc = member.voice and member.voice.channel
                    try: 
                        if in_vc: await member.edit(mute=False, nick=orig_name)
                        else: await member.edit(nick=orig_name)
                    except: pass
                    
            del active_games[interaction.guild.id]
            return
            
        # Якщо після ночі гра продовжується — починається ДЕНЬ
        if interaction.user.voice and interaction.user.voice.channel:
            vc = interaction.user.voice.channel
            for p_id, p_info in self.game.players.items():
                if p_info["alive"]:
                    member = vc.guild.get_member(p_id)
                    if member and member in vc.members:
                        try: await member.edit(mute=False)
                        except: pass

        embed.title = f"☀️ День {self.game.day_count}"
        embed.description = "\n".join(night_events) + "\n\nЧас обговорити та проголосувати!"
        await interaction.message.edit(embed=embed, view=VoteView(self.game))

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

    @app_commands.command(name="mafia_stop", description="Екстрено завершити поточну гру Мафії")
    async def mafia_stop(self, interaction: discord.Interaction):
        if interaction.guild.id not in active_games:
            return await interaction.response.send_message("Зараз немає активної гри на сервері.", ephemeral=True)
            
        game = active_games[interaction.guild.id]
        if interaction.user.id != game.creator_id and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Тільки творець гри або адмін може її зупинити!", ephemeral=True)
            
        # Розмучуємо всіх і повертаємо нікнейми
        for p_id, p_info in game.players.items():
            member = interaction.guild.get_member(p_id)
            if member:
                orig = p_info.get("original_name")
                in_vc = member.voice and member.voice.channel
                try: 
                    if in_vc: await member.edit(mute=False, nick=orig)
                    else: await member.edit(nick=orig)
                except: pass
                    
        del active_games[interaction.guild.id]
        await interaction.response.send_message("🛑 **Гру екстрено завершено.** Усім гравцям повернено мікрофони та нікнейми.")

async def setup(bot):
    await bot.add_cog(MafiaCog(bot))
