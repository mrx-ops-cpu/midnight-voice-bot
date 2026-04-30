import discord
from discord.ext import commands
from flask import request, jsonify
from core import database, faceit_api, config
import asyncio

class FaceitWebhooksCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.app.add_url_rule('/faceit_webhook', 'faceit_webhook', self.handle_webhook, methods=['POST'])

    def handle_webhook(self):
        data = request.json
        if not data:
            return jsonify({"status": "error", "message": "No data received"}), 400

        event = data.get('event')
        if event == 'match_status_finished':
            payload = data.get('payload', {})
            asyncio.run_coroutine_threadsafe(self.process_match_report(payload), self.bot.loop)
            
        return jsonify({"status": "success"}), 200

    async def process_match_report(self, payload: dict):
        match_id = payload.get('id')
        teams = payload.get('teams', [])
        
        users = database.load_faceit_users()
        our_party = []
        
        for team in teams:
            for player in team.get('roster', []):
                faceit_name = player.get('nickname')
                discord_id = next((discord_id for discord_id, name in users.items() if name == faceit_name), None)
                
                if discord_id:
                    kd = player.get('kd_ratio', 0.9) 
                    adr = player.get('adr', 70)
                    kills = player.get('kills', 15)
                    deaths = player.get('deaths', 16)
                    
                    our_party.append({
                        "discord_id": discord_id,
                        "faceit_name": faceit_name,
                        "kd": kd,
                        "adr": adr,
                        "score": f"{kills}/{deaths}"
                    })

        if not our_party:
            return

        embed = discord.Embed(title="⬛ Звіт про матч Faceit", description=f"Матч `{match_id}` завершено.", color=0x2b2d31)
        
        ruiner = None
        lowest_kd = float('inf')

        for p in our_party:
            embed.add_field(
                name=f"▫️ {p['faceit_name']}", 
                value=f"☠️ K/D: `{p['kd']}`\n🎯 ADR: `{p['adr']}`\n📊 K/D: `{p['score']}`", 
                inline=False
            )
            
            if p['kd'] < 0.8 and p['kd'] < lowest_kd:
                ruiner = p
                lowest_kd = p['kd']

        if ruiner:
            comment = "🤡 Головний руїнер матчу! Навіть боти грають краще."
            embed.add_field(name="🤡 Система Руїнера", value=f"<@{ruiner['discord_id']}> {comment}", inline=False)

        channel = self.bot.get_channel(config.GAMING_LOG_ID)
        if channel:
             await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(FaceitWebhooksCog(bot))