"""
generate_a4_mockup.py
Little Dot Book — Merlion Sticker Puzzle A4 Mockup Generator

Renders a print-ready A4 mockup at 150 DPI (1240x1754 px) showing
all 32 Singapore sticker icons arranged as a collage inside the
Merlion silhouette body.

Usage:
    python generate_a4_mockup.py
"""

import os
import re
import math
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ICONS_DIR  = os.path.join(SCRIPT_DIR, "icons", "labeled")
SVG_PATH   = os.path.join(SCRIPT_DIR, "merlion-silhouette.svg")
OUT_PATH   = os.path.join(SCRIPT_DIR, "merlion-puzzle-a4-mockup.png")

# ---------------------------------------------------------------------------
# Canvas — A4 @ 150 DPI
# ---------------------------------------------------------------------------
DPI        = 150
A4_W       = 1240   # 8.27 in
A4_H       = 1754   # 11.69 in
BG_COLOR   = (255, 255, 255)   # white paper

# ---------------------------------------------------------------------------
# Icon definitions — (index, filename_fragment, region_key)
# ---------------------------------------------------------------------------
ICON_DEFS = [
    (1,  "#1 Merlion.png",               "head_center"),
    (2,  "#2 MBS.png",                   "mane_top"),
    (3,  "#3 Esplanade.png",             "mane_top"),
    (4,  "#4 Gardens by the Bay.png",    "mane_top"),
    (5,  "#5 Singapore Flyer.png",       "mane_top"),
    (6,  "#6 Changi Jewel.png",          "mane_top"),
    (7,  "#7 National Museum.png",       "mane_top"),
    (8,  "#8 Chinatown Gate.png",        "mane_top"),
    (9,  "#9 MRT Train.png",             "upper_body"),
    (10, "#10 SBS Bus.png",              "upper_body"),
    (11, "#11 Bumboat.png",              "upper_body"),
    (12, "#12 Cable Car.png",            "upper_body"),
    (13, "#13 Taxi.png",                 "upper_body"),
    (14, "#14 Chicken Rice.png",         "belly"),
    (15, "#15 Laksa.png",                "belly"),
    (16, "#16 Ice Kacang.png",           "belly"),
    (17, "#17 Roti Prata.png",           "belly"),
    (18, "#18 Satay.png",                "belly"),
    (19, "#19 Kaya Toast + Kopi.png",    "belly"),
    (20, "#20 HDB Flat.png",             "lower_body"),
    (21, "#21 Void Deck.png",            "lower_body"),
    (22, "#22 Dragon Playground.png",    "lower_body"),
    (23, "#23 Kopitiam.png",             "lower_body"),
    (24, "#24 Pasar Malam.png",          "lower_body"),
    (25, "#25 Ang Bao.png",              "lower_body"),
    (26, "#26 Lion Dance Head.png",      "lower_body"),
    (27, "#27 Botanic Gardens.png",      "fish_tail"),
    (28, "#28 Orchid.png",               "fish_tail"),
    (29, "#29 Otters.png",               "fish_tail"),
    (30, "#30 Community Cat.png",        "fish_tail"),
    (31, "#31 Singapore Flag.png",       "heart"),
    (32, "#32 National Day Fireworks.png","heart"),
]

# ---------------------------------------------------------------------------
# Anatomical regions — normalized (x0,y0,x1,y1) within the RASTERIZED image
# (which covers the full 600x800 viewBox, so y=0.119 = top of silhouette)
#
# Measured from actual SVG path data:
#   Content Y: 95-705 out of 800 => y_top=0.119, y_bot=0.881
#   Mane     (y=0.00-0.15 vb): x=0.38-0.67  (narrow top spines)
#   Head     (y=0.15-0.30 vb): x=0.21-0.81  (widest point)
#   Upper    (y=0.30-0.48 vb): x=0.17-0.78
#   Belly    (y=0.48-0.63 vb): x=0.15-0.93
#   Lower    (y=0.63-0.78 vb): x=0.07-0.83
#   Tail     (y=0.78-1.00 vb): x=0.08-0.76
# ---------------------------------------------------------------------------
REGIONS = {
    # All x coords kept well inside the silhouette boundary at each Y band
    # (SVG measured: mane x=0.38-0.67, head x=0.21-0.81, upper x=0.17-0.78,
    #  belly x=0.15-0.93, lower x=0.07-0.83, tail x=0.08-0.76)
    "head_center": (0.40, 0.14, 0.62, 0.23),   # lion face center — Icon #1
    "mane_top":    (0.26, 0.12, 0.72, 0.28),   # mane + head (tight x to stay in spines)
    "upper_body":  (0.23, 0.30, 0.70, 0.44),   # chest / transport
    "heart":       (0.38, 0.32, 0.60, 0.44),   # heart badge (national)
    "belly":       (0.20, 0.46, 0.82, 0.60),   # belly / food
    "lower_body":  (0.14, 0.60, 0.76, 0.75),   # lower body / culture
    "fish_tail":   (0.16, 0.75, 0.72, 0.87),   # tail / nature
}

