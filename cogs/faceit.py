import discord
from discord import app_commands
from discord.ext import commands
from core import config, database, faceit_api

class FaceitView(discord.ui.View):
    def __init__(self, target_name: str, caller_name: str):
        super().__init__(timeout=300)
        self.target_name = target_name
        self.caller_name = caller_name

    @discord.ui.button(label="Профіль", emoji="⬛", style=discord.ButtonStyle.secondary)
    async def profile_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = await faceit_api.get_profile(self.target_name)
        
        embed = discord.Embed(title=f"⬛ Faceit Профіль: {self.target_name}", color=0x2b2d31)
        embed.add_field(name="🏆 ELO", value=f"`{data['elo']}`", inline=True)
        embed.add_field(name="📊 Рівень", value=f"`{data['level']}`", inline=True)
        embed.add_field(name="☠️ K/D", value=f"`{data['kd']}`", inline=True)
        embed.add_field(name="🎯 Winrate", value=f"`{data['winrate']}%`", inline=True)
        
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Останній матч", emoji="▫️", style=discord.ButtonStyle.secondary)
    async def last_match_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = await faceit_api.get_last_match(self.target_name)
        
        embed = discord.Embed(title=f"▫️ Останній матч: {self.target_name}", color=0x2b2d31)
        embed.add_field(name="📊 Рахунок", value=f"`{data['score']}`", inline=True)
        embed.add_field(name="☠️ K/D", value=f"`{data['kd']}`", inline=True)
        embed.add_field(name="🏆 ELO +/-", value=f"`{data['elo_diff']}`", inline=True)
        
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Порівняти зі мною", emoji="⚔️", style=discord.ButtonStyle.secondary)
    async def compare_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.caller_name:
            embed = discord.Embed(description="▪️ У вас не прив'язаний Faceit акаунт. Використайте `/faceit link`.", color=0x000000)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if self.target_name == self.caller_name:
            embed = discord.Embed(description="🤡 Ви намагаєтесь порівняти себе із самим собою.", color=0x000000)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        t_data = await faceit_api.get_profile(self.target_name)
        c_data = await faceit_api.get_profile(self.caller_name)

        embed = discord.Embed(title=f"⚔️ Порівняння: {self.caller_name} vs {self.target_name}", color=0x2b2d31)
        embed.add_field(name="🏆 ELO", value=f"Ви: `{c_data['elo']}`\nЦіль: `{t_data['elo']}`", inline=True)
        embed.add_field(name="☠️ K/D", value=f"Ви: `{c_data['kd']}`\nЦіль: `{t_data['kd']}`", inline=True)
        embed.add_field(name="🎯 Winrate", value=f"Ви: `{c_data['winrate']}%`\nЦіль: `{t_data['winrate']}%`", inline=True)
        
        await interaction.response.edit_message(embed=embed, view=self)

class FaceitCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    faceit_group = app_commands.Group(name="faceit", description="Система Faceit")

    @faceit_group.command(name="link", description="Прив'язати Faceit акаунт")
    @app_commands.describe(nickname="Faceit нікнейм")
    async def link_cmd(self, interaction: discord.Interaction, nickname: str):
        users = database.load_faceit_users()
        users[str(interaction.user.id)] = nickname
        database.save_faceit_users(users)

        embed = discord.Embed(
            title="⬛ Реєстрація Faceit",
            description=f"▫️ **Користувач:** {interaction.user.mention}\n▫️ **Faceit:** `{nickname}`\n\n▪️ *Акаунт успішно збережено в базі.*",
            color=0x2b2d31
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @faceit_group.command(name="unlink", description="Відв'язати Faceit акаунт")
    @app_commands.describe(member="Користувач (чужі акаунти можуть відв'язувати лише модератори)")
    async def unlink_cmd(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        
        if target.id != interaction.user.id:
            has_mod = any(role.id == config.MODERATOR_ROLE_ID for role in interaction.user.roles)
            if not has_mod:
                embed = discord.Embed(description="▪️ У вас немає прав для відв'язки чужих акаунтів.", color=0x000000)
                return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        users = database.load_faceit_users()
        target_str_id = str(target.id)
        
        if target_str_id not in users:
            embed = discord.Embed(description=f"▪️ {target.mention} не має прив'язаного Faceit акаунту.", color=0x000000)
            return await interaction.response.send_message(embed=embed, ephemeral=True)
            
        del users[target_str_id]
        database.save_faceit_users(users)
        
        embed = discord.Embed(
            title="⬛ Відв'язка Faceit",
            description=f"▫️ **Користувач:** {target.mention}\n\n▪️ *Акаунт успішно видалено з бази.*",
            color=0x2b2d31
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @faceit_group.command(name="profile", description="Переглянути Faceit профіль")
    @app_commands.describe(member="Користувач (за замовчуванням - ви)")
    async def profile_cmd(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        users = database.load_faceit_users()

        target_name = users.get(str(target.id))
        caller_name = users.get(str(interaction.user.id))

        if not target_name:
            embed = discord.Embed(description=f"▪️ {target.mention} не має прив'язаного Faceit акаунту.", color=0x000000)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        await interaction.response.defer()

        data = await faceit_api.get_profile(target_name)
        
        embed = discord.Embed(title=f"⬛ Faceit Профіль: {target_name}", color=0x2b2d31)
        embed.add_field(name="🏆 ELO", value=f"`{data['elo']}`", inline=True)
        embed.add_field(name="📊 Рівень", value=f"`{data['level']}`", inline=True)
        embed.add_field(name="☠️ K/D", value=f"`{data['kd']}`", inline=True)
        embed.add_field(name="🎯 Winrate", value=f"`{data['winrate']}%`", inline=True)

        view = FaceitView(target_name, caller_name)
        await interaction.followup.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(FaceitCog(bot))