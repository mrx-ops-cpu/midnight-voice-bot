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

async def generate_dashboard_banner(top_players):
    """
    Малює один великий красивий банер з ТОП гравцями сервера
    """
    width, height = 900, 150 + max(1, len(top_players)) * 70
    
    # Спроба завантажити красивий фон
    try:
        bg = Image.open("assets/bg.jpg").convert("RGBA")
        # Змінюємо розмір фону, щоб він покривав всю картинку, зберігаючи пропорції
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
            
        bg = bg.filter(ImageFilter.GaussianBlur(5))
        img = Image.new("RGBA", (width, height))
        img.paste(bg, (0, 0))
        # Накладаємо темний градієнт/тінь для читабельності
        overlay = Image.new("RGBA", (width, height), (20, 22, 25, 200))
        img.paste(overlay, (0, 0), overlay)
    except Exception as e:
        print("Bg err:", e)
        img = Image.new("RGBA", (width, height), (30, 33, 36, 255))
        
    draw = ImageDraw.Draw(img)

    font_title = get_font(42, bold=True)
    font_text = get_font(26, bold=True)
    font_small = get_font(20)

    draw.text((40, 30), "🏆 FACEIT DASHBOARD", fill=(255, 165, 0), font=font_title)
    
    y_offset = 100
    for i, player in enumerate(top_players):
        # Плашка гравця
        draw_rounded_rect(draw, [30, y_offset, width-30, y_offset+60], 10, (40, 45, 50, 220))
        
        # Місце
        color_rank = (255, 215, 0) if i == 0 else (192, 192, 192) if i == 1 else (205, 127, 50) if i == 2 else (150, 150, 150)
        draw.text((50, y_offset + 15), f"#{i+1}", fill=color_rank, font=font_text)
        
        # Нікнейм
        draw.text((120, y_offset + 15), player.get("nickname", "Unknown"), fill=(255, 255, 255), font=font_text)
        
        # Рівень FaceIT
        lvl = player.get("level", 1)
        level_colors = {
            1: (238, 238, 238), 2: (69, 203, 72), 3: (69, 203, 72),
            4: (255, 192, 0), 5: (255, 192, 0), 6: (255, 192, 0), 7: (255, 192, 0),
            8: (255, 110, 0), 9: (255, 110, 0), 10: (211, 44, 38)
        }
        color = level_colors.get(lvl, (255,255,255))
        draw.ellipse([600, y_offset+15, 630, y_offset+45], fill=color)
        lvl_offset = 608 if lvl < 10 else 602
        draw.text((lvl_offset, y_offset + 18), str(lvl), fill=(0, 0, 0), font=font_small)
        
        # ELO
        draw.text((700, y_offset + 15), f"ELO: {player.get('elo', 0)}", fill=(255, 165, 0), font=font_text)
        
        y_offset += 70

    if not top_players:
        draw.text((40, y_offset), "Немає прив'язаних гравців.", fill=(150, 150, 150), font=font_text)

    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output

async def generate_profile_card(nickname, player_data, stats_data, match_stats=None):
    width, height = 700, 400
    
    try:
        bg = Image.open("assets/bg.jpg").convert("RGBA")
        bg = bg.resize((width, height))
        bg = bg.filter(ImageFilter.GaussianBlur(8))
        img = Image.new("RGBA", (width, height))
        img.paste(bg, (0, 0))
        overlay = Image.new("RGBA", (width, height), (15, 18, 22, 220))
        img.paste(overlay, (0, 0), overlay)
    except:
        img = Image.new("RGBA", (width, height), (25, 28, 32, 255))
        
    draw = ImageDraw.Draw(img)

    font_title = get_font(38, bold=True)
    font_text = get_font(24, bold=True)
    font_small = get_font(20)

    draw.text((30, 25), f"Профіль: {nickname}", fill=(255, 165, 0), font=font_title)
    
    if player_data and not player_data.get('error'):
        games = player_data.get("games", {})
        cs2 = games.get("cs2", {})
        elo = cs2.get("faceit_elo", "N/A")
        lvl = cs2.get("skill_level", "N/A")
        
        draw_rounded_rect(draw, [30, 80, 670, 180], 10, (40, 45, 50, 180))
        draw.text((50, 100), f"Level: {lvl}", fill=(255, 255, 255), font=font_text)
        draw.text((250, 100), f"ELO: {elo}", fill=(255, 165, 0), font=font_text)
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
        
        draw.text((30, 200), "Останні ігри:", fill=(255, 255, 255), font=font_small)
        x_offset = 180
        for res in recent:
            color = (50, 200, 50) if str(res) == "1" else (200, 50, 50)
            draw_rounded_rect(draw, [x_offset, 200, x_offset+25, 225], 4, color)
            x_offset += 35

    if match_stats:
        draw_rounded_rect(draw, [30, 260, 670, 360], 10, (40, 45, 50, 180))
        draw.text((50, 275), "Останній матч:", fill=(255, 165, 0), font=font_text)
        draw.text((50, 315), match_stats, fill=(200, 255, 200), font=font_small)

    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output