# Sticker size per region (px at A4 canvas size)
REGION_SIZES = {
    "head_center": 145,
    "mane_top":    100,
    "upper_body":  115,
    "heart":       118,
    "belly":       112,
    "lower_body":  112,
    "fish_tail":   115,
}

# ---------------------------------------------------------------------------
# Parse the SVG path string -> list of (x,y) float tuples
# ---------------------------------------------------------------------------
def parse_svg_path(svg_path: str) -> list:
    """Very lightweight M/L/Z SVG path parser (absolute coords only)."""
    with open(svg_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract d="..." attribute
    match = re.search(r'\bd="([^"]+)"', content)
    if not match:
        raise ValueError("No path data found in SVG")
    d = match.group(1)

    coords = []
    tokens = re.split(r'[MLZmlz,\s]+', d.strip())
    nums = []
    for t in tokens:
        t = t.strip()
        if t:
            try:
                nums.append(float(t))
            except ValueError:
                pass

    for i in range(0, len(nums) - 1, 2):
        coords.append((nums[i], nums[i + 1]))

    return coords


# ---------------------------------------------------------------------------
# Rasterise silhouette -> binary mask at given scale
# Returns: (mask_img, offset_x, offset_y, scale_factor)
# ---------------------------------------------------------------------------
def rasterize_silhouette(svg_path: str, target_width: int):
    """
    Parse the SVG path (viewBox 600x800), scale to target_width,
    rasterize as a binary PIL mask (L mode, 255=inside, 0=outside).
    Returns (mask, bbox_x, bbox_y) where bbox_x/y are the top-left
    pixel of the silhouette in the final A4 canvas.
    """
    raw_pts = parse_svg_path(svg_path)
    if not raw_pts:
        raise ValueError("Failed to parse SVG path points")

    # Original viewBox
    vb_w, vb_h = 600.0, 800.0

    scale = target_width / vb_w
    target_height = int(vb_h * scale)

    # Scale points
    pts = [(int(x * scale), int(y * scale)) for x, y in raw_pts]

    # Create mask image
    mask = Image.new("L", (target_width, target_height), 0)
    draw = ImageDraw.Draw(mask)
    draw.polygon(pts, fill=255)

    return mask, target_width, target_height


# ---------------------------------------------------------------------------
# Check if a point (px,py) is inside the mask
# ---------------------------------------------------------------------------
def point_in_mask(mask_arr: np.ndarray, px: int, py: int) -> bool:
    h, w = mask_arr.shape
    if 0 <= py < h and 0 <= px < w:
        return mask_arr[py, px] > 128
    return False


# ---------------------------------------------------------------------------
# Draw dashed rectangle border
# ---------------------------------------------------------------------------
def draw_dashed_rect(draw: ImageDraw.ImageDraw, bbox, dash=6, gap=4,
                     color=(180, 180, 180), width=2):
    x0, y0, x1, y1 = bbox
    edges = [
        ((x0, y0), (x1, y0)),  # top
        ((x1, y0), (x1, y1)),  # right
        ((x1, y1), (x0, y1)),  # bottom
        ((x0, y1), (x0, y0)),  # left
    ]
    for (sx, sy), (ex, ey) in edges:
        length = math.hypot(ex - sx, ey - sy)
        if length == 0:
            continue
        dx = (ex - sx) / length
        dy = (ey - sy) / length
        pos = 0.0
        drawing = True
        while pos < length:
            seg_len = dash if drawing else gap
            end_pos = min(pos + seg_len, length)
            if drawing:
                draw.line(
                    [
                        (sx + dx * pos,  sy + dy * pos),
                        (sx + dx * end_pos, sy + dy * end_pos),
                    ],
                    fill=color, width=width,
                )
            pos = end_pos
            drawing = not drawing


# ---------------------------------------------------------------------------
# Place icons in a region — grid with organic jitter
# ---------------------------------------------------------------------------
def scatter_icons_in_region(
    icon_imgs,      # list of (idx, PIL.Image, size)
    region_norm,    # (x0,y0,x1,y1) normalized within merlion bbox
    merl_x, merl_y, merl_w, merl_h,  # merlion position on canvas
    mask_arr,       # numpy mask array
    canvas,         # PIL canvas to paste onto
    draw,           # ImageDraw for dashed borders
    rng,            # random.Random instance
    placement_log,  # list to append log entries
):
    if not icon_imgs:
        return

    rx0 = merl_x + region_norm[0] * merl_w
    ry0 = merl_y + region_norm[1] * merl_h
    rx1 = merl_x + region_norm[2] * merl_w
    ry1 = merl_y + region_norm[3] * merl_h

    region_w = rx1 - rx0
    region_h = ry1 - ry0

    n = len(icon_imgs)
    # Build a simple grid
    cols = max(1, math.ceil(math.sqrt(n * region_w / max(region_h, 1))))
    rows = max(1, math.ceil(n / cols))

    cell_w = region_w / cols
    cell_h = region_h / rows

    placed = 0
    for i, (idx, img, sz) in enumerate(icon_imgs):
        col = i % cols
        row = i // cols

        # Cell center
        cx = rx0 + cell_w * col + cell_w * 0.5
        cy = ry0 + cell_h * row + cell_h * 0.5

        # Jitter (up to 20% of cell)
        jitter_x = rng.uniform(-cell_w * 0.20, cell_w * 0.20)
        jitter_y = rng.uniform(-cell_h * 0.20, cell_h * 0.20)
        cx += jitter_x
        cy += jitter_y

        # Clamp to region
        cx = max(rx0 + sz * 0.5, min(rx1 - sz * 0.5, cx))
        cy = max(ry0 + sz * 0.5, min(ry1 - sz * 0.5, cy))

        # Check center is inside mask; nudge aggressively toward region center
        region_cx = rx0 + region_w * 0.5
        region_cy = ry0 + region_h * 0.5
        mask_cx = int(cx) - merl_x
        mask_cy = int(cy) - merl_y
        if not point_in_mask(mask_arr, mask_cx, mask_cy):
            for attempt in range(20):
                strength = 0.30 + attempt * 0.035  # escalate pull each attempt
                cx += (region_cx - cx) * strength
                cy += (region_cy - cy) * strength
                mask_cx = int(cx) - merl_x
                mask_cy = int(cy) - merl_y
                if point_in_mask(mask_arr, mask_cx, mask_cy):
                    break
            else:
                # Fallback: snap to region center
                cx, cy = region_cx, region_cy

        # Rotation
        angle = rng.uniform(-10, 10)
        rotated = img.rotate(angle, expand=True, resample=Image.BICUBIC)
        rw, rh = rotated.size

        paste_x = int(cx - rw / 2)
        paste_y = int(cy - rh / 2)

        # Paste with alpha
        if rotated.mode == "RGBA":
            canvas.paste(rotated, (paste_x, paste_y), rotated)
        else:
            canvas.paste(rotated, (paste_x, paste_y))

        # Dashed border
        border_bbox = (paste_x, paste_y, paste_x + rw, paste_y + rh)
        draw_dashed_rect(draw, border_bbox)

        placement_log.append(f"  Icon #{idx}: placed at ({int(cx)}, {int(cy)}), size={sz}px, angle={angle:.1f}°")
        placed += 1

    return placed


# ---------------------------------------------------------------------------
# Load a font (try system fonts, fall back to default)
# ---------------------------------------------------------------------------
def load_font(size, bold=False):
    font_candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    for path in font_candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    rng = random.Random(42)   # fixed seed for reproducibility

    print("=== Merlion Sticker Puzzle A4 Mockup Generator ===\n")

    # ------------------------------------------------------------------
    # 1. Create canvas
    # ------------------------------------------------------------------
    canvas = Image.new("RGB", (A4_W, A4_H), BG_COLOR)
    draw   = ImageDraw.Draw(canvas)

    # Very subtle paper texture (warm off-white, barely perceptible)
    noise = np.random.default_rng(0).integers(0, 4, (A4_H, A4_W, 3), dtype=np.uint8)
    base = np.full((A4_H, A4_W, 3), [252, 251, 248], dtype=np.uint8)
    texture = Image.fromarray((base + noise).clip(0, 255).astype(np.uint8))
    canvas.paste(texture)
    draw = ImageDraw.Draw(canvas)

    # ------------------------------------------------------------------
    # 2. Title area
    # ------------------------------------------------------------------
    title_font    = load_font(48, bold=True)
    subtitle_font = load_font(34, bold=True)
    instruct_font = load_font(28, bold=False)
    footer_font   = load_font(22, bold=False)

    title_text    = "My Singapore Stories Vol.2"
    subtitle_text = "Merlion Sticker Puzzle"
    instruct_text = "Peel each sticker, then rebuild the Merlion!"

    def centered_text(d, text, font, y, color):
        bb = d.textbbox((0, 0), text, font=font)
        w = bb[2] - bb[0]
        d.text(((A4_W - w) // 2, y), text, fill=color, font=font)

    centered_text(draw, title_text,    title_font,    32,  (26, 54, 120))
    centered_text(draw, subtitle_text, subtitle_font, 92,  (180, 30, 45))
    centered_text(draw, instruct_text, instruct_font, 142, (90, 110, 140))

    # Decorative double rule under title
    rule_y = 185
    draw.rectangle([60, rule_y,     A4_W - 60, rule_y + 3],  fill=(26, 54, 120))
    draw.rectangle([60, rule_y + 6, A4_W - 60, rule_y + 8],  fill=(180, 30, 45))

    # ------------------------------------------------------------------
    # 3. Rasterise Merlion silhouette
    # ------------------------------------------------------------------
    MERL_TARGET_W = 980   # ~79% of A4 width for a large fill

    print("Rasterising Merlion silhouette…")
    mask_img, merl_w, merl_h = rasterize_silhouette(SVG_PATH, MERL_TARGET_W)
    mask_arr = np.array(mask_img)

    # Center horizontally, leave room for title (top ~210px) + footer (bottom ~60px)
    available_h = A4_H - 210 - 60
    # Scale down if too tall
    if merl_h > available_h:
        scale_down = available_h / merl_h
        new_w = int(merl_w * scale_down)
        new_h = int(merl_h * scale_down)
        mask_img = mask_img.resize((new_w, new_h), Image.LANCZOS)
        mask_arr = np.array(mask_img)
        merl_w, merl_h = new_w, new_h

    merl_x = (A4_W - merl_w) // 2
    merl_y = 205  # just below double rule

    print(f"  Silhouette size: {merl_w}x{merl_h}px, top-left: ({merl_x},{merl_y})")

    # ------------------------------------------------------------------
    # 4. Draw silhouette background (drop shadow + light fill + stroke)
    # ------------------------------------------------------------------
    # Parse points at scaled size (reused for fill + outline later)
    raw_pts    = parse_svg_path(SVG_PATH)
    vb_scale   = merl_w / 600.0
    scaled_pts = [(int(x * vb_scale), int(y * vb_scale)) for x, y in raw_pts]

    # Drop shadow — offset silhouette rendered in dark blur
    shadow_layer = Image.new("RGBA", (merl_w + 20, merl_h + 20), (0, 0, 0, 0))
    shadow_draw  = ImageDraw.Draw(shadow_layer)
    shadow_pts   = [(x + 10, y + 10) for x, y in scaled_pts]
    shadow_draw.polygon(shadow_pts, fill=(30, 40, 60, 80))
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=12))
    canvas.paste(shadow_layer, (merl_x - 5, merl_y - 2), shadow_layer)

    # Silhouette fill layer
    fill_layer = Image.new("RGBA", (merl_w, merl_h), (0, 0, 0, 0))
    fill_draw  = ImageDraw.Draw(fill_layer)
    fill_draw.polygon(scaled_pts, fill=(224, 235, 250, 215))
    canvas.paste(fill_layer, (merl_x, merl_y), fill_layer)

    # ------------------------------------------------------------------
    # 5. Load all icons grouped by region
    # ------------------------------------------------------------------
    print("\nLoading icons…")
    region_groups = {}   # region_key -> list of (idx, PIL.Image, size)
    missing = []

    for idx, filename, region_key in ICON_DEFS:
        fpath = os.path.join(ICONS_DIR, filename)
        if not os.path.exists(fpath):
            missing.append(filename)
            print(f"  WARNING: Not found — {filename}")
            continue

        img = Image.open(fpath).convert("RGBA")
        sz  = REGION_SIZES.get(region_key, 120)

        # Resize proportionally
        w, h = img.size
        if w > h:
            new_w = sz
            new_h = int(h * sz / w)
        else:
            new_h = sz
            new_w = int(w * sz / h)
        img = img.resize((new_w, new_h), Image.LANCZOS)

        if region_key not in region_groups:
            region_groups[region_key] = []
        region_groups[region_key].append((idx, img, sz))

    print(f"  Loaded {32 - len(missing)}/32 icons")
    if missing:
        print(f"  Missing: {missing}")

    # ------------------------------------------------------------------
    # 6. Place icons region by region
    # ------------------------------------------------------------------
    print("\nPlacing icons…")
    placement_log = []

    # Scale regions: merlion bbox is (merl_x, merl_y, merl_x+merl_w, merl_y+merl_h)
    region_order = [
        ("head_center", REGIONS["head_center"]),
        ("mane_top",    REGIONS["mane_top"]),
        ("heart",       REGIONS["heart"]),
        ("upper_body",  REGIONS["upper_body"]),
        ("belly",       REGIONS["belly"]),
        ("lower_body",  REGIONS["lower_body"]),
        ("fish_tail",   REGIONS["fish_tail"]),
    ]

    total_placed = 0
    for region_key, region_norm in region_order:
        icons = region_groups.get(region_key, [])
        if not icons:
            continue
        placement_log.append(f"\n[{region_key}] — {len(icons)} icons:")
        n = scatter_icons_in_region(
            icons, region_norm,
            merl_x, merl_y, merl_w, merl_h,
            mask_arr, canvas, draw, rng, placement_log,
        )
        total_placed += n or 0

    # ------------------------------------------------------------------
    # 7. Re-draw silhouette OUTLINE on top (so border stays crisp)
    # ------------------------------------------------------------------
    outline_layer = Image.new("RGBA", (merl_w, merl_h), (0, 0, 0, 0))
    out_draw = ImageDraw.Draw(outline_layer)
    out_draw.line(scaled_pts + [scaled_pts[0]], fill=(44, 62, 80, 240), width=5)
    canvas.paste(outline_layer, (merl_x, merl_y), outline_layer)

    # ------------------------------------------------------------------
    # 8. Footer
    # ------------------------------------------------------------------
    footer_text = "Little Dot Book  .  My Singapore Stories Vol.2"
    bbox_f = draw.textbbox((0, 0), footer_text, font=footer_font)
    fw = bbox_f[2] - bbox_f[0]
    draw.text(((A4_W - fw) // 2, A4_H - 50), footer_text, fill=(120, 140, 160), font=footer_font)

    # Footer rule
    draw.rectangle([80, A4_H - 62, A4_W - 80, A4_H - 59], fill=(200, 210, 220))

    # ------------------------------------------------------------------
    # 9. Save
    # ------------------------------------------------------------------
    print(f"\nSaving to: {OUT_PATH}")
    canvas.save(OUT_PATH, "PNG", dpi=(DPI, DPI))
    print("Saved.\n")

    # ------------------------------------------------------------------
    # 10. Summary report
    # ------------------------------------------------------------------
    print("=== Placement Summary ===")
    for line in placement_log:
        print(line)

    print(f"\nTotal icons placed: {total_placed}/32")
    print(f"Canvas: {A4_W}x{A4_H}px @ {DPI} DPI")
    print(f"Merlion silhouette: {merl_w}x{merl_h}px")
    print(f"Output: {OUT_PATH}")

    if missing:
        print(f"\nWARNING: {len(missing)} icons were missing and skipped.")

    print("\nDone.")


if __name__ == "__main__":
    main()
