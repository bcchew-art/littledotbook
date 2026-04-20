"""
generate_a4_mockup_v8.py
Merlion Puzzle A4 — v8: Region-split tessellation (body + tail)

Algorithm:
1. Parse silhouette to shapely Polygon.
2. Split silhouette into body_poly and tail_poly using a diagonal cut line
   that separates the fish tail (lower-right protrusion) from the main body.
3. Allocate 32 pieces proportional to area: n_tail = round(32 * tail_area / total),
   n_body = 32 - n_tail.
4. Tessellate BODY with v7's equal-area sine-wave algorithm, rows x cols ≈ n_body.
5. Tessellate TAIL similarly, scoped to tail_poly.
6. Combine pieces, sort reading order (body first, tail last by centroid y/x).
7. Assign categories, render with same chrome as v7.
"""

import os
import re
import math
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import Polygon, MultiPolygon, GeometryCollection, box as shapely_box
from shapely.geometry import LineString
from shapely.ops import unary_union

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR    = r"C:/Users/Admin/Projects/oinio/littledotbook/design-hub/assets"
SVG_PATH    = r"C:/Users/Admin/Projects/oinio/littledotbook/design-hub/assets/merlion-silhouette.svg"
OUTPUT_PATH = os.path.join(BASE_DIR, "merlion-puzzle-a4-v8.png")

# ─── Canvas ──────────────────────────────────────────────────────────────────
A4_W, A4_H = 1240, 1754
BG_COLOR = (253, 251, 245)

SVG_VW, SVG_VH = 600, 800
MERL_W_TARGET = 900
SCALE = MERL_W_TARGET / SVG_VW
MERL_W = MERL_W_TARGET
MERL_H = int(SVG_VH * SCALE)
MERL_X = (A4_W - MERL_W) // 2
MERL_Y = 170

# Piece count
N_PIECES = 32

# Stroke colours
PIECE_STROKE_INNER = (45, 55, 72)
PIECE_STROKE_OUTER = (45, 55, 72)

# Sine-wave cut parameters (reproducible)
RNG_SEED = 42
H_AMP    = 12    # horizontal cut amplitude (px)
H_WAVE   = 200   # horizontal cut wavelength (px)
H_NPTS   = 40    # sample points for horizontal cuts
V_AMP    = 10    # vertical cut amplitude (px)
V_WAVE   = 180   # vertical cut wavelength (px)
V_NPTS   = 30    # sample points for vertical cuts

TOLERANCE = 0.01   # 1% binary-search tolerance

# Category colours
CATS = {
    "Landmarks": (255, 155, 130),
    "Transport":  (100, 210, 200),
    "Food":       (255, 185, 100),
    "Culture":    (185, 170, 255),
    "Nature":     (130, 230, 195),
    "National":   (240, 205, 80),
}
CAT_PASTEL = {k: tuple(int(c * 0.25 + 255 * 0.75) for c in v) for k, v in CATS.items()}

ICONS = [
    (1,  "Merlion",           "Landmarks"),
    (2,  "MBS",               "Landmarks"),
    (3,  "Esplanade",         "Landmarks"),
    (4,  "Gardens by Bay",    "Landmarks"),
    (5,  "Singapore Flyer",   "Landmarks"),
    (6,  "Changi Jewel",      "Landmarks"),
    (7,  "National Museum",   "Landmarks"),
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


# ─── SVG parsing ─────────────────────────────────────────────────────────────

def parse_svg_polygon(svg_file):
    with open(svg_file, "r") as f:
        content = f.read()
    m = re.search(r'\bd="(M[^"]+)"', content, re.DOTALL)
    if not m:
        raise ValueError("No 'd' attribute found in SVG")
    d = m.group(1)
    coord_pairs = re.findall(r'[-\d.]+,[-\d.]+', d)
    points = []
    for pair in coord_pairs:
        parts = pair.split(',')
        points.append((float(parts[0]), float(parts[1])))
    return points


def scale_points_to_canvas(raw_pts, scale, tx, ty):
    return [(x * scale + tx, y * scale + ty) for (x, y) in raw_pts]


# ─── Geometry helpers ─────────────────────────────────────────────────────────

def collect_polygons(geom):
    """Return list of all Polygon parts from any geometry type."""
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom] if geom.area > 0 else []
    if isinstance(geom, (MultiPolygon, GeometryCollection)):
        result = []
        for g in geom.geoms:
            result.extend(collect_polygons(g))
        return result
    return []


