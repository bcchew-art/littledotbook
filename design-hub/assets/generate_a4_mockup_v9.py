"""
generate_a4_mockup_v9.py
Merlion Puzzle A4 — v9: Size-matched sticker assignment + ghost sticker preview

Key changes from v8:
- Measure each sticker's visual weight (non-transparent pixel count)
- Measure each piece's area from tessellation
- Rank-match: biggest sticker -> biggest piece, etc.
- Ghost sticker preview at 25% alpha centered on piece centroid
- Number badge = assigned sticker's ORIGINAL number (not reading-order position)
- Category color = derived from assigned sticker's original number
"""

import os
import re
import math
import random
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageEnhance
from shapely.geometry import Polygon, MultiPolygon, GeometryCollection, box as shapely_box
from shapely.geometry import LineString
from shapely.ops import unary_union

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR    = r"C:/Users/Admin/Projects/oinio/littledotbook/design-hub/assets"
SVG_PATH    = r"C:/Users/Admin/Projects/oinio/littledotbook/design-hub/assets/merlion-silhouette.svg"
ICONS_DIR   = r"C:/Users/Admin/Projects/oinio/littledotbook/design-hub/assets/icons"
OUTPUT_PATH = os.path.join(BASE_DIR, "merlion-puzzle-a4-v9.png")

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

# Sine-wave cut parameters (reproducible — same seed as v8)
RNG_SEED = 42
H_AMP    = 12
H_WAVE   = 200
H_NPTS   = 40
V_AMP    = 10
V_WAVE   = 180
V_NPTS   = 30

TOLERANCE = 0.01

# Ghost sticker scale factor: sticker content fits within this fraction of inscribed circle
GHOST_FIT_FACTOR = 0.65  # 65% of inscribed circle diameter

# Category colours (by original sticker number)
CATS = {
    "Landmarks": (255, 155, 130),
    "Transport":  (100, 210, 200),
    "Food":       (255, 185, 100),
    "Culture":    (185, 170, 255),
    "Nature":     (130, 230, 195),
    "National":   (240, 205, 80),
}
CAT_PASTEL = {k: tuple(int(c * 0.25 + 255 * 0.75) for c in v) for k, v in CATS.items()}


def cat_for_sticker_num(n):
    """Category derived from original sticker number (1-based)."""
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


# ─── Sticker loading and measurement ─────────────────────────────────────────

def load_stickers(icons_dir):
    """
    Scan icons_dir for files matching '#N <name>.png' (N=1..32).
    For duplicates (same N), pick the one WITHOUT '[2]' in the name.
    Returns dict: {N: {'name': str, 'path': Path, 'img': PIL.Image}}
    Aborts if not exactly 32 unique numbers found.
    """
    pattern = re.compile(r'^#(\d+)\s+(.+)\.png$', re.IGNORECASE)
    icons_path = Path(icons_dir)

    candidates = {}  # N -> list of Path
    for p in icons_path.glob('*.png'):
        m = pattern.match(p.name)
        if not m:
            print(f"  WARNING: skipping non-matching file: {p.name}")
            continue
        n = int(m.group(1))
        name = m.group(2)
        if n not in candidates:
            candidates[n] = []
        candidates[n].append((p, name))

    # Pick preferred file per number: prefer no '[2]' variant
    stickers = {}
    for n, choices in candidates.items():
        if len(choices) == 1:
            path, name = choices[0]
        else:
            # Prefer the one without '[2]'
            preferred = [c for c in choices if '[2]' not in c[0].name]
            if preferred:
                path, name = preferred[0]
            else:
                path, name = choices[0]
            others = [c[0].name for c in choices if c[0] != path]
            print(f"  INFO: sticker #{n} has duplicates, using '{path.name}', skipping: {others}")
        stickers[n] = {'name': name, 'path': path}

    if len(stickers) != 32:
        found = sorted(stickers.keys())
        missing = [i for i in range(1, 33) if i not in stickers]
        extra   = [i for i in found if i > 32 or i < 1]
        raise RuntimeError(
            f"ABORT: expected 32 stickers (1..32), found {len(stickers)}. "
            f"Missing: {missing}, extra: {extra}"
        )

    # Load images
    for n, info in stickers.items():
        img = Image.open(info['path']).convert("RGBA")
        info['img'] = img

    print(f"  Loaded {len(stickers)} sticker files OK")
    return stickers


