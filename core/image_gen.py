import os
import io
import unicodedata
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from io import BytesIO

def normalize_name(name):
    """Convert fancy Unicode (𝘼𝙧𝙩𝙚𝙢) to normal readable text (Artem)"""
    return unicodedata.normalize('NFKC', name) if name else name

async def fetch_image(url):
    try:
        if not url: return None
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"}) as resp:
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
    # Fonts ordered by Unicode coverage (widest first)
    if bold:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux/Railway
            "C:/Windows/Fonts/segoeui.ttf",   # Windows
            "Roboto-Bold.ttf",
            "arial.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux/Railway
            "C:/Windows/Fonts/segoeui.ttf",   # Windows  
            "Roboto-Regular.ttf",
            "arial.ttf",
        ]
    for font_path in candidates:
        try:
            return ImageFont.truetype(font_path, size)
        except:
            continue
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
        font_micro = get_font(10, bold=True)
        for res in recent:
            if str(res) == "1":
                draw.rectangle([rx, y_offset + 18, rx + 14, y_offset + 32], fill=(45, 150, 45, 255))
                draw.text((rx + 3, y_offset + 19), "W", fill=(255, 255, 255), font=font_micro)
            else:
                draw.rectangle([rx, y_offset + 18, rx + 14, y_offset + 32], fill=(200, 50, 50, 255))
                draw.text((rx + 4, y_offset + 19), "L", fill=(255, 255, 255), font=font_micro)
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

async def generate_active_players_banner(active_matches):
    """
    active_matches: list of dicts:
      {
        "match_id": str,
        "map": str,
        "status": str,
        "score": str,
        "players": [{"nickname": str, "avatar": str, "team": str, "elo": int, "level": int}],
      }
    """
    row_height = 50
    header_height = 40
    match_header_height = 40
    width = 900

    if not active_matches:
        height = header_height + row_height
        img = apply_background(width, height)
        draw = ImageDraw.Draw(img)
        
        font_title = get_font(16, bold=True)
        font_sub = get_font(14)
        
        # Header
        draw.rectangle([0, 0, width, header_height], fill=(22, 25, 27, 255))
        draw.ellipse([20, 12, 32, 24], fill=(80, 80, 80))
        draw.text((40, 10), "LIVE MATCHES", fill=(80, 80, 80), font=font_title)
        
        # Empty row
        draw.rectangle([0, header_height, width, header_height + row_height], fill=(33, 36, 40, 255))
        draw.text((40, header_height + 15), "Зараз ніхто не грає", fill=(100, 100, 100), font=font_sub)
        
        output = BytesIO()
        img.save(output, format="PNG")
        output.seek(0)
        return output

    # Calculate height
    total_player_rows = sum(len(m.get("players", [])) for m in active_matches)
    height = header_height + len(active_matches) * match_header_height + total_player_rows * row_height
    
    img = apply_background(width, height)
    draw = ImageDraw.Draw(img)

    font_title = get_font(16, bold=True)
    font_header = get_font(14, bold=True)
    font_text = get_font(16, bold=True)
    font_small = get_font(14, bold=True)
    font_status = get_font(11, bold=True)
    font_lvl = get_font(13, bold=True)

    header_color = (113, 118, 122)

    # Main header
    draw.rectangle([0, 0, width, header_height], fill=(22, 25, 27, 255))
    draw.ellipse([20, 12, 32, 24], fill=(45, 180, 45))
    draw.text((40, 10), "LIVE MATCHES", fill=(45, 180, 45), font=font_title)
    
    count_text = f"{len(active_matches)} active"
    bbox = draw.textbbox((0, 0), count_text, font=font_small)
    draw.text((width - (bbox[2] - bbox[0]) - 20, 12), count_text, fill=(100, 100, 100), font=font_small)

    y = header_height

    for match in active_matches:
        map_name = match.get("map", "Unknown")
        status = match.get("status", "unknown").upper()
        players = match.get("players", [])
        
        # Match header bar
        draw.rectangle([0, y, width, y + match_header_height], fill=(22, 25, 27, 255))
        draw.rectangle([0, y, 4, y + match_header_height], fill=(255, 85, 0))
        
        draw.text((20, y + 11), f"CS2  ·  {map_name}", fill=(255, 85, 0), font=font_header)
        
        # Status badge
        if status in ("ONGOING", "LIVE", "READY", "CONFIGURING", "VOTING"):
            badge_color = (45, 180, 45)
            badge_text = "LIVE"
        elif status == "FINISHED":
            badge_color = (80, 80, 80)
            badge_text = "FINISHED"
        else:
            badge_color = (255, 192, 0)
            badge_text = status
            
        bbox = draw.textbbox((0, 0), badge_text, font=font_status)
        bw = bbox[2] - bbox[0]
        draw_rounded_rect(draw, [300, y + 10, 300 + bw + 14, y + 28], 4, badge_color)
        draw.text((307, y + 12), badge_text, fill=(0, 0, 0), font=font_status)
        
        # Party badge
        if len(players) > 1:
            party_text = f"PARTY ({len(players)})"
            bbox = draw.textbbox((0, 0), party_text, font=font_status)
            pw = bbox[2] - bbox[0]
            draw_rounded_rect(draw, [width - pw - 34, y + 10, width - 20, y + 28], 4, (110, 70, 200))
            draw.text((width - pw - 27, y + 12), party_text, fill=(255, 255, 255), font=font_status)
        
        y += match_header_height
        
        # Player rows (same style as dashboard)
        for j, player in enumerate(players):
            bg_color = (33, 36, 40, 255) if j % 2 == 0 else (28, 30, 34, 255)
            draw.rectangle([0, y, width, y + row_height], fill=bg_color)
            
            # Avatar
            avatar_img = await fetch_image(player.get("avatar", ""))
            if avatar_img:
                avatar = make_circle_avatar(avatar_img, (34, 34))
                img.paste(avatar, (25, y + 8), avatar)
            
            # Nickname
            draw.text((70, y + 15), player.get("nickname", "Unknown"), fill=(240, 240, 240), font=font_text)
            
            # Level icon + ELO
            lvl = player.get("level", 1)
            elo = player.get("elo", 0)
            draw_faceit_level(draw, 350, y + 12, 26, lvl, font_lvl)
        candidates = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/segoeui.ttf", "Roboto-Regular.ttf", "arial.ttf"]
        
    for font_path in candidates:
        try:
            return ImageFont.truetype(font_path, size)
        except:
            continue
    return ImageFont.load_default()

