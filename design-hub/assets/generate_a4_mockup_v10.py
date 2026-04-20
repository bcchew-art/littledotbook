"""
generate_a4_mockup_v10.py
Merlion Puzzle A4 — v10: Auto-crop 32 stickers, pack inside Merlion silhouette.

No tessellation. Each sticker is auto-cropped from its white/near-white background,
given a transparent background, then packed inside the Merlion silhouette using a
greedy area-maximising placement algorithm. Gabriel will draw puzzle cut lines in
Illustrator later.

Steps:
  1. Auto-crop all 32 stickers (corner-sample background, Euclidean distance mask).
  2. Save cropped PNGs to icons/cropped/ with transparency.
  3. Parse Merlion silhouette SVG -> shapely Polygon at canvas coords.
  4. Pack stickers inside silhouette: greedy placement, largest-first, with retry
     on scale-down if not all 32 fit.
  5. Render A4 page with page chrome (title, subtitle, footer) and silhouette outline.
  6. Save PNG.
"""

import os
import re
import math
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

try:
    from shapely.geometry import Polygon, Point, box as shapely_box
    from shapely.ops import unary_union
    SHAPELY = True
except ImportError:
    SHAPELY = False
    print("WARNING: shapely not installed — using bbox-only containment check")

# ─── Paths ────────────────────────────────────────────────────────────────────

BASE_DIR    = Path(r"C:/Users/Admin/Projects/nexsprint/oinio/littledotbook/design-hub/assets")
SVG_PATH    = BASE_DIR / "merlion-silhouette.svg"
ICONS_DIR   = BASE_DIR / "icons"
CROPPED_DIR = BASE_DIR / "icons" / "cropped"
OUTPUT_PATH = BASE_DIR / "merlion-puzzle-a4-v10.png"

# ─── Canvas ───────────────────────────────────────────────────────────────────

A4_W, A4_H   = 1240, 1754        # 150 DPI A4 portrait
BG_COLOR     = (250, 247, 240)   # cream #FAF7F0
HEADER_H     = 100               # top margin for title/subtitle
FOOTER_H     = 80                # bottom margin for footer
MERL_W_TARGET = 1100             # silhouette width in canvas pixels
SVG_VW, SVG_VH = 600, 800       # SVG viewBox

# ─── Crop parameters ─────────────────────────────────────────────────────────

CORNER_PATCH   = 10     # px — sample square at each corner
BG_THRESHOLD   = 30     # Euclidean RGB distance to consider pixel as foreground
CROP_PADDING   = 8      # px — padding around tight foreground bbox

# ─── Pack parameters ─────────────────────────────────────────────────────────

TARGET_COVERAGE  = 0.85   # 85% of silhouette area
N_STICKERS       = 32
BOUNDARY_MARGIN  = 8      # px — minimum distance from silhouette boundary (loose — stickers have transparent padding)
GRID_STEP        = 8      # px — candidate grid spacing (finer = better packing)
MAX_RETRIES      = 8      # scale-down retries if not all 32 fit
SCALE_DOWN_STEP  = 0.07   # 7% shrink per retry (finer steps)

# ─── Colours ─────────────────────────────────────────────────────────────────

SIL_OUTLINE_COLOR = (207, 203, 192)    # #CFCBC0 light grey
BADGE_BG          = (255, 255, 255)
BADGE_TEXT        = (40, 40, 50)
TITLE_COLOR       = (45, 45, 55)
SUBTITLE_COLOR    = (110, 110, 120)
FOOTER_COLOR      = (160, 160, 170)

# ─── Sticker filename map ─────────────────────────────────────────────────────

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


# ─── Fonts ───────────────────────────────────────────────────────────────────

