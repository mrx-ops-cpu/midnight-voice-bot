import os
import io
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from io import BytesIO

async def fetch_image(url):
    try:
        if not url: return None
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    return Image.open(BytesIO(data)).convert("RGBA")
    except:
        pass
    return None

def make_circle_avatar(img, size):
    img = img.resize(size)
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask) 
    draw.ellipse((0, 0) + size, fill=255)
    output = Image.new('RGBA', size, (0, 0, 0, 0))
    output.paste(img, (0, 0), mask=mask)
    return output

def get_font(size, bold=False):
    font_name = "Roboto-Bold.ttf" if bold else "Roboto-Regular.ttf"
    try:
        return ImageFont.truetype(font_name, size)
    except:
        try:
            return ImageFont.truetype("arial.ttf", size)
        except:
            return ImageFont.load_default()

def draw_rounded_rect(draw, coords, radius, fill):
    x0, y0, x1, y1 = coords
    draw.rectangle([x0+radius, y0, x1-radius, y1], fill=fill)
    draw.rectangle([x0, y0+radius, x1, y1-radius], fill=fill)
    draw.pieslice([x0, y0, x0+radius*2, y0+radius*2], 180, 270, fill=fill)
    draw.pieslice([x1-radius*2, y0, x1, y0+radius*2], 270, 360, fill=fill)
    draw.pieslice([x0, y1-radius*2, x0+radius*2, y1], 90, 180, fill=fill)
    draw.pieslice([x1-radius*2, y1-radius*2, x1, y1], 0, 90, fill=fill)

def apply_background(width, height):
    # Pure FaceIT dark background
    return Image.new("RGBA", (width, height), (22, 25, 27, 255))

def draw_faceit_level(draw, x, y, size, lvl, font):
    level_colors = {
        1: (238, 238, 238), 2: (69, 203, 72), 3: (69, 203, 72),
        4: (255, 192, 0), 5: (255, 192, 0), 6: (255, 192, 0), 7: (255, 192, 0),
        8: (255, 110, 0), 9: (255, 110, 0), 10: (211, 44, 38)
    }
    color = level_colors.get(lvl, (255,255,255))
    
    draw.ellipse([x, y, x+size, y+size], outline=color, width=2)
    lvl_str = str(lvl)
    text_bbox = draw.textbbox((0, 0), lvl_str, font=font)
    text_w = text_bbox[2] - text_bbox[0]
    text_h = text_bbox[3] - text_bbox[1]
    
    draw.text((x + (size - text_w)/2, y + (size - text_h)/2 - 3), lvl_str, fill=color, font=font)

