"""
generate_a4_mockup_v4.py
A4 Merlion Sticker Matching Activity Page — children's book (ages 3-6)
Pure-Python (Pillow + numpy). Parses SVG path directly — no cairo/cairosvg required.

v4 changes vs v3:
- Bigger placeholders: base 120px (up from 76px), hero 150px
- Row-adaptive grid: each row uses as many columns as the body width allows
- Evenly spread across the full Merlion body (not just center)
- Staggered rows for denser packing
- Full name labels with 2-line wrap (no truncation)
- Smaller erosion (14px) to maximise usable interior
- Proper AABB overlap validation
"""

import os
import re
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR = r"C:/Users/Admin/Projects/nexsprint/oinio/littledotbook/design-hub/assets"
SVG_PATH = os.path.join(BASE_DIR, "merlion-silhouette.svg")
ICONS_DIR = os.path.join(BASE_DIR, "icons", "labeled")
OUTPUT_PATH = os.path.join(BASE_DIR, "merlion-puzzle-a4-mockup.png")

# ─── Canvas ───────────────────────────────────────────────────────────────────
A4_W, A4_H = 1240, 1754   # 150 DPI A4 portrait
BG_COLOR = (253, 251, 245)  # warm white

# SVG viewBox: 0 0 600 800
SVG_VW, SVG_VH = 600, 800

# Merlion at 1000px wide for more interior space
MERL_W_TARGET = 1000
SCALE = MERL_W_TARGET / SVG_VW        # 1.667
MERL_W = MERL_W_TARGET
MERL_H = int(SVG_VH * SCALE)          # 1333
MERL_X = (A4_W - MERL_W) // 2        # 120
MERL_Y = 160                           # room for title

ERODE_PX = 14    # safe-zone erosion

# ─── Sizing ───────────────────────────────────────────────────────────────────
BOX_SIZE_DEFAULT = 120        # base placeholder size
BOX_SIZE_HERO    = 150        # hero Merlion
BOX_RADIUS       = 12
GAP              = 16         # minimum gap between box edges
SCAN_STRIDE      = 5

# ─── Category config ─────────────────────────────────────────────────────────
CATS = {
    "Landmarks": (255, 107, 107),
    "Transport":  (78, 205, 196),
    "Food":       (255, 159, 67),
    "Culture":    (162, 155, 254),
    "Nature":     (85, 239, 196),
    "National":   (230, 168, 23),
}

# ─── Icon definitions ─────────────────────────────────────────────────────────
ICONS = [
    (1,  "Merlion",              "Landmarks"),
    (2,  "MBS",                  "Landmarks"),
    (3,  "Esplanade",            "Landmarks"),
    (4,  "Gardens by Bay",       "Landmarks"),
    (5,  "Singapore Flyer",      "Landmarks"),
    (6,  "Changi Jewel",         "Landmarks"),
    (7,  "National Museum",      "Landmarks"),
    (8,  "Chinatown Gate",       "Landmarks"),
    (9,  "MRT Train",            "Transport"),
    (10, "SBS Bus",              "Transport"),
    (11, "Bumboat",              "Transport"),
    (12, "Cable Car",            "Transport"),
    (13, "Taxi",                 "Transport"),
    (14, "Chicken Rice",         "Food"),
    (15, "Laksa",                "Food"),
    (16, "Ice Kacang",           "Food"),
    (17, "Roti Prata",           "Food"),
    (18, "Satay",                "Food"),
    (19, "Kaya Toast",           "Food"),
    (20, "HDB Flat",             "Culture"),
    (21, "Void Deck",            "Culture"),
    (22, "Dragon Playground",    "Culture"),
    (23, "Kopitiam",             "Culture"),
    (24, "Pasar Malam",          "Culture"),
    (25, "Ang Bao",              "Culture"),
    (26, "Lion Dance",           "Culture"),
    (27, "Botanic Gardens",      "Nature"),
    (28, "Orchid",               "Nature"),
    (29, "Otters",               "Nature"),
    (30, "Community Cat",        "Nature"),
    (31, "Singapore Flag",       "National"),
    (32, "Fireworks",            "National"),
]