def load_font(size, bold=False):
    candidates = (
        ["C:/Windows/Fonts/georgiab.ttf", "C:/Windows/Fonts/arialbd.ttf",
         "C:/Windows/Fonts/calibrib.ttf"]
        if bold else
        ["C:/Windows/Fonts/georgia.ttf", "C:/Windows/Fonts/arial.ttf",
         "C:/Windows/Fonts/calibri.ttf", "C:/Windows/Fonts/segoeui.ttf"]
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


# ─── STEP 1: Auto-crop stickers ───────────────────────────────────────────────

def sample_background_color(img_rgb: np.ndarray, patch: int = CORNER_PATCH):
    """Sample 4 corner patches and return median color as background estimate."""
    h, w = img_rgb.shape[:2]
    p = min(patch, h // 4, w // 4)
    corners = [
        img_rgb[:p, :p].reshape(-1, 3),
        img_rgb[:p, w-p:].reshape(-1, 3),
        img_rgb[h-p:, :p].reshape(-1, 3),
        img_rgb[h-p:, w-p:].reshape(-1, 3),
    ]
    samples = np.concatenate(corners, axis=0)
    median = np.median(samples, axis=0)
    return median  # float [R, G, B]


def build_fg_mask(img_rgb: np.ndarray, bg_color: np.ndarray, threshold: float = BG_THRESHOLD):
    """True where pixel is foreground (color distance > threshold)."""
    diff = img_rgb.astype(np.float32) - bg_color.astype(np.float32)
    dist = np.sqrt(np.sum(diff ** 2, axis=2))
    return dist > threshold


def auto_crop_sticker(src_path: Path, dst_path: Path, sticker_id: int):
    """
    Open PNG, sample background, build foreground mask, find tight bbox,
    add padding, crop, make background transparent, save.
    Returns (orig_size, crop_size, content_pct) or None on failure.
    """
    img = Image.open(src_path).convert("RGBA")
    orig_w, orig_h = img.size

    img_rgb = np.array(img.convert("RGB"))
    bg_color = sample_background_color(img_rgb)
    fg_mask = build_fg_mask(img_rgb, bg_color)

    rows = np.any(fg_mask, axis=1)
    cols = np.any(fg_mask, axis=0)

    if not np.any(rows):
        print(f"  WARN #{sticker_id}: no foreground found — using full image")
        fg_box = (0, 0, orig_w - 1, orig_h - 1)
    else:
        r_min, r_max = np.where(rows)[0][[0, -1]]
        c_min, c_max = np.where(cols)[0][[0, -1]]
        fg_box = (c_min, r_min, c_max, r_max)

    # Add padding, clamp to image bounds
    x0 = max(0, fg_box[0] - CROP_PADDING)
    y0 = max(0, fg_box[1] - CROP_PADDING)
    x1 = min(orig_w - 1, fg_box[2] + CROP_PADDING)
    y1 = min(orig_h - 1, fg_box[3] + CROP_PADDING)

    crop_w = x1 - x0 + 1
    crop_h = y1 - y0 + 1

    # Crop the RGBA image
    cropped_rgba = np.array(img)[y0:y1+1, x0:x1+1].copy()
    cropped_fg   = fg_mask[y0:y1+1, x0:x1+1]

    # Make background transparent: set alpha=0 where not foreground
    cropped_rgba[~cropped_fg, 3] = 0

    # Also zero out near-background pixels that bled through (alpha channel)
    # If original image already had partial alpha from the source, respect it
    orig_alpha = np.array(img)[y0:y1+1, x0:x1+1, 3]
    # Combine: pixel is visible only if BOTH fg_mask AND orig_alpha>10
    combined_fg = cropped_fg & (orig_alpha > 10)
    cropped_rgba[~combined_fg, 3] = 0

    out_img = Image.fromarray(cropped_rgba, "RGBA")
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    out_img.save(str(dst_path))

    content_pct = (crop_w * crop_h) / (orig_w * orig_h) * 100
    return (orig_w, orig_h), (crop_w, crop_h), content_pct


def step1_crop_all_stickers():
    """Crop all 32 stickers and save to CROPPED_DIR. Returns dict {id: (crop_w, crop_h)}."""
    print("\n[STEP 1] Auto-cropping 32 stickers...")
    CROPPED_DIR.mkdir(parents=True, exist_ok=True)

    crop_sizes = {}
    failed = []

    for sid in range(1, N_STICKERS + 1):
        fname = FILENAME_MAP.get(sid)
        if not fname:
            print(f"  WARN: no filename for sticker {sid}")
            failed.append(sid)
            continue
        src = ICONS_DIR / fname
        if not src.exists():
            print(f"  WARN: missing file {src}")
            failed.append(sid)
            continue
        dst = CROPPED_DIR / fname

        try:
            orig_sz, crop_sz, pct = auto_crop_sticker(src, dst, sid)
            crop_sizes[sid] = crop_sz
            print(f"  #{sid:2d}: orig {orig_sz[0]}x{orig_sz[1]}, "
                  f"cropped {crop_sz[0]}x{crop_sz[1]}, content {pct:.1f}%")
        except Exception as e:
            print(f"  ERROR #{sid}: {e}")
            failed.append(sid)

    print(f"  Cropped {len(crop_sizes)}/32 stickers. "
          f"{'All OK' if not failed else 'Failed: ' + str(failed)}")
    return crop_sizes


# ─── STEP 2: Parse SVG silhouette ────────────────────────────────────────────

def parse_svg_polygon(svg_file: Path):
    """Parse SVG path 'd' attribute -> list of (x, y) float points."""
    content = svg_file.read_text(encoding="utf-8")
    m = re.search(r'\bd="(M[^"]+)"', content, re.DOTALL)
    if not m:
        # Try polygon points attribute
        m2 = re.search(r'points="([^"]+)"', content)
        if m2:
            raw = m2.group(1).strip()
            pairs = re.findall(r'([-\d.]+)[,\s]+([-\d.]+)', raw)
            return [(float(x), float(y)) for x, y in pairs]
        raise ValueError("No SVG path 'd' or polygon 'points' found in SVG")
    d = m.group(1)
    # Extract coordinate pairs
    coord_pairs = re.findall(r'[-\d.]+,[-\d.]+', d)
    points = []
    for pair in coord_pairs:
        parts = pair.split(',')
        points.append((float(parts[0]), float(parts[1])))
    return points


def build_canvas_silhouette(raw_pts, canvas_w, header_h):
    """
    Scale and position the silhouette polygon on the canvas.
    Width = MERL_W_TARGET, centered horizontally, top-aligned just below header.
    Returns (canvas_pts, scale, tx, ty, sil_poly).
    """
    scale = MERL_W_TARGET / SVG_VW
    merl_w = MERL_W_TARGET
    merl_h = int(SVG_VH * scale)

    tx = (canvas_w - merl_w) // 2
    ty = header_h + 10  # small gap below header

    canvas_pts = [(x * scale + tx, y * scale + ty) for (x, y) in raw_pts]

    if SHAPELY:
        sil_poly = Polygon(canvas_pts)
        if not sil_poly.is_valid:
            sil_poly = sil_poly.buffer(0)
    else:
        sil_poly = None

    return canvas_pts, scale, tx, ty, sil_poly


# ─── STEP 3: Packing ─────────────────────────────────────────────────────────

def rect_inside_silhouette(cx, cy, w, h, sil_poly, canvas_pts):
    """
    Check if rectangle (cx, cy, w, h) centroid-based fits inside the silhouette.
    Uses shapely if available, otherwise point-in-poly on corners.
    """
    x0, y0 = cx - w / 2, cy - h / 2
    x1, y1 = cx + w / 2, cy + h / 2

    if SHAPELY and sil_poly is not None:
        # All 4 corners + centroid must be inside
        test_pts = [
            (cx, cy),
            (x0 + 4, y0 + 4),
            (x1 - 4, y0 + 4),
            (x0 + 4, y1 - 4),
            (x1 - 4, y1 - 4),
        ]
        return all(sil_poly.contains(Point(px, py)) for px, py in test_pts)
    else:
        # Fallback: simple point-in-polygon for corners
        def pip(px, py, poly):
            n = len(poly)
            inside = False
            j = n - 1
            for i in range(n):
                xi, yi = poly[i]
                xj, yj = poly[j]
                if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi + 1e-9) + xi):
                    inside = not inside
                j = i
            return inside
        corners = [(x0+2, y0+2), (x1-2, y0+2), (x0+2, y1-2), (x1-2, y1-2), (cx, cy)]
        return all(pip(px, py, canvas_pts) for px, py in corners)


