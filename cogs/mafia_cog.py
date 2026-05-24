import discord
from discord.ext import commands
from discord import app_commands
import asyncio

from core.mafia import MafiaGame, Role
from core import database

active_games = {} # guild_id -> MafiaGame

# ═══════════════════════════════════════════════════
# НІЧНІ КНОПКИ (відправляються у ЛС кожній ролі)
# ═══════════════════════════════════════════════════

class NightActionView(discord.ui.View):
    """Select menu sent to Mafia/Doctor/Sheriff in DMs during night."""
    def __init__(self, game, role, player_id):
        super().__init__(timeout=60)
        self.game = game
        self.role = role
        self.player_id = player_id
        self.acted = False

        options = []
        for p in self.game.get_alive_players():
            # Мафія не може вбити саму себе
            if role == Role.MAFIA and p.id == player_id:
                continue
            options.append(discord.SelectOption(label=p.display_name, value=str(p.id)))

        if not options:
            return

        if role == Role.MAFIA:
            placeholder = "🔫 Кого вбити цієї ночі?"
        elif role == Role.DOCTOR:
            placeholder = "💊 Кого вилікувати цієї ночі?"
        elif role == Role.SHERIFF:
            placeholder = "🔍 Кого перевірити цієї ночі?"
        else:
            placeholder = "Оберіть гравця"

        select = discord.ui.Select(placeholder=placeholder, options=options)
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        if self.acted:
            return await interaction.response.send_message("Ви вже зробили свій вибір!", ephemeral=True)
            
        self.acted = True
        target_id = int(interaction.data["values"][0])
        target_name = self.game.players[target_id]["user"].display_name

        if self.role == Role.MAFIA:
            self.game.night_actions["kill"] = target_id
            await interaction.response.edit_message(
                content=f"🔫 Ви обрали вбити **{target_name}**. Чекаємо на решту...", view=None
            )
        elif self.role == Role.DOCTOR:
            self.game.night_actions["heal"] = target_id
            await interaction.response.edit_message(
                content=f"💊 Ви лікуєте **{target_name}** цієї ночі. Чекаємо на решту...", view=None
            )
        elif self.role == Role.SHERIFF:
            self.game.night_actions["check"] = target_id
            # Одразу повідомити Комісару результат перевірки
            checked_role = self.game.players[target_id]["role"]
            if checked_role == Role.MAFIA:
                result = f"🚨 **{target_name}** — це **МАФІЯ**! Будьте обережні вдень!"
            else:
                result = f"✅ **{target_name}** — **мирний житель**. Можна довіряти."
            await interaction.response.edit_message(
                content=f"🔍 Результат перевірки:\n{result}", view=None
            )

        self.game.night_actions_received += 1
        # Якщо всі зробили вибір — розбудити гру
        if self.game.night_event and self.game.night_actions_received >= self.game.night_actions_expected:
            self.game.night_event.set()

    async def on_timeout(self):
        """Якщо гравець не зробив вибір за 60 секунд — пропускаємо."""
        if not self.acted:
            self.game.night_actions_received += 1
            if self.game.night_event and self.game.night_actions_received >= self.game.night_actions_expected:
                self.game.night_event.set()


# ═══════════════════════════════════════════════════
# ЛОБІ (Збір гравців)
# ═══════════════════════════════════════════════════

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
        
        # Змінюємо нікнейми і відправляємо ролі в ЛС
        for p_id, p_info in self.game.players.items():
            user = p_info["user"]
            role = p_info["role"]
            member = interaction.guild.get_member(p_id)
            if member:
                p_info["original_name"] = member.display_name
                try: await member.edit(nick=f"🕵️ {member.display_name}")
                except: pass
            try:
                role_emoji = {"Мафія": "🔫", "Лікар": "💊", "Комісар": "🔍", "Мирний житель": "😇"}.get(role, "❓")
                await user.send(f"{role_emoji} Ваша роль у цій грі: **{role}**. Нікому не кажіть!")
            except: pass

        # Починаємо першу ніч
        await run_night_phase(self.game, interaction)


# ═══════════════════════════════════════════════════
# НІЧНА ФАЗА (відправка кнопок + очікування)
# ═══════════════════════════════════════════════════

