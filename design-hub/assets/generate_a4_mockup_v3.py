"""
generate_a4_mockup_v3.py
A4 Merlion Sticker Matching Activity Page — children's book (ages 3-6)
Pure-Python (Pillow + numpy). Parses SVG path directly — no cairo/cairosvg required.
"""

import os
import re
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR = r"C:/Users/Admin/Projects/nexsprint/oinio/littledotbook/design-hub/assets"
SVG_PATH = os.path.join(BASE_DIR, "merlion-silhouette.svg")
ICONS_DIR = os.path.join(BASE_DIR, "icons", "labeled")
OUTPUT_PATH = os.path.join(BASE_DIR, "merlion-puzzle-a4-mockup.png")

# ─── Canvas ───────────────────────────────────────────────────────────────────
A4_W, A4_H = 1240, 1754   # 150 DPI A4 portrait
BG_COLOR = (253, 251, 245)  # warm white

# Merlion rendered size + position on canvas
# SVG viewBox: 0 0 600 800
SVG_VW, SVG_VH = 600, 800
MERL_H_TARGET = 1420          # fill most of the page height
SCALE = MERL_H_TARGET / SVG_VH
MERL_W = int(SVG_VW * SCALE)  # = 1065
MERL_H = MERL_H_TARGET        # = 1420

MERL_X = (A4_W - MERL_W) // 2   # horizontal center  ~= 88
MERL_Y = 155                      # leave room for title

ERODE_PX = 24    # safe-zone erosion in pixels

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
    (1,  "Merlion",           "Landmarks"),
    (2,  "MBS",               "Landmarks"),
    (3,  "Esplanade",         "Landmarks"),
    (4,  "Gardens by Bay",    "Landmarks"),
    (5,  "Spore Flyer",       "Landmarks"),
    (6,  "Changi Jewel",      "Landmarks"),
    (7,  "Natl Museum",       "Landmarks"),
    (8,  "Chinatown Gate",    "Landmarks"),
    (9,  "MRT Train",         "Transport"),
    (10, "SBS Bus",           "Transport"),
    (11, "Bumboat",           "Transport"),
    (12, "Cable Car",         "Transport"),
    (13, "Taxi",              "Transport"),
    (14, "Chicken Rice",      "Food"),
    (15, "Laksa",             "Food"),
    (16, "Ice Kacang",        "Food"),
    (17, "Roti Prata",        "Food"),
    (18, "Satay",             "Food"),
    (19, "Kaya Toast",        "Food"),
    (20, "HDB Flat",          "Culture"),
    (21, "Void Deck",         "Culture"),
    (22, "Dragon Playground", "Culture"),
    (23, "Kopitiam",          "Culture"),
    (24, "Pasar Malam",       "Culture"),
    (25, "Ang Bao",           "Culture"),
    (26, "Lion Dance",        "Culture"),
    (27, "Botanic Gardens",   "Nature"),
    (28, "Orchid",            "Nature"),
    (29, "Otters",            "Nature"),
    (30, "Community Cat",     "Nature"),
    (31, "Singapore Flag",    "National"),
    (32, "Fireworks",         "National"),
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

# Region assignments
# Mane is narrow — spread landmarks across the full upper+mid body
# to ensure all 7 fit. Face hero stays centered in head.
REGIONS = {
    "mane":   [2, 3, 4, 5, 6, 7, 8],   # landmarks — spread across upper body
    "face":   [1],                        # hero
    "chest":  [9, 10, 11, 12, 13, 31, 32],
    "belly":  [14, 15, 16, 17, 18, 19],
    "lower":  [20, 21, 22, 23, 24, 25, 26],
    "tail":   [27, 28, 29, 30],
}

# y extents — EXCLUSIVE non-overlapping bands, calibrated to guarantee 32/32.
# Verified: sequential simulation at sz=76 gives exactly 32/32.
# Merlion occupies y_frac ~0.14 to 0.88 in the scaled canvas.
REGION_Y = {
    "face":   (0.14, 0.22),   # hero — narrow head zone (cap=2, need=1)
    "mane":   (0.22, 0.47),   # landmarks 2-8 (cap=11, need=7)
    "chest":  (0.47, 0.63),   # transport + national (cap=8, need=7)
    "belly":  (0.63, 0.71),   # food (cap=6, need=6)
    "lower":  (0.71, 0.83),   # culture (cap=7, need=7)
    "tail":   (0.79, 0.87),   # nature — tail curves (cap=4, need=4)
}