def get_fallback_font(size):
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Try Segoe UI Symbol first (it has Fraktur like 𝕯)
        font_path = "C:/Windows/Fonts/seguisym.ttf"
        if not os.path.exists(font_path):
            font_path = os.path.join(base_dir, "fonts", "seguisym.ttf")
        return ImageFont.truetype(font_path, size)
    except:
        return get_font(size)

def draw_text_fallback(draw, xy, text, fill, primary_font, fallback_font):
    if not text: return
    x, y = xy
    for char in text:
        code = ord(char)
        if code > 0xFFFF or (0x2100 <= code <= 0x214F): 
            font = fallback_font
        else:
            font = primary_font
            
        draw.text((x, y), char, fill=fill, font=font)
        x += font.getlength(char)

def apply_background(width, height):
    img = Image.new("RGBA", (width, height), (22, 25, 27, 255))
    return img

async def generate_voice_image(top_voice_data):
    width = 1600
    row_height = 110
    header_height = 80
    
    height = header_height + max(1, len(top_voice_data)) * row_height
    img = apply_background(width, height)
    draw = ImageDraw.Draw(img)
    
    font_header = get_font(30, bold=True)
    font_text = get_font(36, bold=True)
    font_text_fallback = get_fallback_font(36)
    font_rank = get_font(32, bold=True)
    font_time = get_font(36, bold=True)
    
    draw.rectangle([0, 0, width, header_height], fill=(22, 25, 27, 255))
    
    mic_img = await fetch_image("https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/1f3a4.png")
    if mic_img:
        mic_img = mic_img.resize((40, 40))
        img.paste(mic_img, (30, 20), mic_img)
    
    draw.text((85, 20), "TOP VOICE (За весь час)", fill=(220, 220, 220), font=font_header)
    
    y = header_height
    for i, p in enumerate(top_voice_data):
        bg_color = (33, 36, 40, 255) if i % 2 == 0 else (28, 30, 34, 255)
        draw.rectangle([0, y, width, y + row_height], fill=bg_color)
        
        color_rank = (255, 215, 0) if i == 0 else (192, 192, 192) if i == 1 else (205, 127, 50) if i == 2 else (60, 60, 60)
        draw.rectangle([0, y, 8, y + row_height], fill=color_rank)
        draw.text((40, y + 35), f"#{i+1}", fill=color_rank, font=font_rank)
        
        avatar_img = await fetch_image(p.get("avatar_url", ""))
        if avatar_img:
            avatar = make_circle_avatar(avatar_img, (80, 80))
            img.paste(avatar, (120, y + 15), avatar)
        else:
            draw.ellipse([120, y+15, 200, y+95], fill=(60, 60, 60))
            
        name = p.get("name", "Unknown")
        draw_text_fallback(draw, (230, y + 33), name, fill=(240, 240, 240), primary_font=font_text, fallback_font=font_text_fallback)
        
        time_text = p.get("time", "0")
        bbox = draw.textbbox((0, 0), time_text, font=font_time)
        tw = bbox[2] - bbox[0]
        draw.text((width - tw - 40, y + 33), time_text, fill=(255, 180, 50), font=font_time)
        
        y += row_height
        
    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output