ICON_LOOKUP = {i: (n, c) for (i, n, c) in ICONS}

FILENAME_MAP = {
    1:  "#1 Merlion.png",
    2:  "#2 MBS.png",
    3:  "#3 Esplanade.png",
    4:  "#4 Gardens by the Bay.png",
    5:  "#5 Singapore Flyer.png",
    6:  "#6 Changi Jewel.png",
    7:  "#7 National Museum.png",
    8:  "#8 Chinatown Gate.png",
    9:  "#9 MRT Train.png",
    10: "#10 SBS Bus.png",
    11: "#11 Bumboat.png",
    12: "#12 Cable Car.png",
    13: "#13 Taxi.png",
    14: "#14 Chicken Rice.png",
    15: "#15 Laksa.png",
    16: "#16 Ice Kacang.png",
    17: "#17 Roti Prata.png",
    18: "#18 Satay.png",
    19: "#19 Kaya Toast + Kopi.png",
    20: "#20 HDB Flat.png",
    21: "#21 Void Deck.png",
    22: "#22 Dragon Playground.png",
    23: "#23 Kopitiam.png",
    24: "#24 Pasar Malam.png",
    25: "#25 Ang Bao.png",
    26: "#26 Lion Dance Head.png",
    27: "#27 Botanic Gardens.png",
    28: "#28 Orchid.png",
    29: "#29 Otters.png",
    30: "#30 Community Cat.png",
    31: "#31 Singapore Flag.png",
    32: "#32 National Day Fireworks.png",
}

# ─── Region assignments (icon_id -> region) ───────────────────────────────────
# Regions define which y-band each icon lives in, for thematic grouping.
# Placement within a region uses the full available safe-mask width.
REGIONS = {
    "face":   [1],                          # hero — upper crown
    "mane":   [2, 3, 4, 5, 6, 7, 8],       # landmarks — mane area
    "chest":  [9, 10, 11, 12, 13, 31, 32],  # transport + national
    "belly":  [14, 15, 16, 17, 18, 19],     # food
    "lower":  [20, 21, 22, 23, 24, 25, 26], # culture
    "tail":   [27, 28, 29, 30],             # nature
}

# y-bands as fractions of actual body height (body starts at SVG y=95.1)
# Canvas body: y=318 to y=1318, height=1000px
# Fractions are (y - 318) / 1000
BODY_Y0 = 318    # canvas y where body starts
BODY_H  = 1000   # canvas body height

REGION_Y_ABS = {
    "face":  (BODY_Y0 + int(0.00 * BODY_H), BODY_Y0 + int(0.13 * BODY_H)),  # 318-448
    "mane":  (BODY_Y0 + int(0.10 * BODY_H), BODY_Y0 + int(0.36 * BODY_H)),  # 418-678
    "chest": (BODY_Y0 + int(0.33 * BODY_H), BODY_Y0 + int(0.56 * BODY_H)),  # 648-878
    "belly": (BODY_Y0 + int(0.52 * BODY_H), BODY_Y0 + int(0.69 * BODY_H)),  # 838-1008
    "lower": (BODY_Y0 + int(0.65 * BODY_H), BODY_Y0 + int(0.85 * BODY_H)),  # 968-1168
    "tail":  (BODY_Y0 + int(0.78 * BODY_H), BODY_Y0 + int(0.98 * BODY_H)),  # 1098-1298
}


# ─── SVG path parser ──────────────────────────────────────────────────────────

def parse_svg_path(svg_file, scale, tx, ty):
    with open(svg_file, "r") as f:
        content = f.read()
    m = re.search(r'\bd="(M[^"]+)"', content, re.DOTALL)
    if not m:
        raise ValueError("Could not find path 'd' attribute in SVG")
    d = m.group(1)
    coord_pairs = re.findall(r'[-\d.]+,[-\d.]+', d)
    points = []
    for pair in coord_pairs:
        parts = pair.split(',')
        x, y = float(parts[0]), float(parts[1])
        points.append((int(x * scale + tx), int(y * scale + ty)))
    return points