def merge_geom(geom):
    """Merge all polygons in geom into a single geometry via unary_union."""
    polys = collect_polygons(geom)
    if not polys:
        return None
    return unary_union(polys) if len(polys) > 1 else polys[0]


def silhouette_area_between(sil, minx, maxx, y_top, y_bot):
    """Area of silhouette clipped to horizontal band [y_top, y_bot]."""
    clip = shapely_box(minx, y_top, maxx, y_bot)
    inter = sil.intersection(clip)
    return inter.area


def strip_area_left_of_x(strip_geom, minx, maxx, miny, maxy, x_cut):
    """Area of strip_geom clipped to left of x_cut."""
    clip = shapely_box(minx, miny, x_cut, maxy)
    inter = strip_geom.intersection(clip)
    return inter.area


# --- Body/Tail split -------------------------------------------------------

def split_body_tail(sil_poly):
    tail_box = shapely_box(718, 755, sil_poly.bounds[2] + 50, 1025)
    tail_poly = merge_geom(sil_poly.intersection(tail_box))
    body_poly = merge_geom(sil_poly.difference(tail_box))
    if tail_poly is None or tail_poly.is_empty:
        print("  WARNING: tail_poly empty")
        return sil_poly, None
    total_area = sil_poly.area
    body_frac = body_poly.area / total_area
    tail_frac = tail_poly.area / total_area
    print(f"  Tail clip: x>718, y=[755,1025]")
    print(f"  Body: {body_frac*100:.1f}%  ({body_poly.geom_type})")
    print(f"  Tail: {tail_frac*100:.1f}%  ({tail_poly.geom_type})")
    return body_poly, tail_poly


def find_equal_area_y_cuts(sil, n_strips, tol=0.01):
    """
    Binary-search y cut positions so each horizontal strip has equal area.
    Returns list of n_strips+1 y-boundaries.
    """
    minx, miny, maxx, maxy = sil.bounds
    total_area = sil.area
    target_per_strip = total_area / n_strips

    y_cuts = [miny]
    current_top = miny

    for i in range(n_strips - 1):
        target_cumulative = target_per_strip * (i + 1)
        lo, hi = current_top, maxy
        for _ in range(60):
            mid = (lo + hi) / 2
            area = silhouette_area_between(sil, minx, maxx, miny, mid)
            if abs(area - target_cumulative) / total_area < tol / n_strips:
                break
            if area < target_cumulative:
                lo = mid
            else:
                hi = mid
        y_cuts.append(mid)
        current_top = mid

    y_cuts.append(maxy)
    return y_cuts


# ─── Equal-area vertical cuts within a strip ─────────────────────────────────

def find_equal_area_x_cuts(strip_geom, n_cols, tol=0.01):
    """
    Binary-search x cut positions within strip_geom so each column piece has equal area.
    Returns list of n_cols+1 x-boundaries.
    """
    minx, miny, maxx, maxy = strip_geom.bounds
    strip_area = strip_geom.area
    target_per_col = strip_area / n_cols

    x_cuts = [minx]

    for i in range(n_cols - 1):
        target_cumulative = target_per_col * (i + 1)
        lo, hi = minx, maxx
        for _ in range(60):
            mid = (lo + hi) / 2
            area = strip_area_left_of_x(strip_geom, minx, maxx, miny, maxy, mid)
            if abs(area - target_cumulative) / max(strip_area, 1) < tol / n_cols:
                break
            if area < target_cumulative:
                lo = mid
            else:
                hi = mid
        x_cuts.append(mid)

    x_cuts.append(maxx)
    return x_cuts