async def generate_dashboard_banner(top_players):
    row_height = 50
    header_height = 40
    width = 900
    height = header_height + max(1, len(top_players)) * row_height
    
    img = apply_background(width, height)
    draw = ImageDraw.Draw(img)

    font_header = get_font(14, bold=True)
    font_text = get_font(16, bold=True)
    font_small = get_font(14, bold=True)
    font_tiny = get_font(12, bold=True)
    font_lvl = get_font(13, bold=True)

    header_color = (113, 118, 122)
    
    # Header Row Background
    draw.rectangle([0, 0, width, header_height], fill=(22, 25, 27, 255))
    
    # Header texts
    draw.text((80, 12), "Player", fill=header_color, font=font_header)
    draw.text((350, 12), "Rank", fill=header_color, font=font_header)
    draw.text((550, 12), "K/D", fill=header_color, font=font_header)
    draw.text((650, 12), "Win %", fill=header_color, font=font_header)
    draw.text((750, 12), "Recent", fill=header_color, font=font_header)
    
    y_offset = header_height
    for i, player in enumerate(top_players):
        # Alternating row colors
        bg_color = (33, 36, 40, 255) if i % 2 == 0 else (28, 30, 34, 255)
        draw.rectangle([0, y_offset, width, y_offset + row_height], fill=bg_color)
        
        # Color bar indicator on left side
        color_rank = (255, 215, 0) if i == 0 else (192, 192, 192) if i == 1 else (205, 127, 50) if i == 2 else (60, 60, 60)
        draw.rectangle([0, y_offset, 4, y_offset + row_height], fill=color_rank)
        
        draw.text((25, y_offset + 16), f"#{i+1}", fill=color_rank, font=font_small)
        
        avatar_img = await fetch_image(player.get("avatar", ""))
        if avatar_img:
            avatar = make_circle_avatar(avatar_img, (34, 34))
            img.paste(avatar, (65, y_offset + 8), avatar)
            
        draw.text((110, y_offset + 15), player.get("nickname", "Unknown"), fill=(240, 240, 240), font=font_text)
        
        # Rank: Level icon + ELO
        lvl = player.get("level", 1)
        draw_faceit_level(draw, 350, y_offset + 12, 26, lvl, font_lvl)
        draw.text((385, y_offset + 16), f"{player.get('elo', 0)}", fill=(220, 220, 220), font=font_small)
        
        # Stats
        stats_data = player.get("stats_data", {})
        lifetime = stats_data.get("lifetime", {}) if stats_data and 'error' not in stats_data else {}
        kd = lifetime.get("Average K/D Ratio", "-")
        wr = lifetime.get("Win Rate %", "-")
        
        # Format WR to match screenshot style (just the number)
        wr_clean = wr.replace('%', '') if wr != '-' else '-'
        
        draw.text((550, y_offset + 16), kd, fill=(220, 220, 220), font=font_small)
        draw.text((650, y_offset + 16), wr_clean + ("%" if wr_clean != "-" else ""), fill=(220, 220, 220), font=font_small)

        # Recent Results
        recent = lifetime.get("Recent Results", [])
        rx = 750
        for res in recent:
            if str(res) == "1":
                draw.rectangle([rx, y_offset + 18, rx + 14, y_offset + 32], fill=(45, 150, 45, 255))
                # Text removed for minimalist faceit style, or kept very small. Let's just use green/red rectangles like faceit does.
            else:
                draw.rectangle([rx, y_offset + 18, rx + 14, y_offset + 32], fill=(200, 50, 50, 255))
            rx += 18

        y_offset += row_height

    if not top_players:
        draw.text((40, y_offset + 15), "Немає прив'язаних гравців.", fill=(150, 150, 150), font=font_text)

    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output

async def generate_profile_card(nickname, player_data, stats_data, match_stats=None):
    width, height = 700, 380
    img = apply_background(width, height)
    draw = ImageDraw.Draw(img)

    font_title = get_font(34, bold=True)
    font_text = get_font(24, bold=True)
    font_small = get_font(18)
    font_lvl = get_font(20, bold=True)

    draw.text((30, 25), f"ПРОФІЛЬ: {nickname.upper()}", fill=(255, 85, 0), font=font_title)
    
    avatar_img = await fetch_image(player_data.get("avatar", "")) if player_data else None
    if avatar_img:
        avatar = make_circle_avatar(avatar_img, (80, 80))
        img.paste(avatar, (550, 15), avatar)
    
    if player_data and not player_data.get('error'):
        games = player_data.get("games", {})
        cs2 = games.get("cs2", {})
        elo = cs2.get("faceit_elo", "N/A")
        lvl = cs2.get("skill_level", 1)
        
        draw.rectangle([30, 80, 670, 180], fill=(33, 36, 40, 255))
        draw_faceit_level(draw, 50, 110, 40, lvl, font_lvl)
        draw.text((100, 115), "Level", fill=(150, 150, 150), font=font_small)
        
        draw.text((250, 115), f"ELO: {elo}", fill=(255, 85, 0), font=font_text)
    else:
        draw.text((30, 80), "Гравець не знайдений.", fill=(255, 50, 50), font=font_text)

    if stats_data and not stats_data.get('error'):
        lifetime = stats_data.get("lifetime", {})
        kd = lifetime.get("Average K/D Ratio", "N/A")
        winrate = lifetime.get("Win Rate %", "N/A")
        matches = lifetime.get("Matches", "N/A")
        recent = lifetime.get("Recent Results", [])
        
        draw.text((50, 140), f"K/D: {kd}", fill=(200, 200, 200), font=font_small)
        draw.text((250, 140), f"Вінрейт: {winrate}%", fill=(200, 200, 200), font=font_small)
        draw.text((450, 140), f"Матчів: {matches}", fill=(200, 200, 200), font=font_small)
        
        draw.text((30, 200), "Останні ігри:", fill=(150, 150, 150), font=font_small)
        rx = 180
        for res in recent:
            if str(res) == "1":
                draw.rectangle([rx, 195, rx+25, 220], fill=(45, 150, 45, 255))
            else:
                draw.rectangle([rx, 195, rx+25, 220], fill=(200, 50, 50, 255))
            rx += 30

    if match_stats:
        draw.rectangle([30, 250, 670, 350], fill=(33, 36, 40, 255))
        draw.text((50, 265), "ОСТАННІЙ МАТЧ", fill=(255, 85, 0), font=font_small)
        draw.text((50, 300), match_stats, fill=(200, 200, 200), font=font_small)

    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output