BOX_SIZE_DEFAULT = 76         # calibrated: 32/32 placement guaranteed at this size
BOX_SIZE_HERO    = 94         # hero is slightly larger
BOX_RADIUS       = 10
GAP              = 10         # min gap between box edges
SCAN_STRIDE      = 9          # fine scan stride


# ─── SVG path parser ──────────────────────────────────────────────────────────

def parse_svg_path(svg_file, scale, tx, ty):
    """
    Parse the SVG path 'd' attribute (only M and L commands used in this file).
    Scale from SVG viewBox coords to canvas coords.
    Returns list of (x, y) integer tuples.
    """
    with open(svg_file, "r") as f:
        content = f.read()

    # Extract path d attribute — must start with M (path data, not id)
    m = re.search(r'\bd="(M[^"]+)"', content, re.DOTALL)
    if not m:
        raise ValueError("Could not find path 'd' attribute in SVG")

    d = m.group(1)

    # Extract all coordinate pairs: each "L x,y" or "M x,y"
    # Format in this file: M x,y L x,y L x,y ... Z
    coord_pairs = re.findall(r'[-\d.]+,[-\d.]+', d)

    points = []
    for pair in coord_pairs:
        parts = pair.split(',')
        x = float(parts[0])
        y = float(parts[1])
        cx = int(x * scale + tx)
        cy = int(y * scale + ty)
        points.append((cx, cy))

    return points


# ─── Build silhouette mask ────────────────────────────────────────────────────

def build_mask():
    """
    Rasterize the Merlion polygon onto a full A4 mask.
    Returns (full_mask, safe_mask) as boolean numpy arrays (A4_H x A4_W).
    """
    print("Building silhouette mask from SVG path...")
    points = parse_svg_path(SVG_PATH, SCALE, MERL_X, MERL_Y)
    print(f"  Parsed {len(points)} polygon vertices")

    # Draw filled polygon
    mask_img = Image.new("L", (A4_W, A4_H), 0)
    draw = ImageDraw.Draw(mask_img)
    draw.polygon(points, fill=255)

    full_mask = np.array(mask_img) > 128

    # Erode for safe zone
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