# ─── Sine-wave cut generation ─────────────────────────────────────────────────

def make_hwave_mask_top(x0, x1, y_top_bound, y_base, amplitude, wavelength, phase, n_pts, pad=80):
    """
    Build a Polygon that covers the TOP half of a horizontal wave cut.
    """
    xs = np.linspace(x0 - pad, x1 + pad, n_pts)
    ys_wave = y_base + amplitude * np.sin(2 * math.pi * xs / wavelength + phase)

    bottom_pts = list(zip(xs.tolist(), ys_wave.tolist()))
    top_left  = (x0 - pad, y_top_bound)
    top_right = (x1 + pad, y_top_bound)
    coords = [top_left] + bottom_pts + [top_right, top_left]
    return Polygon(coords)


def make_vwave_mask_left(y0, y1, x_left_bound, x_base, amplitude, wavelength, phase, n_pts, pad=80):
    """
    Build a Polygon that covers the LEFT half of a vertical wave cut.
    """
    ys = np.linspace(y0 - pad, y1 + pad, n_pts)
    xs_wave = x_base + amplitude * np.sin(2 * math.pi * ys / wavelength + phase)

    right_pts = list(zip(xs_wave.tolist(), ys.tolist()))
    bot_left = (x_left_bound, y1 + pad)
    top_left = (x_left_bound, y0 - pad)
    coords = right_pts + [bot_left, top_left, right_pts[0]]
    return Polygon(coords)


def split_horizontal(geom, y_base, x0, x1, amplitude, wavelength, phase, n_pts):
    """
    Split geom horizontally with a sine-wave at y_base.
    Returns (top_part, bottom_part).
    """
    if geom is None or geom.is_empty:
        return None, None

    b = geom.bounds
    y_top_bound = b[1] - 100

    top_mask = make_hwave_mask_top(x0, x1, y_top_bound, y_base, amplitude, wavelength, phase, n_pts)
    if not top_mask.is_valid:
        top_mask = top_mask.buffer(0)

    top = merge_geom(geom.intersection(top_mask))
    bot = merge_geom(geom.difference(top_mask))

    if top is None or top.area < 1:
        top = merge_geom(geom.intersection(shapely_box(b[0], b[1], b[2], y_base)))
    if bot is None or bot.area < 1:
        bot = merge_geom(geom.difference(shapely_box(b[0], b[1], b[2], y_base)))

    return top, bot


def split_vertical(geom, x_base, y0, y1, amplitude, wavelength, phase, n_pts):
    """
    Split geom vertically with a sine-wave at x_base.
    Returns (left_part, right_part).
    """
    if geom is None or geom.is_empty:
        return None, None

    b = geom.bounds
    x_left_bound = b[0] - 100

    left_mask = make_vwave_mask_left(y0, y1, x_left_bound, x_base, amplitude, wavelength, phase, n_pts)
    if not left_mask.is_valid:
        left_mask = left_mask.buffer(0)

    left = merge_geom(geom.intersection(left_mask))
    rgt  = merge_geom(geom.difference(left_mask))

    if left is None or left.area < 1:
        left = merge_geom(geom.intersection(shapely_box(b[0], b[1], x_base, b[3])))
    if rgt is None or rgt.area < 1:
        rgt  = merge_geom(geom.difference(shapely_box(b[0], b[1], x_base, b[3])))

    return left, rgt


# ─── Region tessellation ─────────────────────────────────────────────────────