def measure_stickers(stickers):
    """
    For each sticker, compute:
      - visual_weight_px: count of pixels with alpha > 32
      - bbox: tight content bounding box (left, top, right, bottom)
      - bbox_diag: diagonal of content bbox
    Returns same dict with added keys.
    """
    print("\n[STICKER MEASUREMENTS]")
    print(f"  {'#':>3}  {'Name':<30}  {'weight_px':>10}  {'bbox_w':>7}  {'bbox_h':>7}  {'bbox_diag':>9}")
    print("  " + "-" * 70)

    for n in sorted(stickers.keys()):
        info = stickers[n]
        img = info['img']
        arr = np.array(img)
        alpha = arr[:, :, 3]

        mask = alpha > 32
        weight = int(mask.sum())

        # Tight bounding box
        rows = np.any(mask, axis=1)
        cols = np.any(mask, axis=0)
        if rows.any():
            rmin, rmax = np.where(rows)[0][[0, -1]]
            cmin, cmax = np.where(cols)[0][[0, -1]]
            bbox = (int(cmin), int(rmin), int(cmax), int(rmax))
            bw = int(cmax - cmin + 1)
            bh = int(rmax - rmin + 1)
            diag = math.sqrt(bw**2 + bh**2)
        else:
            bbox = (0, 0, img.width, img.height)
            bw, bh = img.width, img.height
            diag = math.sqrt(bw**2 + bh**2)

        info['visual_weight_px'] = weight
        info['bbox'] = bbox
        info['bbox_diag'] = diag

        print(f"  #{n:>2}  {info['name']:<30}  {weight:>10,}  {bw:>7}  {bh:>7}  {diag:>9.1f}")

    weights = [stickers[n]['visual_weight_px'] for n in stickers]
    print(f"\n  Min weight: {min(weights):,}  Max: {max(weights):,}  Mean: {int(np.mean(weights)):,}")
    return stickers


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
    polys = collect_polygons(geom)
    if not polys:
        return None
    return unary_union(polys) if len(polys) > 1 else polys[0]


def silhouette_area_between(sil, minx, maxx, y_top, y_bot):
    clip = shapely_box(minx, y_top, maxx, y_bot)
    inter = sil.intersection(clip)
    return inter.area


def strip_area_left_of_x(strip_geom, minx, maxx, miny, maxy, x_cut):
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


def find_equal_area_x_cuts(strip_geom, n_cols, tol=0.01):
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
    xs = np.linspace(x0 - pad, x1 + pad, n_pts)
    ys_wave = y_base + amplitude * np.sin(2 * math.pi * xs / wavelength + phase)
    bottom_pts = list(zip(xs.tolist(), ys_wave.tolist()))
    top_left  = (x0 - pad, y_top_bound)
    top_right = (x1 + pad, y_top_bound)
    coords = [top_left] + bottom_pts + [top_right, top_left]
    return Polygon(coords)


def make_vwave_mask_left(y0, y1, x_left_bound, x_base, amplitude, wavelength, phase, n_pts, pad=80):
    ys = np.linspace(y0 - pad, y1 + pad, n_pts)
    xs_wave = x_base + amplitude * np.sin(2 * math.pi * ys / wavelength + phase)
    right_pts = list(zip(xs_wave.tolist(), ys.tolist()))
    bot_left = (x_left_bound, y1 + pad)
    top_left = (x_left_bound, y0 - pad)
    coords = right_pts + [bot_left, top_left, right_pts[0]]
    return Polygon(coords)


def split_horizontal(geom, y_base, x0, x1, amplitude, wavelength, phase, n_pts):
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
    if n_pieces <= 1:
        return 1, 1
    b = region_poly.bounds
    width  = b[2] - b[0]
    height = b[3] - b[1]
    aspect = height / max(width, 1)
    best_rows, best_cols = n_pieces, 1
    best_score = float('inf')
    for rows in range(1, n_pieces + 1):
        cols = math.ceil(n_pieces / rows)
        if rows * cols < n_pieces:
            continue
        ratio = rows / max(cols, 1)
        score = abs(math.log(ratio) - math.log(max(aspect, 0.1)))
        if score < best_score:
            best_score = score
            best_rows, best_cols = rows, cols
    return best_rows, best_cols