# ─── Build silhouette mask ────────────────────────────────────────────────────

def build_mask():
    print("Building silhouette mask from SVG path...")
    points = parse_svg_path(SVG_PATH, SCALE, MERL_X, MERL_Y)
    print(f"  Parsed {len(points)} polygon vertices")

    mask_img = Image.new("L", (A4_W, A4_H), 0)
    draw = ImageDraw.Draw(mask_img)
    draw.polygon(points, fill=255)
    full_mask = np.array(mask_img) > 128

    eroded = mask_img.filter(ImageFilter.MinFilter(size=ERODE_PX * 2 + 1))
    safe_mask = np.array(eroded) > 128

    print(f"  Full mask: {full_mask.sum()} px, Safe zone: {safe_mask.sum()} px")
    return full_mask, safe_mask, points


# ─── Placement helpers ────────────────────────────────────────────────────────

def box_fits(safe_mask, cx, cy, size):
    half = size // 2
    x0, y0 = cx - half, cy - half
    x1, y1 = cx + half, cy + half
    if x0 < 0 or y0 < 0 or x1 >= A4_W or y1 >= A4_H:
        return False
    return safe_mask[y0:y1, x0:x1].all()


def no_overlap(cx, cy, size, placed_boxes, gap=GAP):
    half = size // 2
    for (px, py, ps) in placed_boxes:
        p_half = ps // 2
        x_overlap = abs(cx - px) < (half + p_half + gap)
        y_overlap = abs(cy - py) < (half + p_half + gap)
        if x_overlap and y_overlap:
            return False
    return True


