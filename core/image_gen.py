import os
import io
import aiohttp
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO

async def fetch_image(url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    return Image.open(BytesIO(data)).convert("RGBA")
    except:
        pass
    return None

async def generate_top_banner(top_players):
    """
    top_players: list of dicts with {'nickname': str, 'elo': int, 'level': int, 'avatar': str}
    """
    width, height = 800, 100 + max(1, len(top_players)) * 60
    img = Image.new("RGBA", (width, height), (30, 33, 36, 255))
    draw = ImageDraw.Draw(img)

    # Optional: try to load a font, otherwise use default
    try:
        font_title = ImageFont.truetype("arial.ttf", 36)
        font_text = ImageFont.truetype("arial.ttf", 24)
        font_small = ImageFont.truetype("arial.ttf", 18)
    except IOError:
        font_title = ImageFont.load_default()
        font_text = ImageFont.load_default()
        font_small = ImageFont.load_default()

    draw.text((30, 20), "🏆 ТОП ГРАВЦІВ СЕРВЕРА (FACEIT)", fill=(255, 165, 0), font=font_title)
    
    y_offset = 80
    for i, player in enumerate(top_players):
        # Draw background bar
        draw.rectangle([20, y_offset, width-20, y_offset+50], fill=(43, 47, 51, 255), outline=(60, 64, 69, 255))
        
        # Draw rank number
        draw.text((30, y_offset + 10), f"#{i+1}", fill=(200, 200, 200), font=font_text)
        
        # If we have avatar, we can draw it, but to keep it fast we will just draw text
        draw.text((100, y_offset + 10), player.get("nickname", "Unknown"), fill=(255, 255, 255), font=font_text)
        
        # Level circle
        lvl = player.get("level", 1)
        level_colors = {
            1: (238, 238, 238), 2: (69, 203, 72), 3: (69, 203, 72),
            4: (255, 192, 0), 5: (255, 192, 0), 6: (255, 192, 0), 7: (255, 192, 0),
            8: (255, 110, 0), 9: (255, 110, 0), 10: (211, 44, 38)
        }
        color = level_colors.get(lvl, (255,255,255))
        draw.ellipse([450, y_offset+10, 480, y_offset+40], fill=color)
        draw.text((458, y_offset + 15), str(lvl), fill=(0, 0, 0), font=font_text)
        
        draw.text((550, y_offset + 10), f"ELO: {player.get('elo', 0)}", fill=(255, 165, 0), font=font_text)
        
        y_offset += 60

    if not top_players:
        draw.text((30, y_offset), "Немає прив'язаних гравців.", fill=(150, 150, 150), font=font_text)

    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output

async def generate_active_matches_banner(active_players):
    """
    active_players: list of dicts with {'nickname': str, 'status': str, ...}
    """
    width, height = 800, 200 + max(1, len(active_players)) * 50
    img = Image.new("RGBA", (width, height), (30, 33, 36, 255))
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("arial.ttf", 32)
        font_text = ImageFont.truetype("arial.ttf", 22)
    except IOError:
        font_title = ImageFont.load_default()
        font_text = ImageFont.load_default()

    draw.text((30, 20), "🔥 АКТИВНІ МАТЧІ (Останні Ігри)", fill=(255, 70, 70), font=font_title)
    
    y_offset = 80
    for p in active_players:
        draw.rectangle([20, y_offset, width-20, y_offset+40], fill=(43, 47, 51, 255))
        draw.text((30, y_offset + 5), f"{p['nickname']} — {p['match_status']}", fill=(200, 200, 200), font=font_text)
        y_offset += 50

    if not active_players:
        draw.text((30, y_offset), "Зараз ніхто не грає, або всі матчі завершені.", fill=(150, 150, 150), font=font_text)
        
    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output

async def generate_profile_card(nickname, player_data, stats_data):
    width, height = 600, 300
    img = Image.new("RGBA", (width, height), (30, 33, 36, 255))
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("arial.ttf", 40)
        font_text = ImageFont.truetype("arial.ttf", 24)
        font_small = ImageFont.truetype("arial.ttf", 18)
    except IOError:
        font_title = ImageFont.load_default()
        font_text = ImageFont.load_default()
        font_small = ImageFont.load_default()

    draw.text((20, 20), f"Профіль: {nickname}", fill=(255, 165, 0), font=font_title)
    
    if player_data and not player_data.get('error'):
        games = player_data.get("games", {})
        cs2 = games.get("cs2", {})
        elo = cs2.get("faceit_elo", "N/A")
        lvl = cs2.get("skill_level", "N/A")
        
        draw.text((20, 80), f"Level: {lvl} | ELO: {elo}", fill=(255, 255, 255), font=font_text)
    else:
        draw.text((20, 80), "Гравець не знайдений.", fill=(255, 50, 50), font=font_text)

    if stats_data and not stats_data.get('error'):
        lifetime = stats_data.get("lifetime", {})
        kd = lifetime.get("Average K/D Ratio", "N/A")
        winrate = lifetime.get("Win Rate %", "N/A")
        matches = lifetime.get("Matches", "N/A")
        recent = lifetime.get("Recent Results", [])
        
        draw.text((20, 120), f"K/D: {kd} | WinRate: {winrate}%", fill=(200, 200, 200), font=font_text)
        draw.text((20, 160), f"Всього матчів: {matches}", fill=(200, 200, 200), font=font_text)
        
        draw.text((20, 210), "Останні ігри:", fill=(255, 255, 255), font=font_small)
        x_offset = 150
        for res in recent:
            color = (50, 200, 50) if str(res) == "1" else (200, 50, 50)
            draw.rectangle([x_offset, 210, x_offset+20, 230], fill=color)
            x_offset += 30

    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output