def tessellate_region(region_poly, n_pieces, rng, label="region"):
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

    y_cuts = find_equal_area_y_cuts(region_poly, n_rows, tol=TOLERANCE)

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

    h_phases = [rng.uniform(0, 2 * math.pi) for _ in range(n_rows - 1)]
    v_phases = [[rng.uniform(0, 2 * math.pi) for _ in range(n_cols - 1)] for _ in range(n_rows)]

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

    clean_pieces = []
    for p in all_pieces:
        if p is None or p.is_empty or p.area < 1:
            continue
        clipped = merge_geom(p.intersection(region_poly))
        if clipped is not None and clipped.area > 1:
            clean_pieces.append(clipped)

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


# ─── Piece ordering ──────────────────────────────────────────────────────────

def sort_pieces_by_reading_order(pieces):
    valid = [(p.centroid.y, p.centroid.x, p) for p in pieces if p is not None]
    valid.sort()
    return [p for (_, _, p) in valid]


# ─── Size-matched assignment ──────────────────────────────────────────────────

def assign_stickers_to_pieces(sorted_pieces, stickers):
    """
    Rank pieces descending by area, rank stickers descending by visual_weight_px.
    Assign rank-i sticker to rank-i piece.
    Returns: list of length 32, where entry[i] = sticker original number for piece i.
             (piece i is sorted_pieces[i])
    """
    # Enumerate pieces with their original index (position in sorted_pieces)
    piece_with_area = [(i, p.area) for i, p in enumerate(sorted_pieces) if p is not None]
    # Sort descending by area
    piece_with_area.sort(key=lambda x: -x[1])

    # Sort stickers descending by visual_weight_px
    sticker_ranked = sorted(stickers.keys(), key=lambda n: -stickers[n]['visual_weight_px'])

    # Build assignment: piece_original_index -> sticker_number
    piece_to_sticker = {}
    for rank, (piece_idx, piece_area) in enumerate(piece_with_area):
        sticker_num = sticker_ranked[rank]
        piece_to_sticker[piece_idx] = sticker_num

    return piece_to_sticker


# ─── Fit verification ─────────────────────────────────────────────────────────

def compute_inscribed_diameter(piece):
    """
    Approximate inscribed circle diameter.
    Uses 2*sqrt(area/pi) as default; tries shapely's representative_point-based fallback.
    """
    area = piece.area
    approx_r = math.sqrt(area / math.pi)
    return 2 * approx_r


def verify_fit(sorted_pieces, piece_to_sticker, stickers, total_area):
    """
    For each piece, compare inscribed diameter vs sticker bbox diagonal.
    Logs and returns misfit list.
    """
    print("\n[FIT VERIFICATION]")
    print(f"  {'Piece':>5}  {'Area':>8}  {'Inscribed~':>10}  {'Sticker':>3}  "
          f"{'bbox_diag':>9}  {'Fits?':>6}")
    print("  " + "-" * 55)

    misfits = []
    sil_area = total_area
    small_threshold = sil_area * 0.005  # 0.5% of silhouette = "very small piece"

    for piece_idx, piece in enumerate(sorted_pieces):
        if piece is None:
            continue
        sticker_num = piece_to_sticker.get(piece_idx)
        if sticker_num is None:
            continue

        inscribed_d = compute_inscribed_diameter(piece)
        sticker_info = stickers[sticker_num]
        bbox_diag = sticker_info['bbox_diag']

        # Effective target size for sticker render: GHOST_FIT_FACTOR * inscribed_d
        available_d = inscribed_d * GHOST_FIT_FACTOR
        fits = available_d >= bbox_diag

        mark = "OK" if fits else "MISFIT"
        print(f"  {piece_idx+1:>5}  {piece.area:>8.0f}  {inscribed_d:>10.1f}  "
              f"#{sticker_num:>2}  {bbox_diag:>9.1f}  {mark:>6}")

        if not fits:
            misfits.append({
                'piece_idx': piece_idx,
                'piece_area': piece.area,
                'inscribed_d': inscribed_d,
                'sticker_num': sticker_num,
                'bbox_diag': bbox_diag,
            })

    print(f"\n  Total misfits: {len(misfits)}")
    return misfits