def scan_valid_slots(safe_mask, ry0, ry1, size, stride=SCAN_STRIDE):
    """Scan a y-band for all valid box centres."""
    slots = []
    for cy in range(ry0 + size // 2 + 2, ry1 - size // 2 - 2, stride):
        for cx in range(size // 2 + 4, A4_W - size // 2 - 4, stride):
            if box_fits(safe_mask, cx, cy, size):
                slots.append((cx, cy))
    return slots


# ─── Evenly-spread slot selection ────────────────────────────────────────────

def spread_slots_evenly(slots, n):
    """
    From valid mask slots, pick n that are maximally spatially spread.
    Uses x-bucketing to ensure horizontal coverage, then picks one per bucket.
    """
    if not slots or n == 0:
        return []
    if len(slots) <= n:
        return list(slots)

    # Sort by y, then x within each y-band
    slots_sorted = sorted(slots, key=lambda p: (p[1], p[0]))

    # Try round-robin across x buckets to get even horizontal spread per row
    xs = [p[0] for p in slots_sorted]
    x_min, x_max = min(xs), max(xs)

    if x_max == x_min:
        return slots_sorted[:n]

    # Create n x-buckets; pick centremost slot from each
    chosen = []
    bucket_w = (x_max - x_min + 1) / n

    for b in range(n):
        bx0 = x_min + b * bucket_w
        bx1 = bx0 + bucket_w
        bucket = [p for p in slots_sorted if bx0 <= p[0] < bx1]
        if bucket:
            target_x = (bx0 + bx1) / 2
            best = min(bucket, key=lambda p: abs(p[0] - target_x))
            chosen.append(best)

    # Fill any gaps from remaining (in case buckets were uneven)
    if len(chosen) < n:
        chosen_set = set(chosen)
        for p in slots_sorted:
            if p not in chosen_set:
                chosen.append(p)
                if len(chosen) >= n:
                    break

    return chosen[:n]


# ─── Region placement ─────────────────────────────────────────────────────────

def place_region(safe_mask, placed_boxes, icon_ids, region_key,
                 size=BOX_SIZE_DEFAULT):
    """
    Place icons evenly across the region's y-band.
    Uses progressively smaller sizes until all icons fit.
    """
    n = len(icon_ids)
    ry0, ry1 = REGION_Y_ABS[region_key]
    result = []
    remaining = list(icon_ids)

    size_steps = [size, size - 10, size - 20, size - 30, max(80, size - 40)]

    for attempt_size in size_steps:
        if not remaining:
            break

        raw_slots = scan_valid_slots(safe_mask, ry0, ry1, attempt_size)

        # Filter slots blocked by already-placed boxes
        free_slots = [
            (cx, cy) for (cx, cy) in raw_slots
            if no_overlap(cx, cy, attempt_size, placed_boxes)
        ]

        if len(free_slots) < len(remaining):
            continue  # not enough free slots at this size

        # Pick evenly spread slots
        chosen = spread_slots_evenly(free_slots, len(remaining))

        # Assign greedily (spread_slots_evenly doesn't check mutual overlap)
        local_placed = []
        for idx, icon_id in enumerate(list(remaining)):
            if idx >= len(chosen):
                break
            cx, cy = chosen[idx]
            if no_overlap(cx, cy, attempt_size, placed_boxes + local_placed):
                result.append((icon_id, cx, cy, attempt_size))
                placed_boxes.append((cx, cy, attempt_size))
                local_placed.append((cx, cy, attempt_size))
                remaining.remove(icon_id)

        if not remaining:
            break

    # Last-resort: scan and greedy for any remaining
    if remaining:
        for fallback_size in [max(80, size - 50), max(76, size - 60)]:
            if not remaining:
                break
            raw_slots = scan_valid_slots(safe_mask, ry0, ry1, fallback_size, stride=4)
            for icon_id in list(remaining):
                for (cx, cy) in raw_slots:
                    if no_overlap(cx, cy, fallback_size, placed_boxes):
                        result.append((icon_id, cx, cy, fallback_size))
                        placed_boxes.append((cx, cy, fallback_size))
                        remaining.remove(icon_id)
                        break

    if remaining:
        print(f"  WARNING: Could not place {remaining} in '{region_key}'")

    return result


def place_hero(safe_mask, placed_boxes):
    """Place hero icon #1 near the top-center of the body."""
    ry0, ry1 = REGION_Y_ABS["face"]
    face_cy = (ry0 + ry1) // 2
    face_cx = MERL_X + MERL_W // 2

    for s in [BOX_SIZE_HERO, BOX_SIZE_HERO - 15, BOX_SIZE_DEFAULT + 10, BOX_SIZE_DEFAULT]:
        for dy in range(-80, 120, SCAN_STRIDE):
            for dx in range(-160, 161, SCAN_STRIDE):
                cx = face_cx + dx
                cy = face_cy + dy
                if box_fits(safe_mask, cx, cy, s) and no_overlap(cx, cy, s, placed_boxes):
                    placed_boxes.append((cx, cy, s))
                    return (1, cx, cy, s)

    # Hard fallback
    slots = scan_valid_slots(safe_mask, ry0, ry1, BOX_SIZE_DEFAULT)
    if slots:
        cx, cy = slots[len(slots) // 2]
        placed_boxes.append((cx, cy, BOX_SIZE_DEFAULT))
        return (1, cx, cy, BOX_SIZE_DEFAULT)

    placed_boxes.append((face_cx, face_cy, BOX_SIZE_DEFAULT))
    return (1, face_cx, face_cy, BOX_SIZE_DEFAULT)


# ─── Sticker loading ─────────────────────────────────────────────────────────

def load_stickers():
    stickers = {}
    for icon_id, fname in FILENAME_MAP.items():
        fpath = os.path.join(ICONS_DIR, fname)
        if os.path.exists(fpath):
            try:
                stickers[icon_id] = Image.open(fpath).convert("RGBA")
            except Exception as e:
                print(f"  WARNING: {fname}: {e}")
        else:
            print(f"  WARNING: Missing: {fpath}")
    print(f"  Loaded {len(stickers)}/32 sticker images")
    return stickers


def make_ghost(img, inner_size):
    img = img.resize((inner_size, inner_size), Image.LANCZOS)
    rgb = img.convert("RGB")
    arr = np.array(rgb, dtype=np.float32)
    is_bg = (arr[:,:,0] > 228) & (arr[:,:,1] > 228) & (arr[:,:,2] > 228)
    fg_alpha = (~is_bg).astype(np.float32)
    gray = 0.299*arr[:,:,0] + 0.587*arr[:,:,1] + 0.114*arr[:,:,2]
    alpha_ch = (fg_alpha * 255 * 0.30).astype(np.uint8)
    gray_u8 = gray.astype(np.uint8)
    ghost_arr = np.stack([gray_u8, gray_u8, gray_u8, alpha_ch], axis=2)
    return Image.fromarray(ghost_arr, "RGBA")


def load_font(size, bold=False):
    candidates = (
        ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/calibrib.ttf"]
        if bold else
        ["C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/calibri.ttf",
         "C:/Windows/Fonts/segoeui.ttf"]
    )
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def text_size(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0], bb[3] - bb[1]


# ─── Draw placeholder ─────────────────────────────────────────────────────────

def wrap_label(name, draw, font, max_w):
    """Wrap name to fit max_w. Returns list of lines (1 or 2)."""
    w, _ = text_size(draw, name, font)
    if w <= max_w:
        return [name]

    words = name.split()
    if len(words) <= 1:
        return [name]

    # Try all split points, pick the one where both lines fit
    for split in range(1, len(words)):
        line1 = " ".join(words[:split])
        line2 = " ".join(words[split:])
        w1, _ = text_size(draw, line1, font)
        w2, _ = text_size(draw, line2, font)
        if w1 <= max_w and w2 <= max_w:
            return [line1, line2]

    return [name]  # last resort, overflow


def draw_placeholder(canvas, draw, icon_id, cx, cy, size, stickers,
                     font_label, font_num):
    name, cat = ICON_LOOKUP[icon_id]
    color = CATS[cat]
    half = size // 2
    x0, y0, x1, y1 = cx - half, cy - half, cx + half, cy + half

    # Tinted fill
    fill = tuple(int(c * 0.09 + 255 * 0.91) for c in color)
    draw.rounded_rectangle([x0, y0, x1, y1], radius=BOX_RADIUS, fill=fill)

    # Ghost sticker
    badge_h = 28
    label_h = 28
    inner = max(30, size - badge_h - label_h - 10)
    if icon_id in stickers:
        ghost = make_ghost(stickers[icon_id], inner)
        gx = cx - inner // 2
        gy = y0 + badge_h + 4
        canvas.paste(ghost, (gx, gy), ghost)

    # Dashed border
    border = tuple(int(c * 0.55) for c in color)
    _dashed_rounded_rect(draw, x0, y0, x1, y1, BOX_RADIUS, border,
                         dash=9, gap=6, width=2)

    # Number badge (top-left)
    br = 13
    bx = x0 + 10 + br
    by = y0 + 10 + br
    draw.ellipse([bx - br, by - br, bx + br, by + br], fill=color)
    ns = str(icon_id)
    nw, nh = text_size(draw, ns, font_num)
    draw.text((bx - nw // 2, by - nh // 2 - 1), ns, fill=(255, 255, 255), font=font_num)

    # Name label — full name, wrap if needed
    max_label_w = size - 14
    lines = wrap_label(name, draw, font_label, max_label_w)

    line_h = text_size(draw, "Ag", font_label)[1]
    line_gap = 2
    total_label_h = len(lines) * line_h + (len(lines) - 1) * line_gap

    label_top = y1 - total_label_h - 7
    max_line_w = max(text_size(draw, l, font_label)[0] for l in lines)
    lbg_x0 = cx - max_line_w // 2 - 4
    lbg_x1 = cx + max_line_w // 2 + 4
    draw.rounded_rectangle([lbg_x0, label_top - 3, lbg_x1, y1 - 4],
                            radius=4, fill=(255, 255, 255, 220))

    for i, line in enumerate(lines):
        lw, _ = text_size(draw, line, font_label)
        lx = cx - lw // 2
        ly = label_top + i * (line_h + line_gap)
        draw.text((lx, ly), line, fill=(45, 45, 65), font=font_label)


def _dashed_rounded_rect(draw, x0, y0, x1, y1, r, color, dash, gap, width=2):
    draw.rounded_rectangle([x0, y0, x1, y1], radius=r, outline=color, width=width)
    bg = BG_COLOR
    period = dash + gap
    for x in range(x0 + r, x1 - r, period):
        xe = min(x + dash + gap, x1 - r)
        xs = x + dash
        if xs < xe:
            draw.line([(xs, y0), (xe, y0)], fill=bg, width=width + 1)
            draw.line([(xs, y1), (xe, y1)], fill=bg, width=width + 1)
    for y in range(y0 + r, y1 - r, period):
        ye = min(y + dash + gap, y1 - r)
        ys = y + dash
        if ys < ye:
            draw.line([(x0, ys), (x0, ye)], fill=bg, width=width + 1)
            draw.line([(x1, ys), (x1, ye)], fill=bg, width=width + 1)


# ─── Draw silhouette ─────────────────────────────────────────────────────────

def draw_silhouette_on_canvas(canvas, points):
    draw = ImageDraw.Draw(canvas)
    draw.polygon(points, fill=(230, 238, 248))
    draw.line(points + [points[0]], fill=(30, 60, 120), width=4)


def draw_silhouette_outline_only(canvas, points):
    draw = ImageDraw.Draw(canvas)
    draw.line(points + [points[0]], fill=(30, 60, 120), width=4)


# ─── Header / footer / legend ─────────────────────────────────────────────────

def draw_header(canvas):
    draw = ImageDraw.Draw(canvas)
    f_title = load_font(52, bold=True)
    f_sub   = load_font(34)
    f_instr = load_font(25)

    title = "My Singapore Stories Vol.2"
    tw, _ = text_size(draw, title, f_title)
    draw.text(((A4_W - tw) // 2, 22), title, fill=(25, 55, 115), font=f_title)

    sub = "Merlion Sticker Activity"
    sw, _ = text_size(draw, sub, f_sub)
    draw.text(((A4_W - sw) // 2, 84), sub, fill=(215, 75, 55), font=f_sub)

    instr = "Match each numbered sticker to its box inside the Merlion!"
    iw, _ = text_size(draw, instr, f_instr)
    draw.text(((A4_W - iw) // 2, 128), instr, fill=(75, 75, 95), font=f_instr)


def draw_legend(canvas):
    draw = ImageDraw.Draw(canvas)
    f_leg  = load_font(21)
    f_head = load_font(21, bold=True)
    swatch = 18
    pad = 7
    y = A4_H - 88

    items = [(cat, text_size(draw, cat, f_leg)) for cat in CATS]
    total_w = sum(swatch + pad + w + 26 for (cat, (w, h)) in items)

    head = "Category Key:"
    hw, _ = text_size(draw, head, f_head)
    x = (A4_W - total_w - hw - 16) // 2
    draw.text((x, y + 2), head, fill=(75, 75, 95), font=f_head)
    x += hw + 16

    for cat, (w, h) in items:
        color = CATS[cat]
        draw.rectangle([x, y + 3, x + swatch, y + swatch + 3], fill=color)
        draw.text((x + swatch + pad, y), cat, fill=(55, 55, 75), font=f_leg)
        x += swatch + pad + w + 26


def draw_footer(canvas):
    draw = ImageDraw.Draw(canvas)
    f = load_font(19)
    text = "Little Dot Book  .  My Singapore Stories Vol.2"
    tw, _ = text_size(draw, text, f)
    draw.text(((A4_W - tw) // 2, A4_H - 38), text, fill=(155, 155, 175), font=f)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Merlion A4 Activity Page Generator v4")
    print("=" * 60)
    print(f"  Merlion: {MERL_W}x{MERL_H}px at ({MERL_X},{MERL_Y})")
    print(f"  Box sizes: default={BOX_SIZE_DEFAULT}px, hero={BOX_SIZE_HERO}px, gap={GAP}px")
    print(f"  Region y-bands (abs canvas coords):")
    for rn, (ry0, ry1) in REGION_Y_ABS.items():
        print(f"    {rn:8s}: y={ry0}-{ry1} (h={ry1-ry0})")

    # 1. Build mask
    full_mask, safe_mask, points = build_mask()

    # 2. Load stickers
    stickers = load_stickers()

    # 3. Place all icons
    print("\nPlacing placeholders...")
    placed_boxes = []
    all_placed = []

    hero = place_hero(safe_mask, placed_boxes)
    all_placed.append(hero)
    print(f"  Hero #1: ({hero[1]}, {hero[2]}) size={hero[3]}")

    region_order = ["mane", "chest", "belly", "lower", "tail"]
    region_needs = {
        "mane":  (REGIONS["mane"],  7),
        "chest": (REGIONS["chest"], 7),
        "belly": (REGIONS["belly"], 6),
        "lower": (REGIONS["lower"], 7),
        "tail":  (REGIONS["tail"],  4),
    }

    for r in region_order:
        icons, expected = region_needs[r]
        group = place_region(safe_mask, placed_boxes, icons, r, BOX_SIZE_DEFAULT)
        all_placed.extend(group)
        placed_count = len(group)
        if placed_count < expected:
            missing_ids = [iid for iid in icons if iid not in {p[0] for p in group}]
            print(f"  WARNING: {r} short by {expected - placed_count}: missing {missing_ids}")
        else:
            sizes = sorted(set(sz for (_, _, _, sz) in group))
            print(f"  {r.capitalize():8s}: {placed_count}/{expected} placed, sizes={sizes}")

    total_placed = len(all_placed)
    placed_ids = {p[0] for p in all_placed}
    missing = [i for i in range(1, 33) if i not in placed_ids]
    print(f"\n  Total: {total_placed}/32 placed")

    # 4. Render
    print("\nRendering canvas...")
    canvas = Image.new("RGB", (A4_W, A4_H), BG_COLOR)

    draw_header(canvas)
    draw_silhouette_on_canvas(canvas, points)

    draw = ImageDraw.Draw(canvas, "RGBA")
    f_label = load_font(11)
    f_num   = load_font(14, bold=True)

    for (icon_id, cx, cy, size) in all_placed:
        draw_placeholder(canvas, draw, icon_id, cx, cy, size, stickers,
                         f_label, f_num)

    draw_silhouette_outline_only(canvas, points)
    draw_legend(canvas)
    draw_footer(canvas)

    # 5. Save
    canvas.save(OUTPUT_PATH, "PNG", dpi=(150, 150))
    print(f"\nSaved: {OUTPUT_PATH}")

    # 6. Stats
    safe_area = safe_mask.sum()
    fill_area = sum(s * s for (_, _, _, s) in all_placed)
    fill_pct = fill_area / safe_area * 100 if safe_area > 0 else 0
    all_sizes = [s for (_, _, _, s) in all_placed]
    downsized = [(iid, sz) for (iid, _, _, sz) in all_placed if sz < BOX_SIZE_DEFAULT]

    print("\n" + "=" * 60)
    print(f"DONE: {total_placed}/32 placeholders placed")
    if all_sizes:
        print(f"  Sizes used: min={min(all_sizes)}, max={max(all_sizes)}, "
              f"target={BOX_SIZE_DEFAULT}")
    print(f"  Safe zone area: {safe_area} px^2")
    print(f"  Placeholder coverage: {fill_area} px^2 = {fill_pct:.1f}% of safe zone")
    print(f"FILES: {OUTPUT_PATH}")
    if downsized:
        print(f"  Downsized boxes: {downsized}")
    else:
        print("  Downsized: none")
    if missing:
        print(f"ISSUES: Could not place icons {missing}")
    else:
        print("ISSUES: None")
    print("=" * 60)

    return total_placed, missing, fill_pct


if __name__ == "__main__":
    main()
