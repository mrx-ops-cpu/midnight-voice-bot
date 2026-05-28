import os
import io
import random
import unicodedata
import aiohttp
os.system('python -m playwright install chromium')
os.system('python -m playwright install-deps chromium')
from playwright.async_api import async_playwright
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

async def render_html_to_image(html_content, width=600):
    from io import BytesIO
    import shutil
    async with async_playwright() as p:
        executable_path = shutil.which("chromium") or shutil.which("google-chrome") or shutil.which("chromium-browser")
        launch_args = {"args": ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]}
        if executable_path:
            launch_args["executable_path"] = executable_path
            
        browser = await p.chromium.launch(**launch_args)
        # Scale 2.0 for high resolution rendering
        page = await browser.new_page(device_scale_factor=2.0)
        await page.set_content(html_content)
        await page.wait_for_timeout(500) # give time for fonts/images to load
        
        # We find the body element or a specific wrapper to screenshot exactly its height
        screenshot_bytes = await page.locator(".container").screenshot(omit_background=True)
        await browser.close()
        
    return BytesIO(screenshot_bytes)

async def generate_voice_image(top_voice_data):
    cards_html = ""
    for i, p in enumerate(top_voice_data):
        rank = i + 1
        name = p.get('name', 'Unknown')
        time = p.get('time', '0')
        avatar = p.get('avatar_url', '') or 'https://ui-avatars.com/api/?background=random&name=' + name.replace(" ", "+")
        
        c_class = min(rank, 3)
        
        cards_html += f'''
        <div class="card">
            <div class="shield-container outline-{c_class}">
                <svg class="shield-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
                </svg>
                <div class="rank-text color-{c_class}">#{rank}</div>
            </div>
            <div class="avatar-container"><div class="avatar-img" style="background-image: url('{avatar}');"></div></div>
            <div class="player-info">
                <div class="player-name">{name}</div>
                <div class="time-box">
                    <div class="voice-time">{time}</div>
                    <div class="voice-sub">в голосі</div>
                </div>
            </div>
        </div>
        '''

    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
            body {{
                background-color: #08070d;
                background-image: radial-gradient(circle at 20% 40%, rgba(90, 40, 150, 0.4) 0%, transparent 50%),
                                  radial-gradient(circle at 80% 60%, rgba(40, 120, 150, 0.4) 0%, transparent 50%);
                font-family: 'Inter', sans-serif; color: white; padding: 30px; width: 600px; margin: 0; box-sizing: border-box; -webkit-font-smoothing: antialiased;
            }}
            .header {{ text-align: center; font-size: 26px; font-weight: 900; color: #a461f5; text-shadow: 0 0 15px rgba(164, 97, 245, 0.8); margin-bottom: 25px; text-transform: uppercase; }}
            .container {{ background: #18191c; border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 14px; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.6); }}
            .container-top {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }}
            .top-label {{ font-size: 14px; font-weight: 800; color: #b0b5bd; display: flex; align-items: center; gap: 8px; }}
            .voice-btn {{ background: rgba(30, 80, 40, 0.2); border: 1px solid rgba(60, 150, 60, 0.4); color: #4ade80; padding: 5px 12px; border-radius: 6px; font-size: 12px; font-weight: 800; display: flex; align-items: center; gap: 6px; text-shadow: 0 0 8px rgba(74, 222, 128, 0.4); }}
            .card {{ background: rgba(30, 32, 38, 0.6); border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 12px; padding: 12px 18px; margin-bottom: 12px; display: flex; align-items: center; position: relative; backdrop-filter: blur(10px); }}
            .card:last-child {{ margin-bottom: 0; }}
            .shield-container {{ width: 38px; height: 44px; position: relative; display: flex; justify-content: center; align-items: center; margin-right: 18px; flex-shrink: 0; }}
            .shield-svg {{ position: absolute; width: 100%; height: 100%; top: 0; left: 0; }}
            .rank-text {{ font-size: 14px; font-weight: 800; z-index: 2; }}
            .avatar-container {{ width: 48px; height: 48px; border-radius: 50%; position: relative; margin-right: 18px; flex-shrink: 0; border: 2px solid rgba(255,255,255,0.1); }}
            .avatar-img {{ width: 100%; height: 100%; border-radius: 50%; background-size: cover; background-position: center; }}
            .player-info {{ flex: 1; display: flex; justify-content: space-between; align-items: center; }}
            .player-name {{ font-size: 16px; font-weight: 800; color: #ffffff; text-shadow: 0 0 8px rgba(255, 255, 255, 0.3); }}
            .time-box {{ display: flex; flex-direction: column; align-items: flex-end; }}
            .voice-time {{ font-size: 18px; font-weight: 800; color: #f7a93b; text-shadow: 0 0 10px rgba(247, 169, 59, 0.6); }}
            .voice-sub {{ font-size: 10px; font-weight: 600; color: #8a8a93; text-transform: uppercase; letter-spacing: 1px; margin-top: 2px; }}
            .color-1 {{ color: #f6a125; }} .color-2 {{ color: #a4b4c4; }} .color-3 {{ color: #cd7f32; }}
            .outline-1 {{ color: #f6a125; filter: drop-shadow(0 0 4px rgba(246,161,37,0.8)); }}
            .outline-2 {{ color: #a4b4c4; filter: drop-shadow(0 0 4px rgba(164,180,196,0.8)); }}
            .outline-3 {{ color: #cd7f32; filter: drop-shadow(0 0 4px rgba(205,127,50,0.8)); }}
        </style>
    </head>
    <body>
        <div class="header">💜 ТОП VOICE</div>
        <div class="container">
            <div class="container-top">
                <div class="top-label">⬅ VOICE LEADERBOARD 💜</div>
                <div class="voice-btn">🎙 VOICE CHAT</div>
            </div>
            {cards_html}
        </div>
    </body>
    </html>
    '''
    return await render_html_to_image(html)

async def generate_streaks_image(top_streaks_data):
    cards_html = ""
    for i, p in enumerate(top_streaks_data):
        rank = i + 1
        name = p.get('name', 'Unknown')
        time = p.get('streak', '0')
        avatar = p.get('avatar_url', '') or 'https://ui-avatars.com/api/?background=random&name=' + name.replace(" ", "+")
        
        c_class = min(rank, 3)
        
        cards_html += f'''
        <div class="card card-{c_class}">
            <div class="shield-container outline-{c_class}">
                <svg class="shield-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
                </svg>
                <div class="rank-text color-{c_class}">#{rank}</div>
            </div>
            <div class="avatar-container avatar-{c_class}"><div class="avatar-img" style="background-image: url('{avatar}');"></div></div>
            <div class="player-info">
                <div class="player-name">{name} 🔥</div>
                <div class="streak-time">{time}</div>
            </div>
        </div>
        '''

    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
            body {{
                background-color: #0d0a0a;
                background-image: radial-gradient(circle at center, rgba(150, 40, 0, 0.4) 0%, transparent 60%);
                font-family: 'Inter', sans-serif; color: white; padding: 30px; width: 600px; margin: 0; box-sizing: border-box; -webkit-font-smoothing: antialiased;
            }}
            .header {{ text-align: center; font-size: 26px; font-weight: 900; color: #ff9a44; text-shadow: 0 0 15px rgba(255, 120, 0, 0.8); margin-bottom: 25px; text-transform: uppercase; }}
            .container {{ background: #18191c; border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 14px; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.6); }}
            .container-top {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }}
            .top-label {{ font-size: 14px; font-weight: 800; color: #b0b5bd; display: flex; align-items: center; gap: 8px; }}
            .voice-btn {{ background: rgba(30, 80, 40, 0.2); border: 1px solid rgba(60, 150, 60, 0.4); color: #4ade80; padding: 5px 12px; border-radius: 6px; font-size: 12px; font-weight: 800; display: flex; align-items: center; gap: 6px; text-shadow: 0 0 8px rgba(74, 222, 128, 0.4); }}
            .card {{ background: #252321; border-radius: 12px; padding: 12px 18px; margin-bottom: 12px; display: flex; align-items: center; position: relative; }}
            .card:last-child {{ margin-bottom: 0; }}
            .card-1 {{ border: 2px solid #f6a125; box-shadow: 0 0 15px rgba(246,161,37,0.4), inset 0 0 10px rgba(246,161,37,0.2); background: rgba(45, 35, 25, 0.8); }}
            .card-2 {{ border: 2px solid #57a6e5; box-shadow: 0 0 15px rgba(87,166,229,0.4), inset 0 0 10px rgba(87,166,229,0.2); background: rgba(25, 35, 45, 0.8); }}
            .card-3 {{ border: 2px solid #e55757; box-shadow: 0 0 15px rgba(229,87,87,0.4), inset 0 0 10px rgba(229,87,87,0.2); background: rgba(45, 25, 25, 0.8); }}
            .shield-container {{ width: 38px; height: 44px; position: relative; display: flex; justify-content: center; align-items: center; margin-right: 18px; flex-shrink: 0; }}
            .shield-svg {{ position: absolute; width: 100%; height: 100%; top: 0; left: 0; }}
            .rank-text {{ font-size: 14px; font-weight: 800; z-index: 2; }}
            .avatar-container {{ width: 48px; height: 48px; border-radius: 50%; position: relative; margin-right: 18px; flex-shrink: 0; }}
            .avatar-img {{ width: 100%; height: 100%; border-radius: 50%; background-size: cover; background-position: center; }}
            .avatar-1 {{ box-shadow: 0 0 12px #f6a125; border: 2px solid #f6a125; }} .avatar-2 {{ box-shadow: 0 0 12px #57a6e5; border: 2px solid #57a6e5; }} .avatar-3 {{ box-shadow: 0 0 12px #e55757; border: 2px solid #e55757; }}
            .player-info {{ flex: 1; display: flex; justify-content: space-between; align-items: center; }}
            .player-name {{ font-size: 16px; font-weight: 800; display: flex; align-items: center; gap: 6px; color: #ffffff; text-transform: uppercase; text-shadow: 0 0 8px rgba(255, 255, 255, 0.3);}}
            .streak-time {{ font-size: 16px; font-weight: 800; color: #f6a125; text-shadow: 0 0 10px rgba(246, 161, 37, 0.6); text-transform: uppercase; }}
            .color-1 {{ color: #f6a125; }} .color-2 {{ color: #57a6e5; }} .color-3 {{ color: #e55757; }}
            .outline-1 {{ color: #f6a125; filter: drop-shadow(0 0 4px rgba(246,161,37,0.8)); }} .outline-2 {{ color: #57a6e5; filter: drop-shadow(0 0 4px rgba(87,166,229,0.8)); }} .outline-3 {{ color: #e55757; filter: drop-shadow(0 0 4px rgba(229,87,87,0.8)); }}
        </style>
    </head>
    <body>
        <div class="header">🔥 ТОП СЕРІЇ В ВОЙСІ</div>
        <div class="container">
            <div class="container-top">
                <div class="top-label">⬅ TOP STREAKS 🔥</div>
                <div class="voice-btn">🎙 VOICE CHAT</div>
            </div>
            {cards_html}
        </div>
    </body>
    </html>
    '''
    return await render_html_to_image(html)

async def generate_games_image(top_games_data, offset=0, show_header=True):
    cards_html = ""
    for i, g in enumerate(top_games_data):
        rank = i + 1 + offset
        g_name = g.get('name', 'Unknown')
        g_time = g.get('time', '0 h')
        g_icon = g.get('icon_url', '') or 'https://via.placeholder.com/56x56/2a2a2a/2a2a2a'
        c_class = min(rank, 5)
        
        players_html = ""
        for pl in g.get('players', []):
            p_name = pl.get('name', '')
            p_time = pl.get('time', '')
            p_av = pl.get('avatar_url', '') or 'https://ui-avatars.com/api/?background=random&name=' + p_name.replace(" ", "+")
            
            players_html += f'''
            <div class="player-row">
                <div class="player-left"><div class="player-avatar" style="background-image: url('{p_av}');"></div><div class="player-name">{p_name}</div></div>
                <div class="player-time">{p_time}</div>
            </div>
            '''

        cards_html += f'''
        <div class="card">
            <div class="shield-container rank-{c_class}">
                <svg class="shield-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
                </svg>
                <div class="rank-text">#{rank}</div>
            </div>
            <div class="game-icon" style="background-image: url('{g_icon}');"></div>
            <div class="game-info">
                <div class="game-title-row">
                    <div class="game-name">{g_name}</div>
                    <div class="game-time">{g_time}</div>
                </div>
                {players_html}
            </div>
        </div>
        '''

    header_html = '<div class="header">ТОП ІГОР (За весь час)</div>' if show_header else ''

    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
            body {{
                background-color: #0f0a0a;
                background-image: radial-gradient(circle at 10% 50%, rgba(100, 20, 20, 0.8) 0%, transparent 50%),
                                  radial-gradient(circle at 90% 80%, rgba(150, 30, 20, 0.6) 0%, transparent 40%);
                font-family: 'Inter', sans-serif; color: white; padding: 30px; width: 580px; margin: 0; box-sizing: border-box; -webkit-font-smoothing: antialiased;
            }}
            .container {{ padding: 24px; display: flex; flex-direction: column; gap: 16px; width: 500px; box-sizing: border-box; }}
            .header {{ text-align: center; color: #ff7666; font-size: 24px; font-weight: 800; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; filter: drop-shadow(0 0 10px rgba(255, 118, 102, 0.4)); }}
            .card {{ background: linear-gradient(145deg, rgba(30, 20, 20, 0.9), rgba(15, 10, 10, 0.95)); border-radius: 16px; padding: 18px; display: flex; align-items: stretch; position: relative; overflow: hidden; box-shadow: 0 8px 32px rgba(0,0,0,0.4); border: 1px solid rgba(255, 118, 102, 0.15); }}
            .card::before {{ content: ""; position: absolute; top: 0; left: 0; right: 0; height: 1px; background: linear-gradient(90deg, transparent, rgba(255, 118, 102, 0.4), transparent); }}
            .shield-container {{ width: 44px; height: 50px; position: relative; display: flex; justify-content: center; align-items: center; margin-right: 16px; flex-shrink: 0; }}
            .shield-svg {{ position: absolute; width: 100%; height: 100%; top: 0; left: 0; }}
            .rank-text {{ font-size: 16px; font-weight: 700; z-index: 2; margin-top: -2px; }}
            .game-icon {{ width: 64px; height: 64px; border-radius: 12px; margin-right: 18px; flex-shrink: 0; background-color: #2a2a2a; border: 1px solid rgba(255,255,255,0.05); background-size: cover; background-position: center; }}
            .game-info {{ flex: 1; display: flex; flex-direction: column; justify-content: center; }}
            .game-title-row {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
            .game-name {{ font-size: 19px; font-weight: 700; color: #ff7666; text-shadow: 0 0 10px rgba(255, 118, 102, 0.8), 0 0 20px rgba(255, 118, 102, 0.4); }}
            .game-time {{ font-size: 19px; font-weight: 700; color: #f7a93b; text-shadow: 0 0 10px rgba(247, 169, 59, 0.8), 0 0 20px rgba(247, 169, 59, 0.4); }}
            .player-row {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }}
            .player-row:last-child {{ margin-bottom: 0; }}
            .player-left {{ display: flex; align-items: center; }}
            .player-avatar {{ width: 18px; height: 18px; border-radius: 50%; background: #ccc; margin-right: 8px; background-size: cover; background-position: center; }}
            .player-name {{ font-size: 15px; color: #c4cdd5; font-weight: 600; }}
            .player-time {{ font-size: 15px; color: #e5c487; font-weight: 600; text-shadow: 0 0 8px rgba(229, 196, 135, 0.7); }}
            .rank-1 {{ color: #ff6633; filter: drop-shadow(0 0 6px rgba(255,102,51,0.5)); }}
            .rank-2 {{ color: #ff5522; filter: drop-shadow(0 0 6px rgba(255,85,34,0.5)); }}
            .rank-3 {{ color: #ee4411; filter: drop-shadow(0 0 6px rgba(238,68,17,0.5)); }}
            .rank-4 {{ color: #dd3300; filter: drop-shadow(0 0 6px rgba(221,51,0,0.5)); }}
            .rank-5 {{ color: #cc2200; filter: drop-shadow(0 0 6px rgba(204,34,0,0.5)); }}
        </style>
    </head>
    <body>
        <div class="container">
            {header_html}
            {cards_html}
        </div>
    </body>
    </html>
    '''
    return await render_html_to_image(html, width=580)