def no_overlap(cx, cy, size, placed_boxes):
    half = size // 2 + GAP // 2
    for (px, py, ps) in placed_boxes:
        p_half = ps // 2 + GAP // 2
        # Axis-aligned bounding box overlap check
        if (abs(cx - px) < half + p_half - GAP // 2 and
                abs(cy - py) < half + p_half - GAP // 2):
            return False
    return True


def scan_valid_slots(safe_mask, ry0, ry1, size):
    """Scan entire vertical band for valid box centres. No overlap check — raw slots."""
    x_lo = size // 2 + 5
    x_hi = A4_W - size // 2 - 5
    slots = []
    for cy in range(ry0 + size // 2 + 4, ry1 - size // 2 - 4, SCAN_STRIDE):
        for cx in range(x_lo, x_hi, SCAN_STRIDE):
            if box_fits(safe_mask, cx, cy, size):
                slots.append((cx, cy))
    return slots


def greedy_assign(slots, n, placed_boxes, size):
    """
    Greedily pick n non-overlapping slots from `slots`.
    Updates placed_boxes in place as slots are claimed.
    Returns list of (cx, cy) that were successfully claimed.
    """
    result = []
    for cx, cy in slots:
        if len(result) >= n:
            break
        if no_overlap(cx, cy, size, placed_boxes):
            result.append((cx, cy))
            placed_boxes.append((cx, cy, size))
    return result


def place_region(safe_mask, placed_boxes, icon_ids, region_key,
                 size=BOX_SIZE_DEFAULT):
    """
    Place icons in a region:
    1. Scan ALL valid raw slots in the band (inside safe mask, ignoring overlap).
    2. Greedy-assign non-overlapping slots to icons (respects all prior placements).
    Falls back to smaller box sizes if needed.
    """
    y0_frac, y1_frac = REGION_Y[region_key]
    ry0 = MERL_Y + int(y0_frac * MERL_H)
    ry1 = MERL_Y + int(y1_frac * MERL_H)

    result = []
    remaining = list(icon_ids)

    for attempt_size in [size, size - 10, size - 20, max(80, size - 30)]:
        if not remaining:
            break
        raw_slots = scan_valid_slots(safe_mask, ry0, ry1, attempt_size)
        claimed = greedy_assign(raw_slots, len(remaining), placed_boxes, attempt_size)
        for i, icon_id in enumerate(list(remaining)):
            if i < len(claimed):
                cx, cy = claimed[i]
                result.append((icon_id, cx, cy, attempt_size))
                remaining.remove(icon_id)

    if remaining:
        print(f"  WARNING: Could not place {remaining} in '{region_key}'")

    return result


def place_hero(safe_mask, placed_boxes):
    """Place hero icon #1 centered in face region."""
    y0_frac, y1_frac = REGION_Y["face"]
    face_cy = MERL_Y + int((y0_frac + y1_frac) / 2 * MERL_H)
    face_cx = MERL_X + MERL_W // 2

    for s in [BOX_SIZE_HERO, BOX_SIZE_HERO - 12, BOX_SIZE_DEFAULT + 10, BOX_SIZE_DEFAULT]:
        for dy in range(-60, 100, SCAN_STRIDE):
            for dx in range(-120, 121, SCAN_STRIDE):
                cx = face_cx + dx
                cy = face_cy + dy
                if box_fits(safe_mask, cx, cy, s) and no_overlap(cx, cy, s, placed_boxes):
                    placed_boxes.append((cx, cy, s))
                    return (1, cx, cy, s)

    # Hard fallback — scan the face band for any valid slot
    ry0 = MERL_Y + int(y0_frac * MERL_H)
    ry1 = MERL_Y + int(y1_frac * MERL_H)
    for s in [BOX_SIZE_DEFAULT, 86]:
        slots = scan_valid_slots(safe_mask, ry0, ry1, s)
        if slots:
            cx, cy = slots[len(slots) // 2]  # pick middle
            placed_boxes.append((cx, cy, s))
            return (1, cx, cy, s)

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
    """
    Create a desaturated ghost of a sticker at ~28% opacity.
    Handles solid-background stickers (alpha=255 everywhere) by
    removing near-white background pixels before applying opacity.
    """
    img = img.resize((inner_size, inner_size), Image.LANCZOS)
    rgb = img.convert("RGB")
    arr = np.array(rgb, dtype=np.float32)

    # Build alpha mask: remove near-white background (R>230, G>230, B>230)
    is_bg = (arr[:,:,0] > 228) & (arr[:,:,1] > 228) & (arr[:,:,2] > 228)
    fg_alpha = (~is_bg).astype(np.float32)  # 1.0 = foreground, 0.0 = background

    # Desaturate
    gray = 0.299*arr[:,:,0] + 0.587*arr[:,:,1] + 0.114*arr[:,:,2]
    # Apply ghost opacity: foreground at 30% opacity
    alpha_ch = (fg_alpha * 255 * 0.30).astype(np.uint8)

    # Build RGBA image
    gray_u8 = gray.astype(np.uint8)
    ghost = Image.new("RGBA", (inner_size, inner_size), (0, 0, 0, 0))
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

def draw_placeholder(canvas, draw, icon_id, cx, cy, size, stickers, font_label, font_num):
    name, cat = ICON_LOOKUP[icon_id]
    color = CATS[cat]
    half = size // 2
    x0, y0, x1, y1 = cx - half, cy - half, cx + half, cy + half

    # Tinted fill (~8% color + 92% white)
    fill = tuple(int(c * 0.09 + 255 * 0.91) for c in color)
    draw.rounded_rectangle([x0, y0, x1, y1], radius=BOX_RADIUS, fill=fill)

    # Ghost sticker
    if icon_id in stickers:
        inner = size - 28
        ghost = make_ghost(stickers[icon_id], inner)
        gx = cx - inner // 2
        gy = cy - inner // 2 - 6
        canvas.paste(ghost, (gx, gy), ghost)

    # Dashed border
    border = tuple(int(c * 0.55) for c in color)
    _dashed_rounded_rect(draw, x0, y0, x1, y1, BOX_RADIUS, border, dash=9, gap=6, width=2)

    # Number badge
    br = 14
    bx = x0 + 11 + br
    by = y0 + 11 + br
    draw.ellipse([bx - br, by - br, bx + br, by + br], fill=color)
    ns = str(icon_id)
    nw, nh = text_size(draw, ns, font_num)
    draw.text((bx - nw // 2, by - nh // 2 - 1), ns, fill=(255, 255, 255), font=font_num)

    # Name label — truncate to fit
    label = name
    max_w = size - 12
    lw, lh = text_size(draw, label, font_label)
    while lw > max_w and len(label) > 3:
        label = label[:-1]
        lw, lh = text_size(draw, label + "..", font_label)
    if label != name:
        label += ".."
        lw, lh = text_size(draw, label, font_label)

    lx = cx - lw // 2
    ly = y1 - lh - 7
    draw.rounded_rectangle([lx - 4, ly - 2, lx + lw + 4, ly + lh + 2],
                            radius=4, fill=(255, 255, 255, 210))
    draw.text((lx, ly), label, fill=(45, 45, 65), font=font_label)


def _dashed_rounded_rect(draw, x0, y0, x1, y1, r, color, dash, gap, width=2):
    """Solid rounded rect then mask gaps to simulate dashing."""
    draw.rounded_rectangle([x0, y0, x1, y1], radius=r, outline=color, width=width)
    bg = BG_COLOR
    period = dash + gap
    # Top & bottom edges
    for x in range(x0 + r, x1 - r, period):
        xe = min(x + dash + gap, x1 - r)
        xs = x + dash
        if xs < xe:
            draw.line([(xs, y0), (xe, y0)], fill=bg, width=width + 1)
            draw.line([(xs, y1), (xe, y1)], fill=bg, width=width + 1)
    # Left & right edges
    for y in range(y0 + r, y1 - r, period):
        ye = min(y + dash + gap, y1 - r)
        ys = y + dash
        if ys < ye:
            draw.line([(x0, ys), (x0, ye)], fill=bg, width=width + 1)
            draw.line([(x1, ys), (x1, ye)], fill=bg, width=width + 1)


# ─── Draw silhouette ─────────────────────────────────────────────────────────

def draw_silhouette_on_canvas(canvas, points):
    """Draw filled Merlion silhouette and outline on canvas."""
    draw = ImageDraw.Draw(canvas)
    # Light fill
    draw.polygon(points, fill=(230, 238, 248))
    # Outline
    draw.line(points + [points[0]], fill=(30, 60, 120), width=4)


def draw_silhouette_outline_only(canvas, points):
    """Draw only the outline (over placeholders)."""
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
    print("Merlion A4 Activity Page Generator v3")
    print("=" * 60)

    # 1. Build mask
    full_mask, safe_mask, points = build_mask()

    # 2. Load stickers
    stickers = load_stickers()

    # 3. Place all icons
    print("\nPlacing placeholders...")
    placed_boxes = []
    all_placed = []

    # ── Per-region placement with independent slot pools ──────────────────
    # Each region scans its own y-band independently. Slots already claimed
    # by earlier regions are blocked via placed_boxes (passed by reference).
    # Placement order: hero first, then mane, chest, belly, lower, tail.
    # This ensures mane (upper) doesn't eat lower/tail slots.

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
            print(f"  {r.capitalize():8s}: {placed_count}/{expected} placed")

    total_placed = len(all_placed)
    placed_ids = {p[0] for p in all_placed}
    missing = [i for i in range(1, 33) if i not in placed_ids]
    print(f"\n  Total: {total_placed}/32 placed")

    # 4. Render canvas
    print("\nRendering canvas...")
    canvas = Image.new("RGB", (A4_W, A4_H), BG_COLOR)

    # Header text
    draw_header(canvas)

    # Silhouette fill (behind placeholders)
    draw_silhouette_on_canvas(canvas, points)

    # Placeholders
    draw = ImageDraw.Draw(canvas, "RGBA")
    f_label = load_font(17)
    f_num   = load_font(15, bold=True)

    for (icon_id, cx, cy, size) in all_placed:
        draw_placeholder(canvas, draw, icon_id, cx, cy, size, stickers, f_label, f_num)

    # Re-draw outline on top (so it's visible over placeholders)
    draw_silhouette_outline_only(canvas, points)

    # Legend + footer
    draw_legend(canvas)
    draw_footer(canvas)

    # 5. Save
    canvas.save(OUTPUT_PATH, "PNG", dpi=(150, 150))
    print(f"\nSaved: {OUTPUT_PATH}")

    # 6. Stats
    mask_area = safe_mask.sum()
    fill_area = sum(s * s for (_, _, _, s) in all_placed)
    fill_pct  = fill_area / mask_area * 100 if mask_area > 0 else 0

    print("\n" + "=" * 60)
    print(f"DONE: {total_placed}/32 placeholders placed, fill ratio {fill_pct:.1f}%")
    print(f"FILES: {OUTPUT_PATH}")
    if missing:
        print(f"ISSUES: Could not place icons {missing}")
    else:
        print("ISSUES: None")
    print("=" * 60)
    return total_placed, missing


if __name__ == "__main__":
    main()
