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
    
    # Темний фон іконки
    draw.ellipse([x, y, x+size, y+size], fill=(18, 20, 22, 255))
    
    # Малюємо дугу (arc) з розривом внизу. FaceIT стиль: від 140 до 40 градусів
    arc_width = max(2, int(size * 0.15))
    draw.arc([x + arc_width//2, y + arc_width//2, x + size - arc_width//2, y + size - arc_width//2], start=135, end=45, fill=color, width=arc_width)
    
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

async def draw_compact_card(draw, img, x_off, y_off, nickname, player_data, stats_data):
    font_elo = get_font(36, bold=True)
    font_stat_val = get_font(18, bold=True)
    font_stat_lbl = get_font(12, bold=False)
    font_nick = get_font(18, bold=True)
    font_recent = get_font(16, bold=True)
    
    draw_rounded_rect(draw, [x_off, y_off, x_off + 380, y_off + 180], 8, (33, 36, 40, 255))
    
    if not player_data or player_data.get('error'):
        draw.text((x_off + 20, y_off + 70), "Гравець не знайдений", fill=(255, 50, 50), font=font_elo)
        return

    games = player_data.get("games", {})
    cs2 = games.get("cs2", {})
    elo = cs2.get("faceit_elo", 0)
    lvl = cs2.get("skill_level", 1)
    
    draw_faceit_level(draw, x_off + 20, y_off + 15, 46, lvl, get_font(22, bold=True))
    draw.text((x_off + 80, y_off + 20), str(elo), fill=(255, 255, 255), font=font_elo)
    
    lifetime = stats_data.get("lifetime", {}) if stats_data and 'error' not in stats_data else {}
    wr = lifetime.get("Win Rate %", "-") + "%" if lifetime.get("Win Rate %", "-") != "-" else "-"
    kd = lifetime.get("Average K/D Ratio", "-")
    hs = lifetime.get("Average Headshots %", "-") + "%" if lifetime.get("Average Headshots %", "-") != "-" else "-"
    matches = lifetime.get("Matches", "-")
    
    def draw_centered(cx, y, text, font, fill):
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        draw.text((cx - w/2, y), text, fill=fill, font=font)

    draw_centered(x_off + 60, y_off + 80, str(wr), font_stat_val, (255, 255, 255))
    draw_centered(x_off + 60, y_off + 100, "Win rate", font_stat_lbl, (180, 180, 180))
    
    draw_centered(x_off + 190, y_off + 80, f"{kd} / {hs}", font_stat_val, (255, 255, 255))
    draw_centered(x_off + 190, y_off + 100, "Avg. K/D / HS", font_stat_lbl, (180, 180, 180))
    
    draw_centered(x_off + 320, y_off + 80, str(matches), font_stat_val, (255, 255, 255))
    draw_centered(x_off + 320, y_off + 100, "Matches", font_stat_lbl, (180, 180, 180))
    
    avatar_img = await fetch_image(player_data.get("avatar", ""))
    if avatar_img:
        avatar = make_circle_avatar(avatar_img, (24, 24))
        img.paste(avatar, (x_off + 20, y_off + 135), avatar)
        nick_x = x_off + 55
    else:
        nick_x = x_off + 20
        
    draw.text((nick_x, y_off + 138), nickname.upper(), fill=(255, 255, 255), font=font_nick)
    
    recent = lifetime.get("Recent Results", [])
    rx = x_off + 270
    for res in recent:
        if str(res) == "1":
            draw.text((rx, y_off + 138), "W", fill=(45, 180, 45), font=font_recent)
        else:
            draw.text((rx, y_off + 138), "L", fill=(211, 44, 38), font=font_recent)
        rx += 20

async def generate_profile_card(nickname, player_data, stats_data, match_stats=None):
    width = 400
    height = 290 if match_stats else 200
    
    img = apply_background(width, height)
    draw = ImageDraw.Draw(img)

    await draw_compact_card(draw, img, 10, 10, nickname, player_data, stats_data)

    if match_stats:
        draw_rounded_rect(draw, [10, 200, 390, 280], 8, (33, 36, 40, 255))
        draw.text((25, 210), "ОСТАННІЙ МАТЧ", fill=(255, 85, 0), font=get_font(12, bold=True))
        draw.text((25, 230), match_stats, fill=(200, 200, 200), font=get_font(14))

    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output

async def generate_compare_card(nickname1, p1_data, p1_stats, nickname2, p2_data, p2_stats):
    width, height = 820, 200
    img = apply_background(width, height)
    draw = ImageDraw.Draw(img)

    await draw_compact_card(draw, img, 10, 10, nickname1, p1_data, p1_stats)
    await draw_compact_card(draw, img, 430, 10, nickname2, p2_data, p2_stats)
    
    # VS badge in the middle
    font_vs = get_font(24, bold=True)
    bbox = draw.textbbox((0, 0), "VS", font=font_vs)
    w = bbox[2] - bbox[0]
    
    draw.ellipse([390, 80, 430, 120], fill=(22, 25, 27, 255))
    draw.ellipse([392, 82, 428, 118], outline=(255, 85, 0), width=2)
    draw.text((410 - w/2, 85), "VS", fill=(255, 85, 0), font=font_vs)

    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output
