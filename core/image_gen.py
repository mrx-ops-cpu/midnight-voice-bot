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

def make_circle_avatar(img, size, stroke_color=None, stroke_width=3):
    img = img.resize(size)
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask) 
    draw.ellipse((0, 0) + size, fill=255)
    output = Image.new('RGBA', size, (0, 0, 0, 0))
    output.paste(img, (0, 0), mask=mask)
    
    if stroke_color:
        out_img = Image.new('RGBA', (size[0]+stroke_width*2, size[1]+stroke_width*2), (0,0,0,0))
        draw_out = ImageDraw.Draw(out_img)
        draw_out.ellipse((0, 0, size[0]+stroke_width*2-1, size[1]+stroke_width*2-1), outline=stroke_color, width=stroke_width)
        out_img.paste(output, (stroke_width, stroke_width), output)
        return out_img
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

def draw_rounded_rect(draw, coords, radius, fill, outline=None, width=1):
    x0, y0, x1, y1 = coords
    draw.rectangle([x0+radius, y0, x1-radius, y1], fill=fill)
    draw.rectangle([x0, y0+radius, x1, y1-radius], fill=fill)
    draw.pieslice([x0, y0, x0+radius*2, y0+radius*2], 180, 270, fill=fill)
    draw.pieslice([x1-radius*2, y0, x1, y0+radius*2], 270, 360, fill=fill)
    draw.pieslice([x0, y1-radius*2, x0+radius*2, y1], 90, 180, fill=fill)
    draw.pieslice([x1-radius*2, y1-radius*2, x1, y1], 0, 90, fill=fill)
    
    if outline:
        draw.arc([x0, y0, x0+radius*2, y0+radius*2], 180, 270, fill=outline, width=width)
        draw.arc([x1-radius*2, y0, x1, y0+radius*2], 270, 360, fill=outline, width=width)
        draw.arc([x0, y1-radius*2, x0+radius*2, y1], 90, 180, fill=outline, width=width)
        draw.arc([x1-radius*2, y1-radius*2, x1, y1], 0, 90, fill=outline, width=width)
        draw.line([x0+radius, y0, x1-radius, y0], fill=outline, width=width)
        draw.line([x0+radius, y1, x1-radius, y1], fill=outline, width=width)
        draw.line([x0, y0+radius, x0, y1-radius], fill=outline, width=width)
        draw.line([x1, y0+radius, x1, y1-radius], fill=outline, width=width)

