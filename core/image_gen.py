import os
import io
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter
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
    try:
        bg = Image.open("assets/bg.jpg").convert("RGBA")
        bg_ratio = bg.width / bg.height
        target_ratio = width / height
        if bg_ratio > target_ratio:
            new_width = int(height * bg_ratio)
            bg = bg.resize((new_width, height))
            left = (new_width - width) // 2
            bg = bg.crop((left, 0, left + width, height))
        else:
            new_height = int(width / bg_ratio)
            bg = bg.resize((width, new_height))
            top = (new_height - height) // 2
            bg = bg.crop((0, top, width, top + height))
            
        bg = bg.filter(ImageFilter.GaussianBlur(2)) # Мінімум розмиття
        img = Image.new("RGBA", (width, height))
        img.paste(bg, (0, 0))
        overlay = Image.new("RGBA", (width, height), (20, 22, 25, 220)) # Темніший оверлей для стилю фейсіт
        img.paste(overlay, (0, 0), overlay)
        return img
    except:
        return Image.new("RGBA", (width, height), (25, 27, 31, 255))

async def generate_dashboard_banner(top_players):
    """
    top_players is a list of dicts: nickname, elo, level, stats_data
    """
    width, height = 900, 120 + max(1, len(top_players)) * 75
    img = apply_background(width, height)
    draw = ImageDraw.Draw(img)

    font_title = get_font(36, bold=True)
    font_text = get_font(24, bold=True)
    font_small = get_font(18)
    font_tiny = get_font(14, bold=True)

    draw.text((40, 30), "FACEIT DASHBOARD", fill=(255, 85, 0), font=font_title) # Колір FaceIT (Помаранчевий)
    
    y_offset = 90
    for i, player in enumerate(top_players):
        # Плашка гравця (трохи темніша, FaceIT стиль)
        draw_rounded_rect(draw, [30, y_offset, width-30, y_offset+65], 8, (35, 40, 45, 230))
        
        # Місце
        color_rank = (255, 215, 0) if i == 0 else (192, 192, 192) if i == 1 else (205, 127, 50) if i == 2 else (130, 130, 130)
        draw.text((45, y_offset + 18), f"#{i+1}", fill=color_rank, font=font_text)
        
        # Нікнейм
        draw.text((100, y_offset + 10), player.get("nickname", "Unknown"), fill=(240, 240, 240), font=font_text)
        
        # Статистика (KD, WR) під нікнеймом
        stats_data = player.get("stats_data", {})
        lifetime = stats_data.get("lifetime", {}) if stats_data and 'error' not in stats_data else {}
        kd = lifetime.get("Average K/D Ratio", "-")
        wr = lifetime.get("Win Rate %", "-")
        draw.text((100, y_offset + 40), f"K/D: {kd}  |  Win: {wr}%", fill=(150, 150, 150), font=font_small)

        # 5 Останніх матчів
        recent = lifetime.get("Recent Results", [])
        rx = 350
        for res in recent:
            if str(res) == "1":
                draw_rounded_rect(draw, [rx, y_offset+20, rx+25, y_offset+45], 4, (45, 150, 45, 255))
                draw.text((rx+6, y_offset+23), "W", fill=(255, 255, 255), font=font_tiny)
            else:
                draw_rounded_rect(draw, [rx, y_offset+20, rx+25, y_offset+45], 4, (200, 50, 50, 255))
                draw.text((rx+8, y_offset+23), "L", fill=(255, 255, 255), font=font_tiny)
            rx += 32

        # Рівень FaceIT
        lvl = player.get("level", 1)
        level_colors = {
            1: (238, 238, 238), 2: (69, 203, 72), 3: (69, 203, 72),
            4: (255, 192, 0), 5: (255, 192, 0), 6: (255, 192, 0), 7: (255, 192, 0),
            8: (255, 110, 0), 9: (255, 110, 0), 10: (211, 44, 38)
        }
        color = level_colors.get(lvl, (255,255,255))
        draw.ellipse([640, y_offset+18, 670, y_offset+48], fill=color)
        lvl_offset = 648 if lvl < 10 else 642
        draw.text((lvl_offset, y_offset + 21), str(lvl), fill=(0, 0, 0), font=font_small)
        
        # ELO
        draw.text((720, y_offset + 18), f"ELO: {player.get('elo', 0)}", fill=(255, 255, 255), font=font_text)
        
        y_offset += 75

    if not top_players:
        draw.text((40, y_offset), "Немає прив'язаних гравців.", fill=(150, 150, 150), font=font_text)

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
    font_tiny = get_font(14, bold=True)

    draw.text((30, 25), f"ПРОФІЛЬ: {nickname.upper()}", fill=(255, 85, 0), font=font_title)
    
    if player_data and not player_data.get('error'):
        games = player_data.get("games", {})
        cs2 = games.get("cs2", {})
        elo = cs2.get("faceit_elo", "N/A")
        lvl = cs2.get("skill_level", "N/A")
        
        draw_rounded_rect(draw, [30, 80, 670, 180], 8, (35, 40, 45, 230))
        draw.text((50, 100), f"Level: {lvl}", fill=(255, 255, 255), font=font_text)
        draw.text((250, 100), f"ELO: {elo}", fill=(255, 85, 0), font=font_text)
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
        x_offset = 180
        for res in recent:
            if str(res) == "1":
                draw_rounded_rect(draw, [x_offset, 195, x_offset+30, 225], 4, (45, 150, 45, 255))
                draw.text((x_offset+8, 200), "W", fill=(255, 255, 255), font=font_tiny)
            else:
                draw_rounded_rect(draw, [x_offset, 195, x_offset+30, 225], 4, (200, 50, 50, 255))
                draw.text((x_offset+10, 200), "L", fill=(255, 255, 255), font=font_tiny)
            x_offset += 40

    if match_stats:
        draw_rounded_rect(draw, [30, 250, 670, 350], 8, (35, 40, 45, 230))
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
    
    # Headers
    draw.text((250, 80), nickname1.upper(), fill=(255, 255, 255), font=font_text)
    draw.text((500, 80), nickname2.upper(), fill=(255, 255, 255), font=font_text)
    
    # Helper to compare
    def draw_stat(y, label, val1_str, val2_str, reverse=False):
        draw.text((30, y), label, fill=(150, 150, 150), font=font_small)
        try:
            v1 = float(val1_str.replace('%', ''))
            v2 = float(val2_str.replace('%', ''))
            c1 = (45, 150, 45) if (v1 > v2 and not reverse) or (v1 < v2 and reverse) else ((200, 50, 50) if v1 != v2 else (200,200,200))
            c2 = (45, 150, 45) if (v2 > v1 and not reverse) or (v2 < v1 and reverse) else ((200, 50, 50) if v1 != v2 else (200,200,200))
        except:
            c1 = c2 = (200, 200, 200)
            
        draw.text((250, y), str(val1_str), fill=c1, font=font_text)
        draw.text((500, y), str(val2_str), fill=c2, font=font_text)

    # Get data
    e1 = p1_data.get("games", {}).get("cs2", {}).get("faceit_elo", 0) if p1_data else 0
    e2 = p2_data.get("games", {}).get("cs2", {}).get("faceit_elo", 0) if p2_data else 0
    
    kd1 = p1_stats.get("lifetime", {}).get("Average K/D Ratio", "0") if p1_stats else "0"
    kd2 = p2_stats.get("lifetime", {}).get("Average K/D Ratio", "0") if p2_stats else "0"
    
    wr1 = p1_stats.get("lifetime", {}).get("Win Rate %", "0") if p1_stats else "0"
    wr2 = p2_stats.get("lifetime", {}).get("Win Rate %", "0") if p2_stats else "0"
    
    m1 = p1_stats.get("lifetime", {}).get("Matches", "0") if p1_stats else "0"
    m2 = p2_stats.get("lifetime", {}).get("Matches", "0") if p2_stats else "0"

    draw_rounded_rect(draw, [20, 120, 680, 360], 8, (35, 40, 45, 230))

    draw_stat(140, "ELO", str(e1), str(e2))
    draw_stat(190, "K/D RATIO", str(kd1), str(kd2))
    draw_stat(240, "ВІНРЕЙТ (%)", str(wr1), str(wr2))
    draw_stat(290, "МАТЧІВ", str(m1), str(m2))

    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output