# ─── Rendering helpers ────────────────────────────────────────────────────────

def poly_to_pil(geom):
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


def make_ghost_sticker(sticker_img, sticker_info, target_diameter):
    """
    Scale sticker so its content bounding box fits within target_diameter.
    Apply 25% alpha (ghost effect).
    Returns PIL RGBA image.
    """
    bbox = sticker_info['bbox']  # left, top, right, bottom of content
    bw = bbox[2] - bbox[0] + 1
    bh = bbox[3] - bbox[1] + 1

    # Compute scale to fit content within target_diameter circle
    content_diag = math.sqrt(bw**2 + bh**2)
    if content_diag < 1:
        return None

    scale = target_diameter / content_diag
    new_w = max(1, int(bw * scale))
    new_h = max(1, int(bh * scale))

    # Crop to content bbox first
    content = sticker_img.crop((bbox[0], bbox[1], bbox[2] + 1, bbox[3] + 1))
    resized = content.resize((new_w, new_h), Image.LANCZOS)

    # Apply 25% alpha
    arr = np.array(resized).astype(np.float32)
    arr[:, :, 3] = arr[:, :, 3] * 0.25
    ghost = Image.fromarray(arr.astype(np.uint8), 'RGBA')
    return ghost


def paste_ghost_sticker(canvas, piece, sticker_info, total_area):
    """
    Paste ghost sticker centered on piece centroid, scaled to GHOST_FIT_FACTOR * inscribed_d.
    Badge offset: move centroid up by badge_r + small margin so badge doesn't overlap sticker.
    """
    inscribed_d = compute_inscribed_diameter(piece)
    target_d = inscribed_d * GHOST_FIT_FACTOR

    ghost = make_ghost_sticker(sticker_info['img'], sticker_info, target_d)
    if ghost is None:
        return

    cx = int(piece.centroid.x)
    cy = int(piece.centroid.y)

    # Center ghost on centroid
    px = cx - ghost.width // 2
    py = cy - ghost.height // 2

    # Paste with alpha channel as mask
    canvas.paste(ghost, (px, py), ghost)


def draw_number_badge(draw, cx, cy, sticker_num, cat, font_num, piece_area, total_area):
    """
    Draw number badge at centroid.
    Small pieces (< 0.5% of silhouette) get 28px badge, others get 38px.
    """
    sil_threshold = total_area * 0.005
    if piece_area < sil_threshold:
        badge_r = 14
    else:
        badge_r = 19

    bx, by = int(cx), int(cy)
    bx = max(badge_r + 2, min(A4_W - badge_r - 2, bx))
    by = max(badge_r + 2, min(A4_H - badge_r - 2, by))

    draw.ellipse([bx - badge_r, by - badge_r, bx + badge_r, by + badge_r],
                 fill=(255, 255, 255), outline=CATS[cat], width=2)
    ns = str(sticker_num)
    nw, nh = text_size(draw, ns, font_num)
    draw.text((bx - nw // 2, by - nh // 2), ns,
              fill=PIECE_STROKE_INNER, font=font_num)


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
    }


# ─── Page chrome ─────────────────────────────────────────────────────────────

