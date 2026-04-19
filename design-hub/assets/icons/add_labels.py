"""
Label sticker icons for Little Dot Book children's sticker book.
Places a frosted glass banner at the BOTTOM of each sticker (no canvas extension).
Uses Comic Sans Bold as the kid-friendly font.
"""

from PIL import Image, ImageDraw, ImageFont
import os

ICONS_DIR = "C:/Users/Admin/Projects/nexsprint/oinio/littledotbook/design-hub/assets/icons/"
OUTPUT_DIR = "C:/Users/Admin/Projects/nexsprint/oinio/littledotbook/design-hub/assets/icons/labeled/"

# The 32 icons in order (skip [2] duplicates, varients folder, labeled folder)
ICONS = [
    ("#1 Merlion.png",                  "Merlion"),
    ("#2 MBS.png",                       "MBS"),
    ("#3 Esplanade.png",                 "Esplanade"),
    ("#4 Gardens by the Bay.png",        "Gardens by the Bay"),
    ("#5 Singapore Flyer.png",           "Singapore Flyer"),
    ("#6 Changi Jewel.png",              "Changi Jewel"),
    ("#7 National Museum.png",           "National Museum"),
    ("#8 Chinatown Gate.png",            "Chinatown Gate"),
    ("#9 MRT Train.png",                 "MRT Train"),
    ("#10 SBS Bus.png",                  "SBS Bus"),
    ("#11 Bumboat.png",                  "Bumboat"),
    ("#12 Cable Car.png",                "Cable Car"),
    ("#13 Taxi.png",                     "Taxi"),
    ("#14 Chicken Rice.png",             "Chicken Rice"),
    ("#15 Laksa.png",                    "Laksa"),
    ("#16 Ice Kacang.png",               "Ice Kacang"),
    ("#17 Roti Prata.png",               "Roti Prata"),
    ("#18 Satay.png",                    "Satay"),
    ("#19 Kaya Toast + Kopi.png",        "Kaya Toast + Kopi"),
    ("#20 HDB Flat.png",                 "HDB Flat"),
    ("#21 Void Deck.png",                "Void Deck"),
    ("#22 Dragon Playground.png",        "Dragon Playground"),
    ("#23 Kopitiam.png",                 "Kopitiam"),
    ("#24 Pasar Malam.png",              "Pasar Malam"),
    ("#25 Ang Bao.png",                  "Ang Bao"),
    ("#26 Lion Dance Head.png",          "Lion Dance Head"),
    ("#27 Botanic Gardens.png",          "Botanic Gardens"),
    ("#28 Orchid.png",                   "Orchid"),
    ("#29 Otters.png",                   "Otters"),
    ("#30 Community Cat.png",            "Community Cat"),
    ("#31 Singapore Flag.png",           "Singapore Flag"),
    ("#32 National Day Fireworks.png",   "National Day Fireworks"),
]

# Category colors (index 0-based)
def get_color(icon_num):
    # icon_num is 1-based
    if 1 <= icon_num <= 8:
        return (255, 107, 107)   # Coral - Landmarks
    elif 9 <= icon_num <= 13:
        return (78, 205, 196)    # Teal - Transport
    elif 14 <= icon_num <= 19:
        return (255, 159, 67)    # Orange - Food
    elif 20 <= icon_num <= 26:
        return (162, 155, 254)   # Purple - Culture
    elif 27 <= icon_num <= 30:
        return (46, 204, 113)    # Green (darker mint) - Nature
    elif 31 <= icon_num <= 32:
        return (230, 168, 23)    # Golden yellow - National
    return (100, 100, 100)

# Font setup
FONT_PATH_COMIC_BOLD = "C:/Windows/Fonts/comicbd.ttf"
FONT_PATH_ARIAL_BOLD = "C:/Windows/Fonts/arialbd.ttf"

def get_font(size):
    for path in [FONT_PATH_COMIC_BOLD, FONT_PATH_ARIAL_BOLD]:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()

def draw_rounded_rect(draw, bbox, radius, fill):
    """Draw a rounded rectangle on the draw context."""
    x0, y0, x1, y1 = bbox
    # Draw with rounded corners using pieslice + rectangle combination
    draw.rectangle([x0 + radius, y0, x1 - radius, y1], fill=fill)
    draw.rectangle([x0, y0 + radius, x1, y1 - radius], fill=fill)
    draw.ellipse([x0, y0, x0 + radius * 2, y0 + radius * 2], fill=fill)
    draw.ellipse([x1 - radius * 2, y0, x1, y0 + radius * 2], fill=fill)
    draw.ellipse([x0, y1 - radius * 2, x0 + radius * 2, y1], fill=fill)
    draw.ellipse([x1 - radius * 2, y1 - radius * 2, x1, y1], fill=fill)