def truncate_text(draw, text, font, max_width):
    if max_width <= 0: return ""
    if draw.textlength(text, font=font) <= max_width:
        return text
    while len(text) > 0 and draw.textlength(text + "...", font=font) > max_width:
        text = text[:-1]
    return text + "..."

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
    width = 1000
    row_height = 90
    header_height = 120
    
    height = header_height + max(1, len(top_voice_data)) * (row_height + 20)
    
    img = Image.new('RGBA', (width, height), (10, 12, 16, 255))
    
    bg_draw = ImageDraw.Draw(img)
    bg_draw.ellipse([-300, -200, 500, 600], fill=(90, 20, 150, 40))
    bg_draw.ellipse([500, -100, 1300, 700], fill=(0, 150, 255, 30))
    img = img.filter(ImageFilter.GaussianBlur(150))
    
    draw = ImageDraw.Draw(img)
    
    font_header = get_font(42, bold=True)
    font_name = get_font(38, bold=True)
    font_name_fallback = get_fallback_font(38)
    font_rank = get_font(30, bold=True)
    font_time = get_font(38, bold=True)
    
    mic_img = await fetch_image("https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/2728.png") # Sparkles emoji
    if mic_img:
        mic_img = mic_img.resize((45, 45))
        img.paste(mic_img, (50, 40), mic_img)
        
    draw.text((105, 42), "ТOП VOICE (За весь час)", fill=(0, 0, 0, 150), font=font_header)
    draw.text((103, 40), "ТOП VOICE (За весь час)", fill=(255, 255, 255, 255), font=font_header)
    
    colors = [(255, 215, 0), (192, 192, 192), (205, 127, 50), (200, 200, 200), (200, 200, 200)]
    
    overlay = Image.new('RGBA', (width, height), (0,0,0,0))
    overlay_draw = ImageDraw.Draw(overlay)
    
    y = header_height
    for i, p in enumerate(top_voice_data):
        c = colors[i] if i < len(colors) else (200, 200, 200)
        
        row_bg = (20, 25, 30, 140)
        row_outline = (c[0], c[1], c[2], 120)
        draw_rounded_rect(overlay_draw, [40, y, width - 40, y + row_height], 20, fill=row_bg, outline=row_outline, width=2)
        
        badge_w = 70
        badge_h = 40
        bx, by = 60, y + (row_height - badge_h) // 2
        
        draw_rounded_rect(overlay_draw, [bx, by, bx + badge_w, by + badge_h], 20, fill=(c[0], c[1], c[2], 30), outline=c, width=2)
        r_w = draw.textlength(f"#{i+1}", font=font_rank)
        overlay_draw.text((bx + (badge_w - r_w) // 2, by + 4), f"#{i+1}", fill=c, font=font_rank)
        
        ax, ay = 150, y + 10
        avatar_img = await fetch_image(p.get("avatar_url", ""))
        if avatar_img:
            avatar = make_circle_avatar(avatar_img, (70, 70), stroke_color=c, stroke_width=2)
            overlay.paste(avatar, (ax-2, ay-2), avatar)
        else:
            overlay_draw.ellipse([ax, ay, ax+70, ay+70], fill=(40, 45, 50))
            overlay_draw.ellipse([ax-2, ay-2, ax+72, ay+72], outline=c, width=2)
            
        time_text = p.get("time", "0")
        t_w = overlay_draw.textlength(time_text, font=font_time)
        tx, ty = width - 60 - t_w, y + 25
        
        nx, ny = 250, y + 25
        name = p.get("name", "Unknown")
        name = truncate_text(overlay_draw, name, font_name, tx - nx - 20)
        
        draw_text_fallback(overlay_draw, (nx+2, ny+2), name, fill=(0,0,0,150), primary_font=font_name, fallback_font=font_name_fallback)
        draw_text_fallback(overlay_draw, (nx, ny), name, fill=(240, 240, 245), primary_font=font_name, fallback_font=font_name_fallback)
        
        overlay_draw.text((tx+2, ty+2), time_text, fill=(0,0,0,150), font=font_time)
        overlay_draw.text((tx, ty), time_text, fill=c, font=font_time)
        
        y += row_height + 20
        
    img = Image.alpha_composite(img, overlay)
    
    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output

async def generate_streaks_image(top_streaks_data):
    width = 1000
    row_height = 90
    header_height = 120
    
    height = header_height + max(1, len(top_streaks_data)) * (row_height + 20)
    
    img = Image.new('RGBA', (width, height), (10, 12, 16, 255))
    
    bg_draw = ImageDraw.Draw(img)
    bg_draw.ellipse([-300, -200, 500, 600], fill=(200, 50, 0, 40))
    bg_draw.ellipse([500, -100, 1300, 700], fill=(255, 120, 0, 30))
    img = img.filter(ImageFilter.GaussianBlur(150))
    
    draw = ImageDraw.Draw(img)
    
    font_header = get_font(42, bold=True)
    font_name = get_font(38, bold=True)
    font_name_fallback = get_fallback_font(38)
    font_rank = get_font(30, bold=True)
    font_streak = get_font(38, bold=True)
    
    fire_header = await fetch_image("https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/1f525.png")
    if fire_header:
        fh = fire_header.resize((45, 45))
        img.paste(fh, (50, 40), fh)
    
    draw.text((105, 42), "ТОП СЕРІЇ В ВОЙСІ", fill=(0, 0, 0, 150), font=font_header)
    draw.text((103, 40), "ТОП СЕРІЇ В ВОЙСІ", fill=(255, 255, 255, 255), font=font_header)
    
    fire_img = await fetch_image("https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/1f525.png")
    if fire_img:
        fire_img = fire_img.resize((42, 42))
        
    colors = [(255, 215, 0), (192, 192, 192), (205, 127, 50), (200, 200, 200), (200, 200, 200)]
    
    overlay = Image.new('RGBA', (width, height), (0,0,0,0))
    overlay_draw = ImageDraw.Draw(overlay)
    
    y = header_height
    for i, p in enumerate(top_streaks_data):
        c = colors[i] if i < len(colors) else (200, 200, 200)
        
        row_bg = (20, 25, 30, 140)
        row_outline = (c[0], c[1], c[2], 120)
        draw_rounded_rect(overlay_draw, [40, y, width - 40, y + row_height], 20, fill=row_bg, outline=row_outline, width=2)
        
        badge_w = 70
        badge_h = 40
        bx, by = 60, y + (row_height - badge_h) // 2
        
        draw_rounded_rect(overlay_draw, [bx, by, bx + badge_w, by + badge_h], 20, fill=(c[0], c[1], c[2], 30), outline=c, width=2)
        r_w = draw.textlength(f"#{i+1}", font=font_rank)
        overlay_draw.text((bx + (badge_w - r_w) // 2, by + 4), f"#{i+1}", fill=c, font=font_rank)
        
        ax, ay = 150, y + 10
        avatar_img = await fetch_image(p.get("avatar_url", ""))
        if avatar_img:
            avatar = make_circle_avatar(avatar_img, (70, 70), stroke_color=c, stroke_width=2)
            overlay.paste(avatar, (ax-2, ay-2), avatar)
        else:
            overlay_draw.ellipse([ax, ay, ax+70, ay+70], fill=(40, 45, 50))
            overlay_draw.ellipse([ax-2, ay-2, ax+72, ay+72], outline=c, width=2)
            
        streak_txt = p.get("streak", "0")
        s_w = overlay_draw.textlength(streak_txt, font=font_streak)
        tx, ty = width - 80 - s_w, y + 25
        
        # Fire emoji
        if fire_img:
            overlay.paste(fire_img, (int(tx - 55), int(ty - 5)), fire_img)
            
        nx, ny = 250, y + 25
        name = p.get("name", "Unknown")
        name = truncate_text(overlay_draw, name, font_name, tx - 55 - nx - 10)
        
        draw_text_fallback(overlay_draw, (nx+2, ny+2), name, fill=(0,0,0,150), primary_font=font_name, fallback_font=font_name_fallback)
        draw_text_fallback(overlay_draw, (nx, ny), name, fill=(240, 240, 245), primary_font=font_name, fallback_font=font_name_fallback)
        
        overlay_draw.text((tx+2, ty+2), streak_txt, fill=(0,0,0,150), font=font_streak)
        overlay_draw.text((tx, ty), streak_txt, fill=(255, 120, 0), font=font_streak)
        
        y += row_height + 20
        
    img = Image.alpha_composite(img, overlay)
    
    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output

async def generate_games_image(top_games_data, offset=0, show_header=True):
    width = 1000
    total_h = 1000 # Hardcode height so both images are identical in size!
        
    img = Image.new('RGBA', (width, total_h), (10, 12, 16, 255))
    
    bg_draw = ImageDraw.Draw(img)
    bg_draw.ellipse([-300, -200, 500, 600], fill=(200, 20, 50, 40))
    bg_draw.ellipse([500, -100, 1300, 700], fill=(255, 100, 0, 30))
    img = img.filter(ImageFilter.GaussianBlur(150))
    
    draw = ImageDraw.Draw(img)
    
    font_header = get_font(52, bold=True)
    font_game = get_font(46, bold=True)
    font_game_fallback = get_fallback_font(46)
    font_time_game = get_font(40, bold=True)
    font_player = get_font(34)
    font_player_fallback = get_fallback_font(34)
    font_player_time = get_font(34, bold=True)
    font_rank_small = get_font(28, bold=True)
    
    if show_header:
        game_emoji = await fetch_image("https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/1f3ae.png")
        if game_emoji:
            game_emoji = game_emoji.resize((45, 45))
            img.paste(game_emoji, (50, 40), game_emoji)
        
        draw.text((105, 42), "ТOП ІГОР (За весь час)", fill=(0, 0, 0, 150), font=font_header)
        draw.text((103, 40), "ТOП ІГОР (За весь час)", fill=(255, 255, 255, 255), font=font_header)
    
    medal_colors = [(255, 215, 0), (192, 192, 192), (205, 127, 50)]
    
    overlay = Image.new('RGBA', (width, total_h), (0,0,0,0))
    overlay_draw = ImageDraw.Draw(overlay)
    
    y = 110 if show_header else 40
    
    for i, g in enumerate(top_games_data):
        players = g.get("players", [])
        
        # Make the card height more compact!
        card_h = 75 + len(players) * 60
        
        draw_rounded_rect(overlay_draw, [40, y, width - 40, y + card_h], 20, fill=(20, 25, 30, 140), outline=(255, 80, 80, 80), width=2)
        
        rank = i + 1 + offset
        c = medal_colors[i] if rank <= 3 else (150, 150, 150)
        
        draw_rounded_rect(overlay_draw, [60, y + 15, 110, y + 45], 10, fill=(c[0], c[1], c[2], 40), outline=c, width=1)
        r_txt = f"#{rank}"
        rw = overlay_draw.textlength(r_txt, font=font_rank_small)
        overlay_draw.text((60 + (50 - rw) // 2, y + 17), r_txt, fill=c, font=font_rank_small)
        
        icon_x, icon_y = 125, y + 12
        icon_url = g.get("icon_url", "")
        if icon_url:
            icon_img = await fetch_image(icon_url)
            if icon_img:
                icon_img = ImageOps.fit(icon_img, (80, 40))
                mask = Image.new('L', (80, 40), 0)
                draw_mask = ImageDraw.Draw(mask)
                draw_rounded_rect(draw_mask, [0, 0, 80, 40], 8, fill=255)
                icon_rounded = Image.new('RGBA', (80, 40), (0,0,0,0))
                icon_rounded.paste(icon_img, (0,0), mask=mask)
                overlay.paste(icon_rounded, (icon_x, icon_y), icon_rounded)
            else:
                draw_rounded_rect(overlay_draw, [icon_x, icon_y, icon_x+80, icon_y+40], 8, fill=(60, 60, 60))
        else:
            draw_rounded_rect(overlay_draw, [icon_x, icon_y, icon_x+80, icon_y+40], 8, fill=(60, 60, 60))
            
        total_t = g.get("time", "0")
        t_w = overlay_draw.textlength(total_t, font=font_time_game)
        tx, ty = width - 60 - t_w, y + 14
        
        nx, ny = 220, y + 12
        name = g.get("name", "Unknown")
        name = truncate_text(overlay_draw, name, font_game, tx - nx - 20)
        draw_text_fallback(overlay_draw, (nx+2, ny+2), name, fill=(0,0,0,150), primary_font=font_game, fallback_font=font_game_fallback)
        draw_text_fallback(overlay_draw, (nx, ny), name, fill=(255, 80, 80), primary_font=font_game, fallback_font=font_game_fallback)
        
        overlay_draw.text((tx+2, ty+2), total_t, fill=(0,0,0,150), font=font_time_game)
        overlay_draw.text((tx, ty), total_t, fill=(255, 150, 50), font=font_time_game)
        
        overlay_draw.line([60, y + 65, width - 60, y + 65], fill=(255, 255, 255, 30), width=2)
        
        py = y + 75
        
        for j, pl in enumerate(players):
            p_colors = [(255, 215, 0), (192, 192, 192)]
            pc = p_colors[j] if j < 2 else (100, 100, 100)
            
            draw_rounded_rect(overlay_draw, [60, py, width - 60, py + 50], 12, fill=(0, 0, 0, 80))
            
            rank_label = "1st" if j == 0 else "2nd"
            p_badge_w = 45
            p_badge_h = 30
            pbx, pby = 80, py + 10
            draw_rounded_rect(overlay_draw, [pbx, pby, pbx + p_badge_w, pby + p_badge_h], 8, fill=(pc[0], pc[1], pc[2], 40))
            pr_w = overlay_draw.textlength(rank_label, font=font_rank_small)
            overlay_draw.text((pbx + (p_badge_w - pr_w) // 2, pby + 2), rank_label, fill=pc, font=font_rank_small)
            
            pax, pay = 140, py + 5
            p_av = await fetch_image(pl.get("avatar_url", ""))
            if p_av:
                p_av = make_circle_avatar(p_av, (40, 40))
                overlay.paste(p_av, (pax, pay), p_av)
            else:
                overlay_draw.ellipse([pax, pay, pax+40, pay+40], fill=(60, 60, 60))
            
            pt = pl.get("time", "")
            pt_w = overlay_draw.textlength(pt, font=font_player_time)
            ptx, pty = width - 80 - pt_w, py + 8
            
            pnx, pny = 195, py + 6
            pname = pl.get("name", "")
            pname = truncate_text(overlay_draw, pname, font_player, ptx - pnx - 20)
            draw_text_fallback(overlay_draw, (pnx, pny), pname, fill=(220, 220, 225), primary_font=font_player, fallback_font=font_player_fallback)
            
            overlay_draw.text((ptx, pty), pt, fill=(255, 180, 50), font=font_player_time)
            
            py += 55
            
        y += card_h + 20
        
    img = Image.alpha_composite(img, overlay)
            
    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output