async def run_night_phase(game, interaction):
    """Запускає нічну фазу: мутить, відправляє кнопки в ЛС, чекає відповідей."""
    guild = interaction.guild
    message = interaction.message
    
    # Мутимо всіх у войсі
    vc = None
    for p_id in game.players:
        member = guild.get_member(p_id)
        if member and member.voice and member.voice.channel:
            vc = member.voice.channel
            break
    
    if vc:
        for p_id, p_info in game.players.items():
            if p_info["alive"]:
                member = guild.get_member(p_id)
                if member and member in vc.members:
                    try: await member.edit(mute=True)
                    except: pass

    night_num = game.day_count + 1
    embed = discord.Embed(
        title=f"🌙 Ніч {night_num}",
        description="Місто засинає. Мафія виходить на полювання...\n\n*Перевірте свої особисті повідомлення!*",
        color=0x2b2d31
    )
    await message.edit(embed=embed, view=None)

    # Перша ніч — ніч знайомств, кнопки не потрібні
    if game.day_count == 0:
        await asyncio.sleep(10)
    else:
        # Відправляємо кнопки вибору кожній ролі в ЛС
        game.night_event = asyncio.Event()
        game.night_actions_expected = game.count_expected_night_actions()
        game.night_actions_received = 0

        for p_id, p_info in game.players.items():
            if not p_info["alive"]:
                continue
            role = p_info["role"]
            user = p_info["user"]
            
            if role == Role.MAFIA:
                try:
                    view = NightActionView(game, Role.MAFIA, p_id)
                    await user.send("🔫 **Ніч настала.** Оберіть, кого вбити:", view=view)
                except: 
                    game.night_actions_received += 1
                    
            elif role == Role.DOCTOR:
                try:
                    view = NightActionView(game, Role.DOCTOR, p_id)
                    await user.send("💊 **Ніч настала.** Оберіть, кого вилікувати:", view=view)
                except: 
                    game.night_actions_received += 1
                    
            elif role == Role.SHERIFF:
                try:
                    view = NightActionView(game, Role.SHERIFF, p_id)
                    await user.send("🔍 **Ніч настала.** Оберіть, кого перевірити:", view=view)
                except: 
                    game.night_actions_received += 1

        # Чекаємо поки всі зроблять вибір АБО timeout 60 секунд
        try:
            await asyncio.wait_for(game.night_event.wait(), timeout=60)
        except asyncio.TimeoutError:
            pass

    # Обробляємо результати ночі
    night_events, dead = game.process_night()
    
    # Перевіряємо, чи хтось переміг після ночі
    win = game.check_win_condition()
    if win:
        embed.title = "🏆 Гра закінчена!"
        embed.description = "\n".join(night_events) + f"\n\n**Перемогли: {win}**"
        await message.edit(embed=embed, view=None)
        await end_game(game, guild)
        return

    # Розмучуємо живих для денної фази
    if vc:
        for p_id, p_info in game.players.items():
            if p_info["alive"]:
                member = guild.get_member(p_id)
                if member and member in vc.members:
                    try: await member.edit(mute=False)
                    except: pass

    embed.title = f"☀️ День {game.day_count}"
    embed.description = "\n".join(night_events) + "\n\n**Час обговорити та проголосувати!**"
    embed.color = 0xf1c40f
    await message.edit(embed=embed, view=VoteView(game))


# ═══════════════════════════════════════════════════
# ДЕННЕ ГОЛОСУВАННЯ
# ═══════════════════════════════════════════════════

class VoteView(discord.ui.View):
    def __init__(self, game):
        super().__init__(timeout=None)
        self.game = game

        options = []
        for p in self.game.get_alive_players():
            options.append(discord.SelectOption(label=p.display_name, value=str(p.id)))
            
        if options:
            select = discord.ui.Select(placeholder="⚖️ Оберіть, кого стратити", options=options, custom_id="mafia_vote_select")
            select.callback = self.vote_callback
            self.add_item(select)

    async def vote_callback(self, interaction: discord.Interaction):
        if interaction.user.id not in self.game.players or not self.game.players[interaction.user.id]["alive"]:
            return await interaction.response.send_message("Тільки живі гравці можуть голосувати!", ephemeral=True)
            
        target_id = int(interaction.data["values"][0])
        target_name = self.game.players[target_id]["user"].display_name
        self.game.day_votes[interaction.user.id] = target_id
        
        alive_count = len(self.game.get_alive_players())
        voted_count = len(self.game.day_votes)
        await interaction.response.send_message(f"✅ Ви проголосували проти **{target_name}** ({voted_count}/{alive_count})", ephemeral=True)

    @discord.ui.button(label="Завершити день", style=discord.ButtonStyle.blurple, custom_id="end_day")
    async def end_day_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in self.game.players or not self.game.players[interaction.user.id]["alive"]:
            return await interaction.response.send_message("Ви не живий гравець!", ephemeral=True)
            
        alive_players = self.game.get_alive_players()
        if len(self.game.day_votes) < len(alive_players):
            return await interaction.response.send_message(
                f"Ще не всі проголосували! ({len(self.game.day_votes)}/{len(alive_players)})", ephemeral=True
            )
            
        await interaction.response.defer()
        
        executed, event = self.game.process_day_votes()
        embed = interaction.message.embeds[0]
        
        # Перевіряємо перемогу після голосування
        win = self.game.check_win_condition()
        if win:
            embed.title = "🏆 Гра закінчена!"
            embed.description = event + f"\n\n**Перемогли: {win}**"
            embed.color = 0xffd700
            await interaction.message.edit(embed=embed, view=None)
            await end_game(self.game, interaction.guild)
            return
            
        # Якщо гра не закінчилася — починається НІЧ
        await run_night_phase(self.game, interaction)


# ═══════════════════════════════════════════════════
# ДОПОМІЖНІ ФУНКЦІЇ
# ═══════════════════════════════════════════════════

async def end_game(game, guild):
    """Відновлює нікнейми, знімає мут, видаляє гру."""
    for p_id, p_info in game.players.items():
        member = guild.get_member(p_id)
        if member:
            orig_name = p_info.get("original_name")
            in_vc = member.voice and member.voice.channel
            try: 
                if in_vc: await member.edit(mute=False, nick=orig_name)
                else: await member.edit(nick=orig_name)
            except: pass
                
    if game.guild_id in active_games:
        del active_games[game.guild_id]


# ═══════════════════════════════════════════════════
# КОГ (Slash commands)
# ═══════════════════════════════════════════════════

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
            
        await end_game(game, interaction.guild)
        await interaction.response.send_message("🛑 **Гру екстрено завершено.** Усім гравцям повернено мікрофони та нікнейми.")

async def setup(bot):
    await bot.add_cog(MafiaCog(bot))