async def generate_streaks_image(top_streaks_data):
    width = 1600
    row_height = 110
    header_height = 80
    
    height = header_height + max(1, len(top_streaks_data)) * row_height
    img = apply_background(width, height)
    draw = ImageDraw.Draw(img)
    
    font_header = get_font(30, bold=True)
    font_text = get_font(36, bold=True)
    font_text_fallback = get_fallback_font(36)
    font_rank = get_font(32, bold=True)
    font_streak = get_font(36, bold=True)
    
    draw.rectangle([0, 0, width, header_height], fill=(22, 25, 27, 255))
    
    fire_header = await fetch_image("https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/1f525.png")
    if fire_header:
        fh = fire_header.resize((40, 40))
        img.paste(fh, (30, 20), fh)
    
    draw.text((85, 20), "ТОП СЕРІЇ В ВОЙСІ", fill=(220, 220, 220), font=font_header)
    
    fire_img = await fetch_image("https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/1f525.png")
    if fire_img:
        fire_img = fire_img.resize((42, 42))
    
    y = header_height
    for i, p in enumerate(top_streaks_data):
        bg_color = (33, 36, 40, 255) if i % 2 == 0 else (28, 30, 34, 255)
        draw.rectangle([0, y, width, y + row_height], fill=bg_color)
        
        color_rank = (255, 215, 0) if i == 0 else (192, 192, 192) if i == 1 else (205, 127, 50) if i == 2 else (60, 60, 60)
        draw.rectangle([0, y, 8, y + row_height], fill=color_rank)
        draw.text((40, y + 35), f"#{i+1}", fill=color_rank, font=font_rank)
        
        avatar_img = await fetch_image(p.get("avatar_url", ""))
        if avatar_img:
            avatar = make_circle_avatar(avatar_img, (80, 80))
            img.paste(avatar, (120, y + 15), avatar)
        else:
            draw.ellipse([120, y+15, 200, y+95], fill=(60, 60, 60))
            
        name = p.get("name", "Unknown")
        draw_text_fallback(draw, (230, y + 33), name, fill=(240, 240, 240), primary_font=font_text, fallback_font=font_text_fallback)
        
        streak_text = p.get("streak", "0")
        bbox = draw.textbbox((0, 0), streak_text, font=font_streak)
        tw = bbox[2] - bbox[0]
        text_x = width - tw - 40
        
        if fire_img:
            img.paste(fire_img, (text_x - 55, y + 33), fire_img)
            
        draw.text((text_x, y + 35), streak_text, fill=(255, 120, 0), font=font_streak)
        
        y += row_height
        
    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output