def rects_overlap(r1, r2):
    """r1, r2 = (cx, cy, w, h). Returns True if they overlap."""
    ax0, ay0 = r1[0] - r1[2] / 2, r1[1] - r1[3] / 2
    ax1, ay1 = r1[0] + r1[2] / 2, r1[1] + r1[3] / 2
    bx0, by0 = r2[0] - r2[2] / 2, r2[1] - r2[3] / 2
    bx1, by1 = r2[0] + r2[2] / 2, r2[1] + r2[3] / 2
    return not (ax1 <= bx0 or bx1 <= ax0 or ay1 <= by0 or by1 <= ay0)


def dist_to_rect(px, py, cx, cy, w, h):
    """Min distance from point to rectangle edge (for spread score)."""
    dx = max(abs(px - cx) - w / 2, 0)
    dy = max(abs(py - cy) - h / 2, 0)
    return math.sqrt(dx * dx + dy * dy)


def dist_to_silhouette(cx, cy, sil_poly, canvas_pts):
    """Approximate distance from point to silhouette boundary."""
    if SHAPELY and sil_poly is not None:
        pt = Point(cx, cy)
        return sil_poly.exterior.distance(pt)
    # Fallback: min dist to any vertex
    min_d = float('inf')
    for px, py in canvas_pts:
        d = math.hypot(cx - px, cy - py)
        if d < min_d:
            min_d = d
    return min_d