async def generate_compare_card(nickname1, p1_data, p1_stats, nickname2, p2_data, p2_stats):
    width, height = 700, 400
    img = apply_background(width, height)
    draw = ImageDraw.Draw(img)

    font_title = get_font(30, bold=True)
    font_text = get_font(24, bold=True)
    font_small = get_font(18)

    draw.text((30, 20), "ПОРІВНЯННЯ", fill=(255, 85, 0), font=font_title)
    
    draw.text((150, 80), nickname1.upper(), fill=(255, 255, 255), font=font_text)
    draw.text((450, 80), nickname2.upper(), fill=(255, 255, 255), font=font_text)
    
    av1 = await fetch_image(p1_data.get("avatar", "")) if p1_data else None
    av2 = await fetch_image(p2_data.get("avatar", "")) if p2_data else None
    
    if av1:
        img.paste(make_circle_avatar(av1, (40, 40)), (100, 75), make_circle_avatar(av1, (40, 40)))
    if av2:
        img.paste(make_circle_avatar(av2, (40, 40)), (400, 75), make_circle_avatar(av2, (40, 40)))

    def draw_stat(y, label, val1_str, val2_str, reverse=False):
        draw.text((30, y), label, fill=(150, 150, 150), font=font_small)
        try:
            v1 = float(val1_str.replace('%', ''))
            v2 = float(val2_str.replace('%', ''))
            c1 = (45, 150, 45) if (v1 > v2 and not reverse) or (v1 < v2 and reverse) else ((200, 50, 50) if v1 != v2 else (200,200,200))
            c2 = (45, 150, 45) if (v2 > v1 and not reverse) or (v2 < v1 and reverse) else ((200, 50, 50) if v1 != v2 else (200,200,200))
        except:
            c1 = c2 = (200, 200, 200)
            
        draw.text((150, y), str(val1_str), fill=c1, font=font_text)
        draw.text((450, y), str(val2_str), fill=c2, font=font_text)

    e1 = p1_data.get("games", {}).get("cs2", {}).get("faceit_elo", 0) if p1_data else 0
    e2 = p2_data.get("games", {}).get("cs2", {}).get("faceit_elo", 0) if p2_data else 0
    
    kd1 = p1_stats.get("lifetime", {}).get("Average K/D Ratio", "0") if p1_stats else "0"
    kd2 = p2_stats.get("lifetime", {}).get("Average K/D Ratio", "0") if p2_stats else "0"
    
    wr1 = p1_stats.get("lifetime", {}).get("Win Rate %", "0") if p1_stats else "0"
    wr2 = p2_stats.get("lifetime", {}).get("Win Rate %", "0") if p2_stats else "0"
    
    m1 = p1_stats.get("lifetime", {}).get("Matches", "0") if p1_stats else "0"
    m2 = p2_stats.get("lifetime", {}).get("Matches", "0") if p2_stats else "0"

    draw.rectangle([20, 130, 680, 370], fill=(33, 36, 40, 255))

    draw_stat(150, "ELO", str(e1), str(e2))
    draw_stat(200, "K/D RATIO", str(kd1), str(kd2))
    draw_stat(250, "ВІНРЕЙТ (%)", str(wr1), str(wr2))
    draw_stat(300, "МАТЧІВ", str(m1), str(m2))

    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output