async def generate_games_image(top_games_data, offset=0, show_header=True):
    width = 1600
    game_header_height = 70
    player_row_height = 55
    header_height = 70 if show_header else 0
    
    total_h = header_height
    for g in top_games_data:
        total_h += game_header_height
        players = g.get("players", [])
        total_h += max(1, len(players)) * player_row_height
    if not top_games_data:
        total_h += game_header_height
    
    img = apply_background(width, total_h)
    draw = ImageDraw.Draw(img)
    
    font_header = get_font(30, bold=True)
    font_game = get_font(36, bold=True)
    font_time_game = get_font(36, bold=True)
    font_player = get_font(36, bold=True)
    font_player_fallback = get_fallback_font(36)
    font_player_time = get_font(36, bold=True)
    font_rank_small = get_font(24, bold=True)
    
    if show_header:
        draw.rectangle([0, 0, width, header_height], fill=(22, 25, 27, 255))
        
        game_emoji = await fetch_image("https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/1f3ae.png")
        if game_emoji:
            game_emoji = game_emoji.resize((40, 40))
            img.paste(game_emoji, (30, 15), game_emoji)
        
        draw.text((85, 15), "TOP ІГОР (За весь час)", fill=(220, 220, 220), font=font_header)
    
    medal_colors = [(255, 215, 0), (192, 192, 192), (205, 127, 50)]
    
    y = header_height
    for i, g in enumerate(top_games_data):
        draw.rectangle([0, y, width, y + game_header_height], fill=(42, 47, 52, 255))
        
        rank_idx = i + offset
        color_rank = medal_colors[rank_idx] if rank_idx < 3 else (200, 200, 200)
        draw.rectangle([0, y, 8, y + game_header_height], fill=color_rank)
        
        draw.text((20, y + 20), f"#{rank_idx+1}", fill=color_rank, font=font_rank_small)
        
        icon_url = g.get("icon_url", "")
        icon_x = 90
        if icon_url:
            icon_img = await fetch_image(icon_url)
            if icon_img:
                icon_img = icon_img.resize((50, 50))
                img.paste(icon_img, (icon_x, y + 10))
            else:
                draw.rectangle([icon_x, y+10, icon_x+50, y+60], fill=(60, 60, 60))
        else:
            draw.rectangle([icon_x, y+10, icon_x+50, y+60], fill=(60, 60, 60))
        
        # Red Game Name
        draw.text((icon_x + 65, y + 13), g.get("name", "Unknown"), fill=(255, 60, 60), font=font_game)
        
        total_t = g.get("time", "0")
        bbox = draw.textbbox((0, 0), total_t, font=font_time_game)
        tw = bbox[2] - bbox[0]
        draw.text((width - tw - 40, y + 13), total_t, fill=(255, 180, 50), font=font_time_game)
        
        y += game_header_height
        
        players = g.get("players", [])
        for j, pl in enumerate(players):
            bg_pl = (32, 35, 40, 255) if j % 2 == 0 else (24, 27, 31, 255)
            draw.rectangle([0, y, width, y + player_row_height], fill=bg_pl)
            
            p_colors = [(255, 215, 0), (192, 192, 192)]
            p_color = p_colors[j] if j < 2 else (100, 100, 100)
            
            rank_label = "1st" if j == 0 else "2nd"
            
            # Dynamically size the rank badge
            r_bbox = draw.textbbox((0, 0), rank_label, font=font_rank_small)
            rtw = r_bbox[2] - r_bbox[0]
            
            box_width = max(50, rtw + 16)
            box_height = 28
            
            bx1 = 55
            by1 = y + 14
            bx2 = bx1 + box_width
            by2 = by1 + box_height
            
            draw_rounded_rect(draw, [bx1, by1, bx2, by2], 6, (p_color[0], p_color[1], p_color[2], 40))
            draw.text((bx1 + (box_width - rtw) // 2, by1 + 4), rank_label, fill=p_color, font=font_rank_small)
            
            pl_avatar = await fetch_image(pl.get("avatar_url", ""))
            if pl_avatar:
                pa = make_circle_avatar(pl_avatar, (45, 45))
                img.paste(pa, (120, y + 5), pa)
            else:
                draw.ellipse([120, y+5, 165, y+50], fill=(60, 60, 60))
            
            name = pl.get("name", "")
            draw_text_fallback(draw, (180, y + 8), name, fill=(200, 200, 200), primary_font=font_player, fallback_font=font_player_fallback)
            
            pt = pl.get("time", "")
            bbox = draw.textbbox((0, 0), pt, font=font_player_time)
            ptw = bbox[2] - bbox[0]
            draw.text((width - ptw - 40, y + 8), pt, fill=(255, 180, 50), font=font_player_time)
            
            y += player_row_height
            
    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output