def pick_rows_cols(n_pieces, region_poly):
    """
    Pick (rows, cols) such that rows * cols >= n_pieces
    and the aspect ratio matches the region.
    """
    if n_pieces <= 1:
        return 1, 1

    b = region_poly.bounds
    width  = b[2] - b[0]
    height = b[3] - b[1]
    aspect = height / max(width, 1)  # > 1 = tall, < 1 = wide

    best_rows, best_cols = n_pieces, 1
    best_score = float('inf')

    for rows in range(1, n_pieces + 1):
        cols = math.ceil(n_pieces / rows)
        if rows * cols < n_pieces:
            continue
        # Score: how well does rows/cols match the aspect ratio?
        ratio = rows / max(cols, 1)
        score = abs(math.log(ratio) - math.log(max(aspect, 0.1)))
        if score < best_score:
            best_score = score
            best_rows, best_cols = rows, cols

    return best_rows, best_cols


def tessellate_region(region_poly, n_pieces, rng, label="region"):
    """
    Tessellate a polygon into approximately n_pieces equal-area pieces
    using the v7 equal-area sine-wave algorithm.

    Returns list of shapely geometries.
    """
    if region_poly is None or region_poly.is_empty or n_pieces <= 0:
        return []

    if n_pieces == 1:
        return [region_poly]

    n_rows, n_cols = pick_rows_cols(n_pieces, region_poly)
    print(f"  [{label}] {n_pieces} pieces -> {n_rows} rows x {n_cols} cols")

    minx, miny, maxx, maxy = region_poly.bounds
    total_area = region_poly.area
    target_area = total_area / n_pieces
    print(f"  [{label}] area={total_area:.0f}px^2, target/piece={target_area:.0f}px^2")

    # Equal-area y cuts
    y_cuts = find_equal_area_y_cuts(region_poly, n_rows, tol=TOLERANCE)

    # Equal-area x cuts per strip
    strip_cuts = []
    for i in range(n_rows):
        y_top = y_cuts[i]
        y_bot = y_cuts[i + 1]
        clip = shapely_box(minx, y_top, maxx, y_bot)
        strip = merge_geom(region_poly.intersection(clip))
        if strip is None or strip.area < 1:
            x_cuts = [minx + (maxx - minx) * j / n_cols for j in range(n_cols + 1)]
        else:
            x_cuts = find_equal_area_x_cuts(strip, n_cols, tol=TOLERANCE)
        strip_cuts.append((strip, x_cuts))

    # Generate sine-wave phases
    h_phases = [rng.uniform(0, 2 * math.pi) for _ in range(n_rows - 1)]
    v_phases = [[rng.uniform(0, 2 * math.pi) for _ in range(n_cols - 1)] for _ in range(n_rows)]

    # Split region into horizontal strips with sine waves
    remaining = merge_geom(region_poly)
    wave_strips = []

    for i in range(n_rows - 1):
        y_cut = y_cuts[i + 1]
        phase = h_phases[i]
        top_part, remaining = split_horizontal(
            remaining, y_cut, minx, maxx,
            H_AMP, H_WAVE, phase, H_NPTS
        )
        if top_part is None:
            top_part = merge_geom(region_poly.intersection(
                shapely_box(minx, y_cuts[i], maxx, y_cuts[i + 1])))
        wave_strips.append(top_part)

    if remaining is not None and remaining.area > 1:
        wave_strips.append(remaining)
    else:
        last = merge_geom(region_poly.intersection(
            shapely_box(minx, y_cuts[-2], maxx, y_cuts[-1])))
        wave_strips.append(last)

    while len(wave_strips) < n_rows:
        wave_strips.append(None)

    # Split each strip into columns
    all_pieces = []

    for i, strip in enumerate(wave_strips):
        if strip is None or strip.area < 1:
            for _ in range(n_cols):
                all_pieces.append(None)
            continue

        strip = merge_geom(strip.intersection(region_poly))
        if strip is None or strip.area < 1:
            for _ in range(n_cols):
                all_pieces.append(None)
            continue

        _, x_cuts = strip_cuts[i]
        strip_bounds = strip.bounds
        y0_s, y1_s = strip_bounds[1], strip_bounds[3]

        remaining_strip = merge_geom(strip)
        col_pieces = []

        for j in range(n_cols - 1):
            x_cut = x_cuts[j + 1]
            phase = v_phases[i][j]

            if remaining_strip is None or remaining_strip.is_empty or remaining_strip.area < 1:
                col_pieces.append(None)
                continue

            left_part, remaining_strip = split_vertical(
                remaining_strip, x_cut, y0_s, y1_s,
                V_AMP, V_WAVE, phase, V_NPTS
            )
            if left_part is None or left_part.is_empty or left_part.area < 1:
                left_part = merge_geom(strip.intersection(
                    shapely_box(x_cuts[j], y0_s, x_cut, y1_s)))
            col_pieces.append(left_part)

        if remaining_strip is not None and not remaining_strip.is_empty and remaining_strip.area > 1:
            col_pieces.append(remaining_strip)
        else:
            last_col = merge_geom(strip.intersection(
                shapely_box(x_cuts[-2], y0_s, x_cuts[-1], y1_s)))
            col_pieces.append(last_col)

        while len(col_pieces) < n_cols:
            col_pieces.append(None)

        all_pieces.extend(col_pieces[:n_cols])

    # Clean pieces: re-intersect with region, remove empties
    clean_pieces = []
    for p in all_pieces:
        if p is None or p.is_empty or p.area < 1:
            continue
        clipped = merge_geom(p.intersection(region_poly))
        if clipped is not None and clipped.area > 1:
            clean_pieces.append(clipped)

    # Merge/split to hit n_pieces target
    if len(clean_pieces) > n_pieces:
        while len(clean_pieces) > n_pieces:
            clean_pieces.sort(key=lambda p: p.area)
            smallest = clean_pieces[0]
            best_idx = 1
            best_dist = float('inf')
            for idx in range(1, len(clean_pieces)):
                d = smallest.centroid.distance(clean_pieces[idx].centroid)
                if d < best_dist:
                    best_dist = d
                    best_idx = idx
            merged = merge_geom(unary_union([smallest, clean_pieces[best_idx]]))
            clean_pieces = [p for i, p in enumerate(clean_pieces) if i not in (0, best_idx)]
            clean_pieces.append(merged)

    if len(clean_pieces) < n_pieces:
        print(f"  [{label}] WARNING: only {len(clean_pieces)} pieces, filling gap...")
        covered = unary_union([p for p in clean_pieces if p is not None])
        gap = merge_geom(region_poly.difference(covered))
        if gap is not None and gap.area > 1:
            n_missing = n_pieces - len(clean_pieces)
            gap_b = gap.bounds
            for k in range(n_missing):
                x_lo = gap_b[0] + (gap_b[2] - gap_b[0]) * k / n_missing
                x_hi = gap_b[0] + (gap_b[2] - gap_b[0]) * (k + 1) / n_missing
                sub = merge_geom(gap.intersection(shapely_box(x_lo, gap_b[1], x_hi, gap_b[3])))
                if sub and sub.area > 1:
                    clean_pieces.append(sub)

    return clean_pieces[:n_pieces]