def draw_header(canvas):
    draw = ImageDraw.Draw(canvas)
    f_title = load_font(48, bold=True)
    f_sub   = load_font(28, bold=True)

    title = "Merlion Puzzle — My Singapore Stories"
    tw, _ = text_size(draw, title, f_title)
    draw.text(((A4_W - tw) // 2, 20), title, fill=(25, 55, 115), font=f_title)

    sub = "Big stickers go to big pieces! Match the number."
    sw, _ = text_size(draw, sub, f_sub)
    draw.text(((A4_W - sw) // 2, 82), sub, fill=(200, 65, 45), font=f_sub)


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
    print("Merlion Puzzle A4 Generator v9 — Size-Matched Sticker Assignment")
    print("=" * 65)

    # 1. Load and measure stickers
    print("\n[1] Loading stickers from icons directory...")
    stickers = load_stickers(ICONS_DIR)
    stickers = measure_stickers(stickers)

    # 2. Parse silhouette
    print("\n[2] Parsing SVG silhouette...")
    raw_pts = parse_svg_polygon(SVG_PATH)
    print(f"    {len(raw_pts)} polygon vertices")
    canvas_pts = scale_points_to_canvas(raw_pts, SCALE, MERL_X, MERL_Y)
    sil_poly = Polygon(canvas_pts)
    if not sil_poly.is_valid:
        sil_poly = sil_poly.buffer(0)
    total_area = sil_poly.area
    print(f"    Silhouette area: {total_area:.0f} px^2")
    print(f"    Bounds: {tuple(f'{v:.1f}' for v in sil_poly.bounds)}")

    # 3. Split into body and tail
    print("\n[3] Splitting silhouette into body + tail regions...")
    body_poly, tail_poly = split_body_tail(sil_poly)

    body_area = body_poly.area
    tail_area = tail_poly.area
    body_pct  = body_area / total_area * 100
    tail_pct  = tail_area / total_area * 100

    print(f"\n  Body area: {body_area:.0f} px^2 ({body_pct:.1f}%)")
    print(f"  Tail area: {tail_area:.0f} px^2 ({tail_pct:.1f}%)")

    # 4. Allocate pieces proportional to area
    n_tail = max(2, round(N_PIECES * tail_area / total_area))
    n_body = N_PIECES - n_tail

    print(f"\n[4] Piece allocation:")
    print(f"    Body: {n_body} pieces  Tail: {n_tail} pieces  Total: {n_body + n_tail}")

    # 5. Tessellate
    print("\n[5] Tessellating body region...")
    rng = random.Random(RNG_SEED)
    body_pieces = tessellate_region(body_poly, n_body, rng, label="BODY")
    print(f"    Body pieces generated: {len(body_pieces)}")

    print("\n[6] Tessellating tail region...")
    tail_pieces = tessellate_region(tail_poly, n_tail, rng, label="TAIL")
    print(f"    Tail pieces generated: {len(tail_pieces)}")

    # 6. Combine and sort
    print("\n[7] Combining and sorting pieces...")
    sorted_body = sort_pieces_by_reading_order(body_pieces)
    sorted_tail = sort_pieces_by_reading_order(tail_pieces)
    sorted_pieces = sorted_body + sorted_tail
    piece_count = len(sorted_pieces)
    print(f"    Total pieces: {piece_count}")

    if piece_count != 32:
        print(f"  WARNING: Expected 32 pieces, got {piece_count}")

    # 7. Coverage check
    all_union = unary_union([p for p in sorted_pieces if p is not None])
    covered  = all_union.area
    coverage = covered / total_area * 100
    gap      = total_area - covered
    print(f"\n[8] Coverage: {coverage:.2f}%  (gap = {gap:.1f} px^2)")

    # 8. Print piece area measurements
    print("\n[PIECE AREAS]")
    print(f"  {'Idx':>4}  {'Area (px^2)':>12}  {'% of sil':>9}")
    print("  " + "-" * 32)
    all_areas = []
    for i, p in enumerate(sorted_pieces):
        a = p.area
        all_areas.append(a)
        print(f"  {i+1:>4}  {a:>12.0f}  {a/total_area*100:>9.2f}%")
    arr_areas = np.array(all_areas)
    print(f"\n  Min: {arr_areas.min():.0f}  Max: {arr_areas.max():.0f}  "
          f"Mean: {arr_areas.mean():.0f}  StdDev: {arr_areas.std():.0f}")

    # 9. Assign stickers to pieces by size rank
    print("\n[9] Assigning stickers to pieces by size rank...")
    piece_to_sticker = assign_stickers_to_pieces(sorted_pieces, stickers)

    # Print assignment sample
    print("\n[ASSIGNMENT — sorted by piece area descending]")
    print(f"  {'Rank':>5}  {'Piece#':>6}  {'PieceArea':>10}  {'StickerN':>8}  {'StickerName':<30}  {'StickerWeight':>13}")
    print("  " + "-" * 80)
    piece_area_rank = sorted(
        [(i, p.area) for i, p in enumerate(sorted_pieces)],
        key=lambda x: -x[1]
    )
    for rank, (piece_idx, area) in enumerate(piece_area_rank):
        sn = piece_to_sticker.get(piece_idx, '?')
        sinfo = stickers.get(sn, {})
        sname = sinfo.get('name', '?')
        sw = sinfo.get('visual_weight_px', 0)
        print(f"  {rank+1:>5}  {piece_idx+1:>6}  {area:>10.0f}  #{sn:>7}  {sname:<30}  {sw:>13,}")

    # 10. Fit verification
    misfits = verify_fit(sorted_pieces, piece_to_sticker, stickers, total_area)

    # 11. Render
    print("\n[10] Rendering canvas...")
    canvas = Image.new("RGBA", (A4_W, A4_H), BG_COLOR + (255,))
    draw_header(canvas)

    draw = ImageDraw.Draw(canvas, "RGBA")

    # Fill all pieces
    for i, piece in enumerate(sorted_pieces):
        sticker_num = piece_to_sticker.get(i, i + 1)
        cat = cat_for_sticker_num(sticker_num)
        fill = CAT_PASTEL[cat]
        draw_piece_fill(draw, piece, fill)

    # Interior borders
    for piece in sorted_pieces:
        draw_piece_border(draw, piece, PIECE_STROKE_INNER, 2)

    # Silhouette outline
    sil_coords = [(int(x), int(y)) for x, y in sil_poly.exterior.coords]
    if len(sil_coords) >= 2:
        draw.line(sil_coords + [sil_coords[0]], fill=PIECE_STROKE_OUTER, width=3)

    # Ghost sticker previews
    for i, piece in enumerate(sorted_pieces):
        sticker_num = piece_to_sticker.get(i)
        if sticker_num is None:
            continue
        paste_ghost_sticker(canvas, piece, stickers[sticker_num], total_area)

    # Number badges (on top of ghost stickers)
    font_num = load_font(16, bold=True)
    for i, piece in enumerate(sorted_pieces):
        sticker_num = piece_to_sticker.get(i, i + 1)
        cat = cat_for_sticker_num(sticker_num)
        cx, cy = piece.centroid.x, piece.centroid.y
        draw_number_badge(draw, cx, cy, sticker_num, cat, font_num, piece.area, total_area)

    draw_legend(canvas)
    draw_footer(canvas)

    # Convert to RGB for saving
    rgb_canvas = canvas.convert("RGB")
    rgb_canvas.save(OUTPUT_PATH, "PNG", dpi=(150, 150))
    print(f"\n    Saved: {OUTPUT_PATH}")

    # 12. Final summary
    print("\n" + "=" * 65)
    print(f"DONE: v9 size-matched sticker assignment complete")
    print(f"FILES: {OUTPUT_PATH}")
    print(f"PIECE COUNT: {piece_count}/32")
    print(f"COVERAGE: {coverage:.2f}% (gap={gap:.1f}px^2)")
    print(f"PIECE AREAS: min={arr_areas.min():.0f} / max={arr_areas.max():.0f} / "
          f"mean={arr_areas.mean():.0f} / stdev={arr_areas.std():.0f}")
    weights = [stickers[n]['visual_weight_px'] for n in stickers]
    print(f"STICKER WEIGHTS: min={min(weights):,} / max={max(weights):,} / mean={int(np.mean(weights)):,}")
    print(f"MISFITS: {len(misfits)}")
    if misfits:
        for mf in misfits:
            print(f"  MISFIT: piece #{mf['piece_idx']+1} (area={mf['piece_area']:.0f}, "
                  f"inscribed~{mf['inscribed_d']:.1f}) <- sticker #{mf['sticker_num']} "
                  f"(bbox_diag={mf['bbox_diag']:.1f})")
    print("=" * 65)

    return piece_count


if __name__ == "__main__":
    main()