def draw_rounded_rect_border(draw, bbox, radius, color, width=2):
    """Draw just the border of a rounded rectangle."""
    x0, y0, x1, y1 = bbox
    # Straight edges
    draw.line([(x0 + radius, y0), (x1 - radius, y0)], fill=color, width=width)
    draw.line([(x0 + radius, y1), (x1 - radius, y1)], fill=color, width=width)
    draw.line([(x0, y0 + radius), (x0, y1 - radius)], fill=color, width=width)
    draw.line([(x1, y0 + radius), (x1, y1 - radius)], fill=color, width=width)
    # Corners
    draw.arc([x0, y0, x0 + radius * 2, y0 + radius * 2], 180, 270, fill=color, width=width)
    draw.arc([x1 - radius * 2, y0, x1, y0 + radius * 2], 270, 360, fill=color, width=width)
    draw.arc([x0, y1 - radius * 2, x0 + radius * 2, y1], 90, 180, fill=color, width=width)
    draw.arc([x1 - radius * 2, y1 - radius * 2, x1, y1], 0, 90, fill=color, width=width)

def add_label(img_path, label_text, icon_num, output_path):
    img = Image.open(img_path).convert("RGBA")
    w, h = img.size

    # --- Determine banner geometry ---
    # Banner height = ~16% of image height
    banner_height = int(h * 0.165)
    banner_w = int(w * 0.83)
    banner_x0 = (w - banner_w) // 2
    banner_y0 = h - banner_height - int(h * 0.04)  # small bottom margin
    banner_y1 = banner_y0 + banner_height
    banner_x1 = banner_x0 + banner_w
    radius = banner_height // 3

    # --- Find the right font size ---
    max_font_size = 48
    min_font_size = 28
    # Scale based on image size (assume baseline of 1024)
    scale = w / 1024.0
    max_font_size = int(max_font_size * scale)
    min_font_size = int(min_font_size * scale)

    # Max text width = banner width minus padding
    text_max_w = banner_w - int(w * 0.08)

    font_size = max_font_size
    font = get_font(font_size)
    while font_size > min_font_size:
        font = get_font(font_size)
        bbox = font.getbbox(label_text)
        text_w = bbox[2] - bbox[0]
        if text_w <= text_max_w:
            break
        font_size -= 2

    # --- Create overlay layer (same size as image) for the banner ---
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Draw frosted glass pill - semi-transparent white fill
    banner_fill = (255, 255, 255, 220)
    draw_rounded_rect(draw, (banner_x0, banner_y0, banner_x1, banner_y1), radius, banner_fill)

    # Soft border using the category color at 60% opacity
    cat_color = get_color(icon_num)
    border_color = (*cat_color, 160)
    draw_rounded_rect_border(draw, (banner_x0, banner_y0, banner_x1, banner_y1), radius, border_color, width=max(2, int(2 * scale)))

    # Composite banner onto image
    result = Image.alpha_composite(img, overlay)
    draw_result = ImageDraw.Draw(result)

    # --- Draw text ---
    font_color = get_color(icon_num)
    text_bbox = font.getbbox(label_text)
    text_w = text_bbox[2] - text_bbox[0]
    text_h = text_bbox[3] - text_bbox[1]
    text_x = (w - text_w) // 2 - text_bbox[0]
    text_y = banner_y0 + (banner_height - text_h) // 2 - text_bbox[1]

    # White stroke/outline for readability (draw 8 offset copies)
    stroke_range = max(2, int(2.5 * scale))
    for dx in range(-stroke_range, stroke_range + 1):
        for dy in range(-stroke_range, stroke_range + 1):
            if dx == 0 and dy == 0:
                continue
            if abs(dx) + abs(dy) <= stroke_range + 1:
                draw_result.text((text_x + dx, text_y + dy), label_text, font=font, fill=(255, 255, 255, 255))

    # Main colored text
    draw_result.text((text_x, text_y), label_text, font=font, fill=(*font_color, 255))

    result.save(output_path, "PNG")
    return w, h, font_size

# Ensure output dir exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

print(f"Processing {len(ICONS)} icons...")
print(f"Source: {ICONS_DIR}")
print(f"Output: {OUTPUT_DIR}")
print()

errors = []
for i, (filename, label) in enumerate(ICONS):
    icon_num = i + 1
    src = os.path.join(ICONS_DIR, filename)
    dst = os.path.join(OUTPUT_DIR, filename)

    if not os.path.exists(src):
        msg = f"  MISSING: {filename}"
        print(msg)
        errors.append(msg)
        continue

    try:
        w, h, fsize = add_label(src, label, icon_num, dst)
        print(f"  #{icon_num:2d} {label:<30s} [{w}x{h}] font={fsize}px -> OK")
    except Exception as e:
        msg = f"  ERROR #{icon_num} {label}: {e}"
        print(msg)
        errors.append(msg)

print()
if errors:
    print(f"DONE with {len(errors)} error(s):")
    for e in errors:
        print(e)
else:
    print(f"DONE: All {len(ICONS)} icons labeled successfully.")
