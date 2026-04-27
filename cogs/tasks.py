import discord
from discord.ext import commands, tasks
from datetime import datetime, time, timezone
from core import config, database, utils

class TasksCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.periodic_save.start()
        self.daily_report.start()
        self.update_dashboards.start()

    def cog_unload(self):
        self.periodic_save.cancel()
        self.daily_report.cancel()
        self.update_dashboards.cancel()

    @tasks.loop(minutes=1)
    async def update_dashboards(self):
        if not config.GLOBAL_SETTINGS["monitoring"] and not config.GLOBAL_SETTINGS["voice_stats"]:
            return
        for guild in self.bot.guilds:
            await utils.update_fame_message(guild, self.bot)
            await utils.update_live_message(guild, self.bot)

    @update_dashboards.before_loop
    async def before_update_dashboards(self):
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=2)
    async def periodic_save(self):
        if not config.GLOBAL_SETTINGS["voice_stats"]: 
            return
            
        now = datetime.now().timestamp()
        s = database.load_stats()
        sv, sg = 0, 0

        for uid, start in list(config.voice_start_times.items()):
            last = config.voice_last_save.get(uid, start)
            dur = now - last
            if dur >= 30: 
                k = str(uid)
                try:
                    s["total"][k] = float(s["total"].get(k, 0)) + dur
                    s["daily"][k] = float(s["daily"].get(k, 0)) + dur
                except: pass
                config.voice_last_save[uid] = now
                sv += 1

        for uid, user_sessions in list(config.game_sessions.items()):
            if not isinstance(user_sessions, dict): continue
            
            for game, sess in user_sessions.items():
                if not isinstance(sess, dict) or "start_time" not in sess: continue
                
                dur = now - sess["start_time"]
                if dur >= 30: 
                    k = str(uid)
                    
                    if "games" not in s or not isinstance(s["games"], dict): 
                        s["games"] = {}
                    if k not in s["games"] or not isinstance(s["games"][k], dict): 
                        s["games"][k] = {}
                    
                    try:
                        current_saved = float(s["games"][k].get(game, 0))
                    except:
                        current_saved = 0.0
                        
                    s["games"][k][game] = current_saved + dur
                    config.game_sessions[uid][game]["start_time"] = now
                    sg += 1

        if sv > 0 or sg > 0:
            database.save_stats(s)
            database.save_voice_sessions()
            database.save_game_sessions()
            print(f"PERIODIC SAVE: Voice={sv}, Games={sg}")

    @periodic_save.before_loop
    async def before_periodic_save(self):
        await self.bot.wait_until_ready()

    @tasks.loop(time=time(hour=0, minute=0, tzinfo=timezone.utc))
    async def daily_report(self):
        if not config.GLOBAL_SETTINGS["voice_stats"]: 
            return
            
        now = datetime.now().timestamp()
        s = database.load_stats()
        
        total_fame = dict(s.get("total", {}))
        for uid_v, start_v in list(config.voice_start_times.items()):
            k_v = str(uid_v)
            last_v = config.voice_last_save.get(uid_v, start_v)
            total_fame[k_v] = float(total_fame.get(k_v, 0)) + (now - last_v)
        
        top3_fame_ids = [str(u) for u, _ in sorted(total_fame.items(), key=lambda x: float(x[1]), reverse=True)[:3]]
        
        all_streak_users = list(s.get("streaks", {}).keys())
        for u_id in set(all_streak_users + top3_fame_ids):
            if u_id in top3_fame_ids:
                database.update_streak(u_id)
            else:
                database.reset_streak(u_id)

        for uid, start in list(config.voice_start_times.items()):
            last = config.voice_last_save.get(uid, start)
            dur = now - last
            if dur >= 30: 
                k = str(uid)
                try:
                    s["total"][k] = float(s["total"].get(k, 0)) + dur
                    s["daily"][k] = float(s["daily"].get(k, 0)) + dur
                except: pass
                config.voice_last_save[uid] = now
                
        total_daily_sec = sum(float(v) for v in s.get("daily", {}).values() if isinstance(v, (int, float)))
        today_str = datetime.now(timezone.utc).strftime("%d.%m")
        s.setdefault("history", {})[today_str] = int(total_daily_sec)
        
        if len(s["history"]) > 7:
            first_key = list(s["history"].keys())[0]
            del s["history"][first_key]

        ch = self.bot.get_channel(config.GAMING_LOG_ID)
        top = sorted(s.get("daily", {}).items(), key=lambda x: float(x[1]) if isinstance(x[1], (int, float)) else 0, reverse=True)[:5]
        
        s["daily"] = {}
        database.save_stats(s)
        
        if not top or not ch:
            return

        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        guild = self.bot.guilds[0] if self.bot.guilds else None
        lines = []
        
        for i, (uid, sec) in enumerate(top):
            display_name = database.get_display_name(uid, guild, self.bot)
            emoji = utils.streak_emoji(uid)
            time_str = utils.format_time(sec)
            lines.append(f"{medals[i]} {display_name}{emoji} — {time_str}")
            
        embed = discord.Embed(
            title="📊 Підсумки дня", 
            description="\n".join(lines),
            color=0x9b59b6, 
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text=utils.midnight_footer())
        
        await ch.send(embed=embed)
        print("DAILY RESET & HISTORY LOGGED")

    @daily_report.before_loop
    async def before_daily_report(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(TasksCog(bot))