# ─── Area statistics ─────────────────────────────────────────────────────────

def compute_area_stats(pieces, target_area, label=""):
    areas = [p.area for p in pieces if p is not None]
    if not areas:
        return {}
    arr = np.array(areas)
    return {
        "label":    label,
        "count":    len(areas),
        "min":      arr.min(),
        "max":      arr.max(),
        "mean":     arr.mean(),
        "std":      arr.std(),
        "pct_min":  (arr.min() / target_area * 100),
        "pct_max":  (arr.max() / target_area * 100),
        "pct_mean": (arr.mean() / target_area * 100),
        "pct_std":  (arr.std() / target_area * 100),
        "outliers": [(i+1, a, a/target_area*100) for i, a in enumerate(areas)
                     if abs(a - target_area) / target_area > 0.05],
    }


# ─── Piece ordering and category assignment ──────────────────────────────────

def sort_pieces_by_reading_order(pieces):
    """Sort top-to-bottom, left-to-right by centroid. Returns list of polygons."""
    valid = [(p.centroid.y, p.centroid.x, p) for p in pieces if p is not None]
    valid.sort()
    return [p for (_, _, p) in valid]


def assign_categories(n):
    """Category by reading order: 1-8 Landmarks, 9-13 Transport, 14-19 Food,
    20-26 Culture, 27-30 Nature, 31-32 National."""
    if n <= 8:
        return "Landmarks"
    elif n <= 13:
        return "Transport"
    elif n <= 19:
        return "Food"
    elif n <= 26:
        return "Culture"
    elif n <= 30:
        return "Nature"
    else:
        return "National"