def generate_candidate_grid(sil_poly, canvas_pts, step=GRID_STEP):
    """Generate candidate centroid positions inside the silhouette (excluding near-boundary)."""
    if SHAPELY and sil_poly is not None:
        bounds = sil_poly.bounds   # (minx, miny, maxx, maxy)
    else:
        xs = [p[0] for p in canvas_pts]
        ys = [p[1] for p in canvas_pts]
        bounds = (min(xs), min(ys), max(xs), max(ys))

    candidates = []
    x = bounds[0] + step
    while x < bounds[2]:
        y = bounds[1] + step
        while y < bounds[3]:
            # Must be inside silhouette and away from boundary
            if SHAPELY and sil_poly is not None:
                pt = Point(x, y)
                if sil_poly.contains(pt):
                    d = sil_poly.exterior.distance(pt)
                    if d >= BOUNDARY_MARGIN:
                        candidates.append((x, y))
            else:
                # Fallback pip
                def pip_fast(px, py, poly):
                    n = len(poly)
                    inside = False
                    j = n - 1
                    for i in range(n):
                        xi, yi = poly[i]
                        xj, yj = poly[j]
                        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi + 1e-9) + xi):
                            inside = not inside
                        j = i
                    return inside
                if pip_fast(x, y, canvas_pts):
                    candidates.append((x, y))
            y += step
        x += step
    return candidates


