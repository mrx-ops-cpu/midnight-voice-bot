import os
import io
import random
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

# ── Shared aesthetic helpers ──────────────────────────────────────────────────

_RANK_COLORS = [
    (255, 200, 55),   # #1 Gold (warmer)
    (180, 195, 210),  # #2 Silver (blue-ish)
    (220, 140, 65),   # #3 Bronze (warmer)
    (120, 130, 145),  # #4 Muted gray-blue
    (120, 130, 145),  # #5
]

def _build_background(width, height, orb_configs):
    """Rich dark background with gradient orbs and subtle noise grain."""
    img = Image.new('RGBA', (width, height), (12, 14, 18, 255))
    bg = ImageDraw.Draw(img)
    for (x0, y0, x1, y1, r, g, b, a) in orb_configs:
        bg.ellipse([x0, y0, x1, y1], fill=(r, g, b, a))
    img = img.filter(ImageFilter.GaussianBlur(220))
    # Noise / grain texture
    noise = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    nd = ImageDraw.Draw(noise)
    rng = random.Random(42)
    for _ in range(width * height // 40):
        nx = rng.randint(0, width - 1)
        ny = rng.randint(0, height - 1)
        v = rng.randint(180, 255)
        nd.point((nx, ny), fill=(v, v, v, rng.randint(6, 16)))
    img = Image.alpha_composite(img, noise)
    return img

def _draw_header_glow(draw, img, text, x, y, font, emoji_img=None, emoji_size=60):
    """Header text with glow effect, decorative divider, and optional emoji icon."""
    # Paste emoji icon
    if emoji_img:
        ei = emoji_img.resize((emoji_size, emoji_size))
        img.paste(ei, (x - emoji_size - 12, y + 2), ei)
    # Glow layers
    for offset, alpha in [(6, 25), (4, 45), (2, 80)]:
        draw.text((x + offset, y + offset), text, fill=(255, 255, 255, alpha), font=font)
    draw.text((x, y), text, fill=(255, 255, 255, 255), font=font)
    # Decorative divider
    tw = draw.textlength(text, font=font)
    line_y = y + 72
    mid = x + tw / 2
    total_w = tw + 80
    for i in range(int(total_w)):
        px = int(mid - total_w / 2 + i)
        dist = abs(i - total_w / 2) / (total_w / 2)
        a = int(120 * (1 - dist ** 1.5))
        if a > 0:
            draw.line([(px, line_y), (px, line_y)], fill=(255, 255, 255, a))
    for i in range(int(total_w * 0.6)):
        px = int(mid - total_w * 0.3 + i)
        dist = abs(i - total_w * 0.3) / (total_w * 0.3)
        a = int(60 * (1 - dist ** 1.5))
        if a > 0:
            draw.line([(px, line_y + 3), (px, line_y + 3)], fill=(255, 255, 255, a))


# ═══════════════════════════════════════════════════════════════════════════════
#  VOICE IMAGE
# ═══════════════════════════════════════════════════════════════════════════════

async def generate_voice_image(top_voice_data):
    width = 1200
    row_height = 110
    card_gap = 16
    header_height = 150

    height = header_height + max(1, len(top_voice_data)) * (row_height + card_gap) + 30

    # ── Background (purple + cyan orbs) ──
    orbs = [
        (-450, -350, 650, 750, 107, 33, 168, 35),
        (600, -150, 1700, 850, 8, 145, 178, 28),
        (200, int(height * 0.4), 900, int(height * 1.2), 80, 20, 140, 18),
    ]
    img = _build_background(width, height, orbs)
    draw = ImageDraw.Draw(img)

    # ── Header with glow ──
    font_header = get_font(54, bold=True)
    emoji_img = await fetch_image("https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/2728.png")
    _draw_header_glow(draw, img, "ТОП VOICE (За весь час)", 130, 35, font_header, emoji_img=emoji_img)

    # ── Fonts ──
    font_name = get_font(34, bold=True)
    font_name_fb = get_fallback_font(34)
    font_rank = get_font(28, bold=True)
    font_time = get_font(36, bold=True)
    font_label = get_font(18)

    # ── Overlay for cards ──
    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    y = header_height
    for i, p in enumerate(top_voice_data):
        c = _RANK_COLORS[i] if i < len(_RANK_COLORS) else _RANK_COLORS[-1]
        card_x0, card_x1 = 50, width - 50

        # Glassmorphism card
        draw_rounded_rect(od, [card_x0, y, card_x1, y + row_height], 18,
                          fill=(255, 255, 255, 8), outline=(255, 255, 255, 25), width=1)

        # Left accent bar
        od.rectangle([card_x0, y + 14, card_x0 + 4, y + row_height - 14], fill=c)

        # Rank badge (pill)
        badge_w, badge_h = 72, 38
        bx = card_x0 + 22
        by = y + (row_height - badge_h) // 2
        draw_rounded_rect(od, [bx, by, bx + badge_w, by + badge_h], 14,
                          fill=(c[0], c[1], c[2], 35))
        draw_rounded_rect(od, [bx, by, bx + badge_w, by + badge_h], 14,
                          fill=None, outline=(c[0], c[1], c[2], 180), width=2)
        rank_txt = f"#{i+1}"
        rw = od.textlength(rank_txt, font=font_rank)
        od.text((bx + (badge_w - rw) / 2, by + 5), rank_txt, fill=c, font=font_rank)

        # Avatar (80px with colored ring)
        ax = card_x0 + 110
        ay = y + (row_height - 80) // 2
        avatar_img = await fetch_image(p.get("avatar_url", ""))
        if avatar_img:
            avatar = make_circle_avatar(avatar_img, (80, 80), stroke_color=c, stroke_width=3)
            overlay.paste(avatar, (ax - 3, ay - 3), avatar)
        else:
            od.ellipse([ax, ay, ax + 80, ay + 80], fill=(40, 45, 50))
            od.ellipse([ax - 2, ay - 2, ax + 82, ay + 82], outline=c, width=3)

        # Time value (right side, accent colored)
        time_text = p.get("time", "0")
        t_w = od.textlength(time_text, font=font_time)
        tx = card_x1 - 35 - int(t_w)
        ty = y + (row_height - 44) // 2
        od.text((tx + 2, ty + 2), time_text, fill=(0, 0, 0, 120), font=font_time)
        od.text((tx, ty), time_text, fill=c, font=font_time)
        label = "в голосі"
        lw = od.textlength(label, font=font_label)
        od.text((tx + (t_w - lw) / 2, ty + 40), label, fill=(255, 255, 255, 60), font=font_label)

        # Name (with text shadow)
        nx = ax + 95
        ny = y + (row_height - 38) // 2
        name = normalize_name(p.get("name", "Unknown"))
        name = truncate_text(od, name, font_name, tx - nx - 25)
        draw_text_fallback(od, (nx + 2, ny + 2), name, fill=(0, 0, 0, 100),
                           primary_font=font_name, fallback_font=font_name_fb)
        draw_text_fallback(od, (nx, ny), name, fill=(240, 242, 248),
                           primary_font=font_name, fallback_font=font_name_fb)

        # Subtle separator between cards
        if i < len(top_voice_data) - 1:
            sep_y = y + row_height + card_gap // 2
            od.line([(card_x0 + 30, sep_y), (card_x1 - 30, sep_y)],
                    fill=(255, 255, 255, 15), width=1)

        y += row_height + card_gap

    img = Image.alpha_composite(img, overlay)

    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output


# ═══════════════════════════════════════════════════════════════════════════════
#  STREAKS IMAGE
# ═══════════════════════════════════════════════════════════════════════════════

async def generate_streaks_image(top_streaks_data):
    width = 1200
    row_height = 110
    card_gap = 16
    header_height = 150

    height = header_height + max(1, len(top_streaks_data)) * (row_height + card_gap) + 30

    # ── Background (amber + red orbs) ──
    orbs = [
        (-450, -350, 650, 750, 217, 119, 6, 32),
        (600, -150, 1700, 850, 220, 38, 38, 25),
        (100, int(height * 0.3), 800, int(height * 1.1), 180, 60, 10, 16),
    ]
    img = _build_background(width, height, orbs)
    draw = ImageDraw.Draw(img)

    # ── Header with glow ──
    font_header = get_font(54, bold=True)
    fire_header = await fetch_image("https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/1f525.png")
    _draw_header_glow(draw, img, "ТОП СЕРІЇ В ВОЙСІ", 130, 35, font_header, emoji_img=fire_header)

    # Fire emoji for rows
    fire_img = await fetch_image("https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/1f525.png")
    if fire_img:
        fire_img = fire_img.resize((42, 42))

    # ── Fonts ──
    font_name = get_font(34, bold=True)
    font_name_fb = get_fallback_font(34)
    font_rank = get_font(28, bold=True)
    font_streak = get_font(40, bold=True)
    font_label = get_font(18)

    # ── Overlay ──
    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    y = header_height
    for i, p in enumerate(top_streaks_data):
        c = _RANK_COLORS[i] if i < len(_RANK_COLORS) else _RANK_COLORS[-1]
        card_x0, card_x1 = 50, width - 50

        # Glassmorphism card
        draw_rounded_rect(od, [card_x0, y, card_x1, y + row_height], 18,
                          fill=(255, 255, 255, 8), outline=(255, 255, 255, 25), width=1)

        # Left accent bar
        od.rectangle([card_x0, y + 14, card_x0 + 4, y + row_height - 14], fill=c)

        # Rank badge (pill)
        badge_w, badge_h = 72, 38
        bx = card_x0 + 22
        by = y + (row_height - badge_h) // 2
        draw_rounded_rect(od, [bx, by, bx + badge_w, by + badge_h], 14,
                          fill=(c[0], c[1], c[2], 35))
        draw_rounded_rect(od, [bx, by, bx + badge_w, by + badge_h], 14,
                          fill=None, outline=(c[0], c[1], c[2], 180), width=2)
        rank_txt = f"#{i+1}"
        rw = od.textlength(rank_txt, font=font_rank)
        od.text((bx + (badge_w - rw) / 2, by + 5), rank_txt, fill=c, font=font_rank)

        # Avatar
        ax = card_x0 + 110
        ay = y + (row_height - 80) // 2
        avatar_img = await fetch_image(p.get("avatar_url", ""))
        if avatar_img:
            avatar = make_circle_avatar(avatar_img, (80, 80), stroke_color=c, stroke_width=3)
            overlay.paste(avatar, (ax - 3, ay - 3), avatar)
        else:
            od.ellipse([ax, ay, ax + 80, ay + 80], fill=(40, 45, 50))
            od.ellipse([ax - 2, ay - 2, ax + 82, ay + 82], outline=c, width=3)

        # Streak value (right side) — orange accent
        streak_txt = p.get("streak", "0")
        s_w = od.textlength(streak_txt, font=font_streak)
        tx = card_x1 - 35 - int(s_w)
        ty = y + (row_height - 50) // 2
        od.text((tx + 2, ty + 2), streak_txt, fill=(0, 0, 0, 120), font=font_streak)
        od.text((tx, ty), streak_txt, fill=(255, 140, 40), font=font_streak)
        label = "серія"
        lw = od.textlength(label, font=font_label)
        od.text((tx + (s_w - lw) / 2, ty + 44), label, fill=(255, 255, 255, 60), font=font_label)

        # Fire emoji next to streak
        if fire_img:
            overlay.paste(fire_img, (int(tx - 52), int(ty + 2)), fire_img)

        # Name (with text shadow)
        nx = ax + 95
        ny = y + (row_height - 38) // 2
        name = normalize_name(p.get("name", "Unknown"))
        max_name_w = (tx - 52 if fire_img else tx) - nx - 20
        name = truncate_text(od, name, font_name, max_name_w)
        draw_text_fallback(od, (nx + 2, ny + 2), name, fill=(0, 0, 0, 100),
                           primary_font=font_name, fallback_font=font_name_fb)
        draw_text_fallback(od, (nx, ny), name, fill=(240, 242, 248),
                           primary_font=font_name, fallback_font=font_name_fb)

        # Separator
        if i < len(top_streaks_data) - 1:
            sep_y = y + row_height + card_gap // 2
            od.line([(card_x0 + 30, sep_y), (card_x1 - 30, sep_y)],
                    fill=(255, 255, 255, 15), width=1)

        y += row_height + card_gap

    img = Image.alpha_composite(img, overlay)

    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output


# ═══════════════════════════════════════════════════════════════════════════════
#  GAMES IMAGE
# ═══════════════════════════════════════════════════════════════════════════════

async def generate_games_image(top_games_data, offset=0, show_header=True):
    width = 1200
    total_h = 1180

    # ── Background (crimson + orange orbs) ──
    orbs = [
        (-350, -250, 550, 600, 190, 18, 60, 32),
        (500, -120, 1400, 750, 234, 88, 12, 25),
        (200, 500, 1000, 1200, 160, 30, 50, 18),
    ]
    img = _build_background(width, total_h, orbs)
    draw = ImageDraw.Draw(img)

    # ── Header ──
    font_header = get_font(54, bold=True)
    if show_header:
        game_emoji = await fetch_image("https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/1f3ae.png")
        _draw_header_glow(draw, img, "ТОП ІГОР (За весь час)", 130, 35, font_header, emoji_img=game_emoji)

    # ── Fonts ──
    font_game = get_font(32, bold=True)
    font_game_fb = get_fallback_font(32)
    font_time_total = get_font(30, bold=True)
    font_player = get_font(26)
    font_player_fb = get_fallback_font(26)
    font_player_time = get_font(26, bold=True)
    font_rank = get_font(24, bold=True)
    font_player_rank = get_font(20, bold=True)

    # ── Overlay ──
    overlay = Image.new('RGBA', (width, total_h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    y = 120 if show_header else 30
    card_x0, card_x1 = 40, width - 40

    for i, g in enumerate(top_games_data):
        players = g.get("players", [])
        game_header_h = 65
        player_row_h = 52
        card_h = game_header_h + len(players) * player_row_h + 12

        rank = i + 1 + offset
        c = _RANK_COLORS[min(rank - 1, len(_RANK_COLORS) - 1)] if rank <= 3 else _RANK_COLORS[-1]

        # Glassmorphism card
        draw_rounded_rect(od, [card_x0, y, card_x1, y + card_h], 16,
                          fill=(255, 255, 255, 8), outline=(255, 255, 255, 20), width=1)

        # Left accent bar
        od.rectangle([card_x0, y + 12, card_x0 + 4, y + card_h - 12], fill=c)

        # Rank badge
        badge_w, badge_h = 64, 34
        bx = card_x0 + 18
        by = y + 16
        draw_rounded_rect(od, [bx, by, bx + badge_w, by + badge_h], 12,
                          fill=(c[0], c[1], c[2], 35))
        draw_rounded_rect(od, [bx, by, bx + badge_w, by + badge_h], 12,
                          fill=None, outline=(c[0], c[1], c[2], 180), width=2)
        r_txt = f"#{rank}"
        rw = od.textlength(r_txt, font=font_rank)
        od.text((bx + (badge_w - rw) / 2, by + 5), r_txt, fill=c, font=font_rank)

        # Game icon
        icon_x, icon_y = card_x0 + 100, y + 13
        icon_w, icon_h = 80, 40
        icon_url = g.get("icon_url", "")
        if icon_url:
            icon_img = await fetch_image(icon_url)
            if icon_img:
                icon_img = ImageOps.fit(icon_img, (icon_w, icon_h))
                mask = Image.new('L', (icon_w, icon_h), 0)
                draw_mask = ImageDraw.Draw(mask)
                draw_rounded_rect(draw_mask, [0, 0, icon_w, icon_h], 8, fill=255)
                icon_rounded = Image.new('RGBA', (icon_w, icon_h), (0, 0, 0, 0))
                icon_rounded.paste(icon_img, (0, 0), mask=mask)
                overlay.paste(icon_rounded, (icon_x, icon_y), icon_rounded)
            else:
                draw_rounded_rect(od, [icon_x, icon_y, icon_x + icon_w, icon_y + icon_h], 8, fill=(60, 60, 60))
        else:
            draw_rounded_rect(od, [icon_x, icon_y, icon_x + icon_w, icon_y + icon_h], 8, fill=(60, 60, 60))

        # Total time (right side, warm amber)
        total_t = g.get("time", "0")
        ttw = od.textlength(total_t, font=font_time_total)
        ttx = card_x1 - 30 - int(ttw)
        tty = y + 18
        od.text((ttx + 2, tty + 2), total_t, fill=(0, 0, 0, 100), font=font_time_total)
        od.text((ttx, tty), total_t, fill=(255, 175, 55), font=font_time_total)

        # Game name (soft coral red)
        gnx = icon_x + icon_w + 18
        gny = y + 18
        gname = g.get("name", "Unknown")
        gname = truncate_text(od, gname, font_game, ttx - gnx - 20)
        draw_text_fallback(od, (gnx + 2, gny + 2), gname, fill=(0, 0, 0, 100),
                           primary_font=font_game, fallback_font=font_game_fb)
        draw_text_fallback(od, (gnx, gny), gname, fill=(255, 100, 110),
                           primary_font=font_game, fallback_font=font_game_fb)

        # Thin divider between game header and player rows
        div_y = y + game_header_h - 4
        od.line([(card_x0 + 20, div_y), (card_x1 - 20, div_y)],
                fill=(255, 255, 255, 25), width=1)

        # ── Player sub-rows ──
        py = y + game_header_h + 4
        medal_labels = ["\U0001f947", "\U0001f948"]  # 🥇 🥈

        for j, pl in enumerate(players):
            pc = _RANK_COLORS[j] if j < 2 else _RANK_COLORS[-1]

            # Sub-row background
            draw_rounded_rect(od, [card_x0 + 14, py, card_x1 - 14, py + player_row_h - 4], 10,
                              fill=(0, 0, 0, 50))

            # Rank label (medal emoji or #N)
            rank_label = medal_labels[j] if j < len(medal_labels) else f"#{j+1}"
            rl_w = od.textlength(rank_label, font=font_player_rank)
            pbx = card_x0 + 28
            pby = py + 8
            p_badge_w = max(50, int(rl_w) + 20)
            p_badge_h = player_row_h - 16
            draw_rounded_rect(od, [pbx, pby, pbx + p_badge_w, pby + p_badge_h], 8,
                              fill=(pc[0], pc[1], pc[2], 30))
            od.text((pbx + (p_badge_w - rl_w) / 2, pby + 4), rank_label, fill=pc, font=font_player_rank)

            # Player avatar
            pax = pbx + p_badge_w + 14
            pay = py + (player_row_h - 40) // 2
            p_av = await fetch_image(pl.get("avatar_url", ""))
            if p_av:
                p_av = make_circle_avatar(p_av, (36, 36))
                overlay.paste(p_av, (pax, pay), p_av)
            else:
                od.ellipse([pax, pay, pax + 36, pay + 36], fill=(60, 60, 60))

            # Player time (right, warm amber)
            pt = pl.get("time", "")
            pt_w = od.textlength(pt, font=font_player_time)
            ptx = card_x1 - 40 - int(pt_w)
            pty = py + (player_row_h - 30) // 2
            od.text((ptx + 1, pty + 1), pt, fill=(0, 0, 0, 80), font=font_player_time)
            od.text((ptx, pty), pt, fill=(255, 175, 55), font=font_player_time)

            # Player name
            pnx = pax + 48
            pny = py + (player_row_h - 30) // 2
            pname = normalize_name(pl.get("name", ""))
            pname = truncate_text(od, pname, font_player, ptx - pnx - 20)
            draw_text_fallback(od, (pnx + 1, pny + 1), pname, fill=(0, 0, 0, 80),
                               primary_font=font_player, fallback_font=font_player_fb)
            draw_text_fallback(od, (pnx, pny), pname, fill=(225, 228, 235),
                               primary_font=font_player, fallback_font=font_player_fb)

            py += player_row_h

        y += card_h + 14

    img = Image.alpha_composite(img, overlay)

    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output