# ─── Rendering helpers ────────────────────────────────────────────────────────

def poly_to_pil(geom):
    """Return list of coordinate lists for PIL polygon drawing."""
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [[(int(x), int(y)) for x, y in geom.exterior.coords]]
    if isinstance(geom, (MultiPolygon, GeometryCollection)):
        result = []
        for g in geom.geoms:
            result.extend(poly_to_pil(g))
        return result
    return []


def load_font(size, bold=False):
    candidates = (
        ["C:/Windows/Fonts/georgiab.ttf", "C:/Windows/Fonts/arialbd.ttf",
         "C:/Windows/Fonts/calibrib.ttf"]
        if bold else
        ["C:/Windows/Fonts/georgia.ttf", "C:/Windows/Fonts/arial.ttf",
         "C:/Windows/Fonts/calibri.ttf"]
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


def draw_piece_fill(draw, geom, fill_color):
    regions = poly_to_pil(geom)
    for coords in regions:
        if len(coords) >= 3:
            draw.polygon(coords, fill=fill_color)


def draw_piece_border(draw, geom, color, width):
    regions = poly_to_pil(geom)
    for coords in regions:
        if len(coords) >= 2:
            draw.line(coords + [coords[0]], fill=color, width=width)


def draw_number_badge(draw, cx, cy, number, cat, font_num):
    badge_r = 18
    bx, by = int(cx), int(cy)
    bx = max(badge_r + 2, min(A4_W - badge_r - 2, bx))
    by = max(badge_r + 2, min(A4_H - badge_r - 2, by))

    draw.ellipse([bx - badge_r, by - badge_r, bx + badge_r, by + badge_r],
                 fill=(255, 255, 255), outline=CATS[cat], width=2)
    ns = str(number)
    nw, nh = text_size(draw, ns, font_num)
    draw.text((bx - nw // 2, by - nh // 2), ns,
              fill=PIECE_STROKE_INNER, font=font_num)


# ─── Page chrome ─────────────────────────────────────────────────────────────

def draw_header(canvas):
    draw = ImageDraw.Draw(canvas)
    f_title = load_font(48, bold=True)
    f_sub   = load_font(30, bold=True)

    title = "Merlion Puzzle — My Singapore Stories"
    tw, _ = text_size(draw, title, f_title)
    draw.text(((A4_W - tw) // 2, 20), title, fill=(25, 55, 115), font=f_title)

    sub = "Match each sticker to its puzzle piece!"
    sw, _ = text_size(draw, sub, f_sub)
    draw.text(((A4_W - sw) // 2, 80), sub, fill=(200, 65, 45), font=f_sub)


def draw_legend(canvas):
    draw = ImageDraw.Draw(canvas)
    f_leg  = load_font(19)
    f_head = load_font(19, bold=True)
    swatch = 16
    pad = 6
    y = A4_H - 80

    items = [(cat, text_size(draw, cat, f_leg)) for cat in CATS]
    total_w = sum(swatch + pad + w + 22 for (cat, (w, h)) in items)
    head = "Category Key:"
    hw, _ = text_size(draw, head, f_head)
    x = (A4_W - total_w - hw - 14) // 2
    draw.text((x, y + 2), head, fill=(75, 75, 95), font=f_head)
    x += hw + 14
    for cat, (w, h) in items:
        color = CATS[cat]
        draw.rectangle([x, y + 4, x + swatch, y + swatch + 4], fill=color)
        draw.text((x + swatch + pad, y), cat, fill=(55, 55, 75), font=f_leg)
        x += swatch + pad + w + 22


def draw_footer(canvas):
    draw = ImageDraw.Draw(canvas)
    f = load_font(17)
    text = "Little Dot Book  \u00b7  Book 2"
    tw, _ = text_size(draw, text, f)
    draw.text(((A4_W - tw) // 2, A4_H - 34), text, fill=(155, 155, 175), font=f)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 65)
    print("Merlion Puzzle A4 Generator v8 — Region-Split Tessellation")
    print("=" * 65)

    # 1. Parse silhouette
    print("\n[1] Parsing SVG silhouette...")
    raw_pts = parse_svg_polygon(SVG_PATH)
    print(f"    {len(raw_pts)} polygon vertices")
    canvas_pts = scale_points_to_canvas(raw_pts, SCALE, MERL_X, MERL_Y)
    sil_poly = Polygon(canvas_pts)
    if not sil_poly.is_valid:
        sil_poly = sil_poly.buffer(0)
    print(f"    Silhouette area: {sil_poly.area:.0f} px^2")
    print(f"    Bounds: {tuple(f'{v:.1f}' for v in sil_poly.bounds)}")

    total_area = sil_poly.area

    # 2. Split into body and tail
    print("\n[2] Splitting silhouette into body + tail regions...")
    body_poly, tail_poly = split_body_tail(sil_poly)

    body_area = body_poly.area
    tail_area = tail_poly.area
    body_pct  = body_area / total_area * 100
    tail_pct  = tail_area / total_area * 100
    area_sum  = body_area + tail_area
    area_diff = abs(area_sum - total_area) / total_area * 100

    print(f"\n  Body area: {body_area:.0f} px^2 ({body_pct:.1f}%)")
    print(f"  Tail area: {tail_area:.0f} px^2 ({tail_pct:.1f}%)")
    print(f"  Sum check: {area_sum:.0f} vs {total_area:.0f} (diff={area_diff:.3f}%)")

    if area_diff > 0.5:
        print(f"  WARNING: Area sum differs from original by {area_diff:.2f}% (>0.5% tolerance)")
    else:
        print(f"  Area check PASSED (diff={area_diff:.3f}%)")

    # 3. Allocate pieces proportional to area
    n_tail = max(2, round(N_PIECES * tail_area / total_area))
    n_body = N_PIECES - n_tail

    print(f"\n[3] Piece allocation:")
    print(f"    Body: {n_body} pieces ({body_pct:.1f}% of area)")
    print(f"    Tail: {n_tail} pieces ({tail_pct:.1f}% of area)")
    print(f"    Total: {n_body + n_tail} pieces")

    # 4. Tessellate body
    print("\n[4] Tessellating body region...")
    rng = random.Random(RNG_SEED)
    body_pieces = tessellate_region(body_poly, n_body, rng, label="BODY")
    print(f"    Body pieces generated: {len(body_pieces)}")

    # 5. Tessellate tail
    print("\n[5] Tessellating tail region...")
    tail_pieces = tessellate_region(tail_poly, n_tail, rng, label="TAIL")
    print(f"    Tail pieces generated: {len(tail_pieces)}")

    # 6. Combine and sort
    print("\n[6] Combining and sorting pieces...")
    # Sort body and tail pieces separately by reading order, then combine
    sorted_body = sort_pieces_by_reading_order(body_pieces)
    sorted_tail = sort_pieces_by_reading_order(tail_pieces)
    sorted_pieces = sorted_body + sorted_tail
    piece_count = len(sorted_pieces)
    print(f"    Total pieces: {piece_count}")

    # 7. Coverage check
    all_union = unary_union([p for p in sorted_pieces if p is not None])
    covered  = all_union.area
    coverage = covered / total_area * 100
    gap      = total_area - covered
    print(f"\n[7] Coverage: {coverage:.2f}%  (gap = {gap:.1f} px^2)")

    # 8. Area statistics per region
    body_target = body_area / n_body if n_body > 0 else 1
    tail_target = tail_area / n_tail if n_tail > 0 else 1

    body_stats = compute_area_stats(sorted_body, body_target, label="BODY")
    tail_stats = compute_area_stats(sorted_tail, tail_target, label="TAIL")

    print("\n[8] Area statistics — BODY:")
    print(f"    Target: {body_target:.0f} px^2")
    print(f"    Min:    {body_stats['min']:.0f} px^2  ({body_stats['pct_min']:.1f}%)")
    print(f"    Max:    {body_stats['max']:.0f} px^2  ({body_stats['pct_max']:.1f}%)")
    print(f"    Mean:   {body_stats['mean']:.0f} px^2  ({body_stats['pct_mean']:.1f}%)")
    print(f"    StDev:  {body_stats['std']:.0f} px^2  ({body_stats['pct_std']:.1f}%)")

    print("\n    Area statistics — TAIL:")
    print(f"    Target: {tail_target:.0f} px^2")
    print(f"    Min:    {tail_stats['min']:.0f} px^2  ({tail_stats['pct_min']:.1f}%)")
    print(f"    Max:    {tail_stats['max']:.0f} px^2  ({tail_stats['pct_max']:.1f}%)")
    print(f"    Mean:   {tail_stats['mean']:.0f} px^2  ({tail_stats['pct_mean']:.1f}%)")
    print(f"    StDev:  {tail_stats['std']:.0f} px^2  ({tail_stats['pct_std']:.1f}%)")

    # 9. Render
    print("\n[9] Rendering canvas...")
    canvas = Image.new("RGB", (A4_W, A4_H), BG_COLOR)
    draw_header(canvas)
    draw = ImageDraw.Draw(canvas, "RGBA")
    font_num = load_font(16, bold=True)

    # Fill all pieces
    for i, piece in enumerate(sorted_pieces):
        num = i + 1
        cat = assign_categories(num)
        fill = CAT_PASTEL[cat]
        draw_piece_fill(draw, piece, fill)

    # Interior borders
    for piece in sorted_pieces:
        draw_piece_border(draw, piece, PIECE_STROKE_INNER, 2)

    # Silhouette outline
    sil_coords = [(int(x), int(y)) for x, y in sil_poly.exterior.coords]
    if len(sil_coords) >= 2:
        draw.line(sil_coords + [sil_coords[0]], fill=PIECE_STROKE_OUTER, width=3)

    # Number badges
    for i, piece in enumerate(sorted_pieces):
        num = i + 1
        cat = assign_categories(num)
        cx, cy = piece.centroid.x, piece.centroid.y
        draw_number_badge(draw, cx, cy, num, cat, font_num)

    draw_legend(canvas)
    draw_footer(canvas)

    # 10. Save
    canvas.save(OUTPUT_PATH, "PNG", dpi=(150, 150))
    print(f"\n    Saved: {OUTPUT_PATH}")

    # 11. Final summary
    print("\n" + "=" * 65)
    print(f"DONE: v8 region-split tessellation complete")
    print(f"FILES: {OUTPUT_PATH}")
    print(f"SPLIT: body={body_pct:.1f}% ({n_body} pieces), tail={tail_pct:.1f}% ({n_tail} pieces)")
    print(f"PIECE COUNT: {piece_count}/32")
    print(f"COVERAGE: {coverage:.2f}% (gap={gap:.1f}px^2)")
    print(f"BODY AREA STATS: min={body_stats['min']:.0f} / max={body_stats['max']:.0f} / "
          f"mean={body_stats['mean']:.0f} / stdev={body_stats['std']:.0f}")
    print(f"TAIL AREA STATS: min={tail_stats['min']:.0f} / max={tail_stats['max']:.0f} / "
          f"mean={tail_stats['mean']:.0f} / stdev={tail_stats['std']:.0f}")
    print("=" * 65)

    return piece_count


if __name__ == "__main__":
    main()