def pack_stickers(crop_sizes, sil_poly, canvas_pts, target_area_each):
    """
    Greedy placement of 32 stickers, largest first.
    Strategy: scan candidate grid top-to-bottom, left-to-right.
    Pick the first valid position (inside silhouette, no overlap).
    This gives dense packing — no wasted space from spread-maximisation.
    Returns list of placed = [(sticker_id, cx, cy, w_s, h_s), ...].
    """
    # Compute scaled dimensions for each sticker
    sticker_dims = {}
    for sid, (cw, ch) in crop_sizes.items():
        aspect = cw / ch if ch > 0 else 1.0
        # w_s * h_s = target_area_each, w_s/h_s = aspect
        h_s = math.sqrt(target_area_each / aspect)
        w_s = aspect * h_s
        sticker_dims[sid] = (w_s, h_s)

    # Sort largest-area sticker first for packing stability
    order = sorted(sticker_dims.keys(), key=lambda s: sticker_dims[s][0] * sticker_dims[s][1], reverse=True)

    # Generate candidate grid once (sorted top-to-bottom, left-to-right for dense packing)
    print(f"  Generating candidate grid (step={GRID_STEP}px)...")
    candidates = generate_candidate_grid(sil_poly, canvas_pts, GRID_STEP)
    # Sort: top-to-bottom primary, left-to-right secondary
    candidates.sort(key=lambda c: (round(c[1] / GRID_STEP), round(c[0] / GRID_STEP)))
    print(f"  {len(candidates)} candidate positions inside silhouette (>{BOUNDARY_MARGIN}px from boundary)")

    placed = []       # list of (sid, cx, cy, w_s, h_s)
    failed_ids = []

    for sid in order:
        w_s, h_s = sticker_dims[sid]
        placed_pos = None

        for (cx, cy) in candidates:
            # Must fit inside silhouette
            if not rect_inside_silhouette(cx, cy, w_s, h_s, sil_poly, canvas_pts):
                continue

            # Must not overlap any placed sticker
            overlap = False
            for (_, pcx, pcy, pw, ph) in placed:
                if rects_overlap((cx, cy, w_s, h_s), (pcx, pcy, pw, ph)):
                    overlap = True
                    break
            if overlap:
                continue

            # First valid position — take it
            placed_pos = (cx, cy)
            break

        if placed_pos:
            cx, cy = placed_pos
            placed.append((sid, cx, cy, w_s, h_s))
        else:
            failed_ids.append(sid)

    return placed, failed_ids, sticker_dims


def step3_pack(crop_sizes, sil_poly, canvas_pts):
    """Run packing with retry on scale-down. Returns (placed, failed, scale_factor)."""
    if SHAPELY and sil_poly is not None:
        sil_area = sil_poly.area
    else:
        # Approximate silhouette area via shoelace
        n = len(canvas_pts)
        area = 0
        for i in range(n):
            x0_, y0_ = canvas_pts[i]
            x1_, y1_ = canvas_pts[(i + 1) % n]
            area += x0_ * y1_ - x1_ * y0_
        sil_area = abs(area) / 2

    print(f"  Silhouette area: {sil_area:.0f} px^2")
    base_area_each = TARGET_COVERAGE * sil_area / N_STICKERS
    print(f"  Target area per sticker: {base_area_each:.0f} px^2 "
          f"(~{math.sqrt(base_area_each):.0f}x{math.sqrt(base_area_each):.0f} avg)")

    scale_factor = 1.0
    for attempt in range(MAX_RETRIES + 1):
        area_each = base_area_each * (scale_factor ** 2)
        print(f"\n  Attempt {attempt + 1}: scale={scale_factor:.2f}, "
              f"area_each={area_each:.0f} px^2")
        placed, failed, sticker_dims = pack_stickers(crop_sizes, sil_poly, canvas_pts, area_each)
        print(f"  Placed: {len(placed)}/32, Failed: {len(failed)}")
        if len(failed) == 0:
            print(f"  All 32 placed successfully.")
            break
        if attempt < MAX_RETRIES:
            scale_factor -= SCALE_DOWN_STEP
            print(f"  Retrying with smaller stickers (scale {scale_factor:.2f})...")

    return placed, failed, scale_factor


# ─── STEP 4: Rendering ────────────────────────────────────────────────────────

def load_cropped_sticker(sid):
    """Load cropped sticker from CROPPED_DIR."""
    fname = FILENAME_MAP.get(sid)
    if not fname:
        return None
    p = CROPPED_DIR / fname
    if not p.exists():
        return None
    try:
        return Image.open(str(p)).convert("RGBA")
    except Exception as e:
        print(f"  WARN: failed to load cropped #{sid}: {e}")
        return None


def draw_silhouette_outline(draw, canvas_pts, color=SIL_OUTLINE_COLOR, width=2):
    """Draw silhouette outline on the draw context."""
    coords = [(int(x), int(y)) for x, y in canvas_pts]
    draw.line(coords + [coords[0]], fill=color, width=width)


def draw_number_badge(draw, x, y, number, font):
    """Draw tiny number badge: white circle + dark number, at (x, y) top-left of sticker."""
    r = 12
    cx, cy = x + r + 2, y + r + 2
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=BADGE_BG)
    label = str(number)
    tw, th = text_size(draw, label, font)
    draw.text((cx - tw // 2, cy - th // 2), label, fill=BADGE_TEXT, font=font)


def step4_render(canvas, placed, sil_poly, canvas_pts):
    """Paste all placed stickers onto canvas, draw silhouette outline on top."""
    draw = ImageDraw.Draw(canvas, "RGBA")
    badge_font = load_font(10, bold=True)

    total_sticker_area = 0

    # Sort by sticker id for predictable rendering order
    placed_sorted = sorted(placed, key=lambda p: p[0])

    for (sid, cx, cy, w_s, h_s) in placed_sorted:
        img = load_cropped_sticker(sid)
        if img is None:
            print(f"  WARN: cropped sticker #{sid} not found — skipping")
            continue

        w_i, h_i = int(round(w_s)), int(round(h_s))
        if w_i < 1 or h_i < 1:
            continue

        resized = img.resize((w_i, h_i), Image.LANCZOS)

        # Paste at centroid (cx, cy) — top-left corner = cx - w/2, cy - h/2
        px = int(round(cx - w_i / 2))
        py = int(round(cy - h_i / 2))

        canvas.paste(resized, (px, py), resized)   # full opacity, transparent bg
        total_sticker_area += w_i * h_i

        # Number badge at top-left of sticker bbox
        draw_number_badge(draw, px, py, sid, badge_font)

    # Draw silhouette outline on top (subtle reference line)
    draw_silhouette_outline(draw, canvas_pts)

    return total_sticker_area


# ─── STEP 5: Page chrome ─────────────────────────────────────────────────────

def draw_page_chrome(canvas):
    draw = ImageDraw.Draw(canvas)

    f_title    = load_font(36, bold=True)
    f_subtitle = load_font(14)
    f_footer   = load_font(12)

    # Title
    title = "Merlion Puzzle \u2014 My Singapore Stories"
    tw, th = text_size(draw, title, f_title)
    draw.text(((A4_W - tw) // 2, 18), title, fill=TITLE_COLOR, font=f_title)

    # Subtitle
    subtitle = "Design draft \u2014 sticker layout for cutting"
    sw, sh = text_size(draw, subtitle, f_subtitle)
    draw.text(((A4_W - sw) // 2, 18 + th + 8), subtitle, fill=SUBTITLE_COLOR, font=f_subtitle)

    # Footer
    footer = "Little Dot Book  \u00b7  Book 2  \u00b7  v10 draft"
    fw, fh = text_size(draw, footer, f_footer)
    draw.text(((A4_W - fw) // 2, A4_H - fh - 20), footer, fill=FOOTER_COLOR, font=f_footer)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Merlion Puzzle A4 — v10: Auto-crop + Pack Stickers")
    print("=" * 60)

    # STEP 1: Crop stickers
    crop_sizes = step1_crop_all_stickers()

    # Verify 32 cropped stickers exist and have transparency
    cropped_ok = 0
    for sid in range(1, N_STICKERS + 1):
        fname = FILENAME_MAP.get(sid)
        if fname:
            p = CROPPED_DIR / fname
            if p.exists():
                try:
                    img = Image.open(str(p))
                    if img.mode == "RGBA":
                        cropped_ok += 1
                    else:
                        print(f"  WARN #{sid}: cropped file not RGBA (mode={img.mode})")
                except Exception as e:
                    print(f"  WARN #{sid}: verify failed: {e}")

    print(f"\n  Verified: {cropped_ok}/32 cropped stickers have RGBA transparency")

    # STEP 2: Parse silhouette
    print("\n[STEP 2] Parsing SVG silhouette...")
    raw_pts = parse_svg_polygon(SVG_PATH)
    print(f"  {len(raw_pts)} polygon vertices parsed")

    canvas_pts, scale, tx, ty, sil_poly = build_canvas_silhouette(raw_pts, A4_W, HEADER_H)
    print(f"  Scale={scale:.4f}, offset=({tx},{ty})")
    if SHAPELY and sil_poly:
        print(f"  Shapely silhouette area: {sil_poly.area:.0f} px^2")
        print(f"  Silhouette bounds: {[int(v) for v in sil_poly.bounds]}")

    # STEP 3: Pack stickers
    print("\n[STEP 3] Packing stickers inside silhouette...")
    placed, failed, scale_factor = step3_pack(crop_sizes, sil_poly, canvas_pts)

    # STEP 4: Render canvas
    print("\n[STEP 4] Rendering canvas...")
    canvas = Image.new("RGB", (A4_W, A4_H), BG_COLOR)

    draw_page_chrome(canvas)

    total_sticker_area = step4_render(canvas, placed, sil_poly, canvas_pts)

    # STEP 5: Save
    canvas.save(str(OUTPUT_PATH), "PNG", dpi=(150, 150))
    print(f"\n  Saved: {OUTPUT_PATH}")

    # ─── Stats ────────────────────────────────────────────────────────────────
    if SHAPELY and sil_poly:
        sil_area = sil_poly.area
    else:
        n = len(canvas_pts)
        area = 0
        for i in range(n):
            x0_, y0_ = canvas_pts[i]
            x1_, y1_ = canvas_pts[(i + 1) % n]
            area += x0_ * y1_ - x1_ * y0_
        sil_area = abs(area) / 2

    coverage_pct = total_sticker_area / sil_area * 100 if sil_area > 0 else 0

    # Avg crop bbox stats
    if crop_sizes:
        avg_w = sum(w for w, h in crop_sizes.values()) / len(crop_sizes)
        avg_h = sum(h for w, h in crop_sizes.values()) / len(crop_sizes)
        avg_pct_of_orig = (avg_w * avg_h) / (1024 * 1024) * 100  # vs 1024x1024 baseline
    else:
        avg_w = avg_h = avg_pct_of_orig = 0

    print("\n" + "=" * 60)
    print(f"DONE: {len(placed)}/32 stickers placed, {len(failed)} failed")
    print(f"FILES: {OUTPUT_PATH}")
    print(f"       {CROPPED_DIR}/")
    print(f"CROP RESULTS: {len(crop_sizes)} stickers cropped, "
          f"avg crop bbox {avg_w:.0f}x{avg_h:.0f}px "
          f"({avg_pct_of_orig:.1f}% of 1024x1024 baseline)")
    print(f"PLACEMENT: {len(placed)} placed / {len(failed)} failed, "
          f"final scale factor={scale_factor:.2f}")
    print(f"COVERAGE: sticker area {total_sticker_area:.0f}px^2, "
          f"silhouette {sil_area:.0f}px^2, "
          f"coverage={coverage_pct:.1f}%")
    if failed:
        print(f"ISSUES: stickers that did not fit: {failed}")
    else:
        print("ISSUES: None — all 32 stickers placed")
    print(f"NEXT: Open {OUTPUT_PATH} in Illustrator, draw puzzle cut lines over stickers")
    print("=" * 60)

    return len(placed), len(failed), scale_factor, coverage_pct


if __name__ == "__main__":
    main()
