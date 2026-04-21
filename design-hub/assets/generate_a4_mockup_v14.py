"""
generate_a4_mockup_v14.py
Merlion Puzzle A4 — v14: UNIFORM sticker size, position-only relaxation.

Fixes from v13:
- v13 sized each sticker to its Voronoi cell's inscribed circle → big cells = big stickers,
  small cells = small stickers → non-uniform baked-in text sizes.
- v14 binary-searches for the LARGEST single uniform S (longest-side pixels) such that ALL
  32 stickers fit inside the silhouette with ZERO pairwise bbox overlaps.
- Position-only relaxation: if overlaps or escapes occur at trial S, push centers apart /
  inward (size stays fixed).
- All 32 stickers rendered at IDENTICAL S. Text sizes are visually uniform.

Algorithm:
  1. Setup: same as v13. 1240x1754 canvas, silhouette 1100px wide, Lloyd's-relaxed 32 points.
  2. Binary search over S in [60, 180]:
     - Scale every sticker so longest side = S.
     - Place at Lloyd's centers.
     - Check: (a) no bbox overlaps, (b) all bboxes inside silhouette.
     - Pass → try larger. Fail → run position relaxation (up to 50 passes), re-check.
     - If still fail after relaxation → try smaller S.
  3. Position relaxation:
     - For each overlapping pair: push BOTH centers apart by (overlap/2 + 2px).
     - For each escaping sticker: shift center 8px toward silhouette centroid.
     - Up to 50 passes.
  4. Target S >= 90. If max feasible S < 90 → log WARNING but proceed.
  5. Verification: log every sticker's display_size=S. Abort if any differs by >1px.
  6. Rendering: same as v13 — paste labeled stickers, 2px grey outline, Phase 3 text.
"""

import os
import re
import math
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

try:
    from shapely.geometry import Polygon, Point, MultiPolygon, box as shapely_box
    from shapely.prepared import prep
    SHAPELY = True
except ImportError:
    SHAPELY = False
    raise RuntimeError("shapely required: pip install shapely")

try:
    from scipy.spatial import Voronoi
    SCIPY = True
except ImportError:
    SCIPY = False
    raise RuntimeError("scipy required: pip install scipy")

# ─── Paths ────────────────────────────────────────────────────────────────────

BASE_DIR         = Path(r"C:/Users/Admin/Projects/oinio/littledotbook/design-hub/assets")
SVG_PATH         = BASE_DIR / "merlion-silhouette.svg"
LABELED_CROP_DIR = BASE_DIR / "icons" / "labeled-cropped"
OUTPUT_PATH      = BASE_DIR / "merlion-puzzle-a4-v14.png"

# ─── Canvas ───────────────────────────────────────────────────────────────────

A4_W, A4_H      = 1240, 1754
BG_COLOR        = (250, 247, 240)   # cream #FAF7F0
HEADER_H        = 100               # top margin for title/subtitle/instruction
FOOTER_H        = 80                # bottom margin
MERL_W_TARGET   = 1100
SVG_VW, SVG_VH  = 600, 800

# ─── Lloyd's parameters ───────────────────────────────────────────────────────

N_STICKERS  = 32
LLOYD_ITERS = 10

# ─── Binary search range ─────────────────────────────────────────────────────

S_MIN = 60
S_MAX = 180
S_TARGET_FLOOR = 90      # warn if best S < this
MAX_RELAX_PASSES = 50    # max position relaxation iterations per trial S

# ─── Colours ─────────────────────────────────────────────────────────────────

SIL_OUTLINE_COLOR = (207, 203, 192)   # #CFCBC0

# ─── Filename map ─────────────────────────────────────────────────────────────

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


# ─── Fonts ────────────────────────────────────────────────────────────────────

def load_font(size, bold=False):
    """Load font from Windows Fonts — Arial Bold primary, fallbacks to calibri/segoe."""
    candidates = (
        ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/calibrib.ttf",
         "C:/Windows/Fonts/segoeuib.ttf"]
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


# ─── STEP 1: Load crop sizes from existing labeled-cropped stickers ───────────

def load_crop_sizes():
    """
    Load aspect ratios from the already-generated labeled-cropped PNGs.
    Returns {sid: (w, h)} for all 32 stickers.
    """
    print("\n[STEP 1] Loading labeled-cropped sticker sizes...")
    crop_sizes = {}
    missing = []

    for sid in range(1, N_STICKERS + 1):
        fname = FILENAME_MAP.get(sid)
        if not fname:
            missing.append(sid)
            continue
        p = LABELED_CROP_DIR / fname
        if not p.exists():
            print(f"  WARN #{sid}: labeled-cropped not found: {p}")
            missing.append(sid)
            crop_sizes[sid] = (100, 100)
            continue
        try:
            img = Image.open(str(p))
            w, h = img.size
            crop_sizes[sid] = (w, h)
            print(f"  #{sid:2d} {fname}: {w}x{h} px  (aspect {w/h:.3f})")
        except Exception as e:
            print(f"  WARN #{sid}: failed to read size: {e}")
            crop_sizes[sid] = (100, 100)
            missing.append(sid)

    print(f"  Loaded {len(crop_sizes) - len(missing)}/32 sizes. Missing: {missing or 'none'}")
    return crop_sizes


# ─── STEP 2: Parse SVG silhouette ────────────────────────────────────────────

def parse_svg_polygon(svg_file: Path):
    content = svg_file.read_text(encoding="utf-8")
    m = re.search(r'\bd="(M[^"]+)"', content, re.DOTALL)
    if not m:
        m2 = re.search(r'points="([^"]+)"', content)
        if m2:
            raw = m2.group(1).strip()
            pairs = re.findall(r'([-\d.]+)[,\s]+([-\d.]+)', raw)
            return [(float(x), float(y)) for x, y in pairs]
        raise ValueError("No SVG path 'd' or polygon 'points' found in SVG")
    d = m.group(1)
    coord_pairs = re.findall(r'[-\d.]+,[-\d.]+', d)
    points = []
    for pair in coord_pairs:
        parts = pair.split(',')
        points.append((float(parts[0]), float(parts[1])))
    return points


def build_canvas_silhouette(raw_pts):
    scale = MERL_W_TARGET / SVG_VW
    tx = (A4_W - MERL_W_TARGET) // 2
    ty = HEADER_H + 10

    canvas_pts = [(x * scale + tx, y * scale + ty) for (x, y) in raw_pts]
    sil_poly = Polygon(canvas_pts)
    if not sil_poly.is_valid:
        sil_poly = sil_poly.buffer(0)

    return canvas_pts, scale, tx, ty, sil_poly


# ─── STEP 3: Seed 32 points inside silhouette ────────────────────────────────

def seed_points_inside(sil_poly, n=N_STICKERS):
    prepared = prep(sil_poly)
    bounds = sil_poly.bounds
    minx, miny, maxx, maxy = bounds

    def grid_points(rows, cols):
        pts = []
        for r in range(rows):
            for c in range(cols):
                x = minx + (maxx - minx) * (c + 0.5) / cols
                y = miny + (maxy - miny) * (r + 0.5) / rows
                if prepared.contains(Point(x, y)):
                    pts.append([x, y])
        return pts

    for rows in range(8, 40):
        pts = grid_points(rows, rows)
        if len(pts) >= n:
            if len(pts) == n:
                return np.array(pts)
            step = len(pts) / n
            indices = [int(i * step) for i in range(n)]
            return np.array([pts[i] for i in indices])

    rng = np.random.default_rng(42)
    pts = []
    attempts = 0
    while len(pts) < n and attempts < 100000:
        x = rng.uniform(minx, maxx)
        y = rng.uniform(miny, maxy)
        if prepared.contains(Point(x, y)):
            pts.append([x, y])
        attempts += 1

    if len(pts) < n:
        raise RuntimeError(f"Could not seed {n} points inside silhouette (got {len(pts)})")
    return np.array(pts[:n])


# ─── STEP 4: Lloyd's Relaxation + Voronoi cells ──────────────────────────────

def make_voronoi_cells(points, sil_poly):
    bounds = sil_poly.bounds
    minx, miny, maxx, maxy = bounds
    pad = max(maxx - minx, maxy - miny) * 1.5

    mirror = np.array([
        [minx - pad, miny - pad], [maxx + pad, miny - pad],
        [minx - pad, maxy + pad], [maxx + pad, maxy + pad],
        [(minx + maxx) / 2, miny - pad], [(minx + maxx) / 2, maxy + pad],
        [minx - pad, (miny + maxy) / 2], [maxx + pad, (miny + maxy) / 2],
    ])

    all_pts = np.vstack([points, mirror])
    vor = Voronoi(all_pts)
    prepared = prep(sil_poly)
    cells = []

    for i in range(len(points)):
        region_idx = vor.point_region[i]
        region = vor.regions[region_idx]

        if -1 in region or len(region) == 0:
            cell = shapely_box(minx - pad, miny - pad, maxx + pad, maxy + pad)
        else:
            verts = [vor.vertices[v] for v in region]
            if len(verts) < 3:
                cell = shapely_box(minx - pad, miny - pad, maxx + pad, maxy + pad)
            else:
                cell = Polygon(verts)
                if not cell.is_valid:
                    cell = cell.buffer(0)

        try:
            clipped = cell.intersection(sil_poly)
        except Exception:
            clipped = sil_poly

        if clipped.is_empty:
            clipped = Point(points[i]).buffer(5)

        if hasattr(clipped, 'geoms'):
            best = max(clipped.geoms, key=lambda g: g.area)
            clipped = best

        centroid = clipped.centroid
        cells.append((clipped, (centroid.x, centroid.y), clipped.area))

    return cells


def lloyds_relaxation(initial_pts, sil_poly, iters=LLOYD_ITERS):
    prepared = prep(sil_poly)
    pts = initial_pts.copy()

    for iteration in range(iters):
        cells = make_voronoi_cells(pts, sil_poly)
        new_pts = []
        for i, (cell, (cx, cy), area) in enumerate(cells):
            if prepared.contains(Point(cx, cy)):
                new_pts.append([cx, cy])
            else:
                ox, oy = pts[i]
                mx, my = (ox + cx) / 2, (oy + cy) / 2
                if prepared.contains(Point(mx, my)):
                    new_pts.append([mx, my])
                else:
                    new_pts.append([ox, oy])
        pts = np.array(new_pts)
        avg_move = np.mean(np.linalg.norm(pts - initial_pts, axis=1))
        print(f"  Lloyd iter {iteration + 1}/{iters}: avg displacement {avg_move:.1f}px")

    cells = make_voronoi_cells(pts, sil_poly)
    return pts, cells


# ─── STEP 5 (v14): Compute per-sticker display dims given uniform S ───────────

def compute_sticker_dims(S, crop_sizes):
    """
    Given uniform S (longest side in pixels), compute (paste_w, paste_h) for each sticker.
    Returns {sid: (paste_w, paste_h)}.
    """
    dims = {}
    for sid in range(1, N_STICKERS + 1):
        cw, ch = crop_sizes.get(sid, (100, 100))
        if cw >= ch:
            paste_w = float(S)
            paste_h = S * ch / cw
        else:
            paste_h = float(S)
            paste_w = S * cw / ch
        dims[sid] = (paste_w, paste_h)
    return dims


# ─── STEP 6 (v14): Check overlaps and escapes ─────────────────────────────────

def rects_overlap(a_cx, a_cy, a_w, a_h, b_cx, b_cy, b_w, b_h):
    """Returns (True, x_depth, y_depth) if overlapping, else (False, 0, 0)."""
    ax0 = a_cx - a_w / 2; ax1 = a_cx + a_w / 2
    ay0 = a_cy - a_h / 2; ay1 = a_cy + a_h / 2
    bx0 = b_cx - b_w / 2; bx1 = b_cx + b_w / 2
    by0 = b_cy - b_h / 2; by1 = b_cy + b_h / 2

    x_overlap = min(ax1, bx1) - max(ax0, bx0)
    y_overlap = min(ay1, by1) - max(ay0, by0)

    if x_overlap > 0 and y_overlap > 0:
        return True, x_overlap, y_overlap
    return False, 0.0, 0.0


def sticker_bbox_inside_silhouette(cx, cy, w, h, sil_poly):
    """
    Check if the sticker's bounding box is fully inside the silhouette polygon.
    Returns True if all 4 corners are within the silhouette.
    """
    corners = [
        (cx - w/2, cy - h/2),
        (cx + w/2, cy - h/2),
        (cx - w/2, cy + h/2),
        (cx + w/2, cy + h/2),
    ]
    for (px, py) in corners:
        if not sil_poly.contains(Point(px, py)):
            return False
    return True


def count_conflicts(centers, dims, sil_poly, n=N_STICKERS):
    """
    Returns (overlap_count, escape_count) for all stickers at given centers/dims.
    centers: list of [cx, cy] indexed 0..N-1, sticker id = idx+1
    dims: {sid: (paste_w, paste_h)}
    """
    overlaps = 0
    escapes = 0

    for i in range(n):
        sid_i = i + 1
        cx_i, cy_i = centers[i]
        w_i, h_i = dims[sid_i]
        if not sticker_bbox_inside_silhouette(cx_i, cy_i, w_i, h_i, sil_poly):
            escapes += 1

    for i in range(n):
        for j in range(i + 1, n):
            sid_i, sid_j = i + 1, j + 1
            cx_i, cy_i = centers[i]
            cx_j, cy_j = centers[j]
            w_i, h_i = dims[sid_i]
            w_j, h_j = dims[sid_j]
            ok, _, _ = rects_overlap(cx_i, cy_i, w_i, h_i, cx_j, cy_j, w_j, h_j)
            if ok:
                overlaps += 1

    return overlaps, escapes


# ─── STEP 7 (v14): Position-only relaxation ───────────────────────────────────

def position_relax(centers_in, dims, sil_poly, max_passes=MAX_RELAX_PASSES):
    """
    Push centers apart to resolve overlaps; shift inward to resolve escapes.
    Size (dims) is FIXED throughout.
    Returns (new_centers, final_overlaps, final_escapes, passes_used).
    """
    centers = [list(c) for c in centers_in]  # mutable copy
    centroid = sil_poly.centroid
    cx_sil, cy_sil = centroid.x, centroid.y
    n = N_STICKERS

    for pass_num in range(1, max_passes + 1):
        changed = False

        # --- Resolve overlaps: push apart ---
        for i in range(n):
            for j in range(i + 1, n):
                sid_i, sid_j = i + 1, j + 1
                cx_i, cy_i = centers[i]
                cx_j, cy_j = centers[j]
                w_i, h_i = dims[sid_i]
                w_j, h_j = dims[sid_j]

                ok, x_depth, y_depth = rects_overlap(
                    cx_i, cy_i, w_i, h_i,
                    cx_j, cy_j, w_j, h_j
                )
                if ok:
                    # Push apart along the overlap vector (center to center)
                    dx = cx_j - cx_i
                    dy = cy_j - cy_i
                    dist = math.sqrt(dx * dx + dy * dy)
                    if dist < 1e-6:
                        # Degenerate: push in a fixed direction
                        dx, dy, dist = 1.0, 0.0, 1.0

                    # Minimum push needed: overlap depth + 2px margin each side
                    overlap_depth = min(x_depth, y_depth)
                    push = (overlap_depth / 2) + 2.0
                    push_x = (dx / dist) * push
                    push_y = (dy / dist) * push

                    centers[i][0] -= push_x
                    centers[i][1] -= push_y
                    centers[j][0] += push_x
                    centers[j][1] += push_y
                    changed = True

        # --- Resolve escapes: shift inward ---
        for i in range(n):
            sid = i + 1
            cx, cy = centers[i]
            w, h = dims[sid]
            if not sticker_bbox_inside_silhouette(cx, cy, w, h, sil_poly):
                dx = cx_sil - cx
                dy = cy_sil - cy
                dist = math.sqrt(dx * dx + dy * dy)
                if dist > 0:
                    centers[i][0] += (dx / dist) * 8
                    centers[i][1] += (dy / dist) * 8
                changed = True

        overlaps, escapes = count_conflicts(centers, dims, sil_poly)

        if overlaps == 0 and escapes == 0:
            return centers, 0, 0, pass_num

    # Final check after max_passes
    overlaps, escapes = count_conflicts(centers, dims, sil_poly)
    return centers, overlaps, escapes, max_passes


# ─── STEP 8 (v14): Binary search for max uniform S ───────────────────────────

def binary_search_uniform_s(lloyd_centers, crop_sizes, sil_poly):
    """
    Binary search over S in [S_MIN, S_MAX] to find the largest S where all 32 stickers
    fit inside silhouette with zero pairwise bbox overlaps.

    Returns:
      best_S: int — the max feasible S
      best_centers: list of [cx, cy] — relaxed centers at best_S
      best_dims: {sid: (paste_w, paste_h)} — dims at best_S
      relax_passes_used: int — relaxation passes used at best_S
    """
    print(f"\n[STEP 5] Binary search for uniform S in [{S_MIN}, {S_MAX}]...")

    lo, hi = S_MIN, S_MAX
    best_S = None
    best_centers = None
    best_dims = None
    best_passes = 0

    initial_centers = [list(lloyd_centers[i]) for i in range(N_STICKERS)]

    while lo <= hi:
        mid = (lo + hi) // 2
        dims = compute_sticker_dims(mid, crop_sizes)

        # Try at current Lloyd centers first
        overlaps, escapes = count_conflicts(initial_centers, dims, sil_poly)

        if overlaps == 0 and escapes == 0:
            # Fits at Lloyd centers with no relaxation needed
            relaxed_centers = [list(c) for c in initial_centers]
            passes_used = 0
            feasible = True
        else:
            # Try position relaxation
            relaxed_centers, final_overlaps, final_escapes, passes_used = \
                position_relax(initial_centers, dims, sil_poly)
            feasible = (final_overlaps == 0 and final_escapes == 0)

        status = "PASS" if feasible else "FAIL"
        print(f"  S={mid:4d}: {status}  (overlaps={overlaps}->{'0' if feasible else '?'}, "
              f"escapes={escapes}->{'0' if feasible else '?'}, relax_passes={passes_used})")

        if feasible:
            best_S = mid
            best_centers = relaxed_centers
            best_dims = dims
            best_passes = passes_used
            lo = mid + 1
        else:
            hi = mid - 1

    return best_S, best_centers, best_dims, best_passes


# ─── STEP 9 (v14): Uniform size verification ──────────────────────────────────

def verify_uniform_sizes(best_S, best_dims):
    """
    For each sticker, compute its longest rendered side and verify it equals best_S.
    Abort if any sticker's longest side differs from best_S by more than 1px.
    """
    print(f"\n[VERIFICATION] Uniform size check — target S={best_S}px")
    print(f"  All 32 stickers must have longest_side == {best_S}px (within 1px tolerance)")

    violations = []
    for sid in range(1, N_STICKERS + 1):
        paste_w, paste_h = best_dims[sid]
        longest_side = max(paste_w, paste_h)
        diff = abs(longest_side - best_S)
        status = "OK" if diff <= 1.0 else "MISMATCH"
        fname = FILENAME_MAP.get(sid, "?")
        print(f"  sticker {sid:2d} {fname.replace('.png',''):30s}: "
              f"display_size={longest_side:.1f}px (confirmed identical across all 32)  [{status}]")
        if diff > 1.0:
            violations.append((sid, longest_side))

    if violations:
        print(f"\nALERT: {len(violations)} sticker(s) have display_size != {best_S}px by >1px:")
        for (sid, ds) in violations:
            print(f"  ALERT: sticker {sid} has display_size={ds:.1f}px, expected {best_S}px")
        raise RuntimeError(
            f"ABORT: uniform size verification FAILED for {len(violations)} sticker(s)"
        )

    print(f"  All 32 stickers verified at uniform S={best_S}px.")


# ─── STEP 10: Render ──────────────────────────────────────────────────────────

def load_labeled_cropped(sid):
    fname = FILENAME_MAP.get(sid)
    if not fname:
        return None
    p = LABELED_CROP_DIR / fname
    if not p.exists():
        return None
    try:
        return Image.open(str(p)).convert("RGBA")
    except Exception as e:
        print(f"  WARN: failed to load labeled-cropped #{sid}: {e}")
        return None


def draw_silhouette_outline(draw, canvas_pts, color=SIL_OUTLINE_COLOR, width=2):
    coords = [(int(x), int(y)) for x, y in canvas_pts]
    draw.line(coords + [coords[0]], fill=color, width=width)


def render_stickers(canvas, best_centers, best_dims, canvas_pts):
    """Render all 32 stickers at uniform size. Returns total sticker area."""
    draw = ImageDraw.Draw(canvas, "RGBA")
    total_area = 0

    for i in range(N_STICKERS):
        sid = i + 1
        cx, cy = best_centers[i]
        paste_w, paste_h = best_dims[sid]

        img = load_labeled_cropped(sid)
        if img is None:
            print(f"  WARN: labeled-cropped sticker #{sid} not found — skipping")
            continue

        w_i = max(1, int(round(paste_w)))
        h_i = max(1, int(round(paste_h)))
        resized = img.resize((w_i, h_i), Image.LANCZOS)
        px = int(round(cx - w_i / 2))
        py = int(round(cy - h_i / 2))

        canvas.paste(resized, (px, py), resized)
        total_area += w_i * h_i

    # 2px silhouette outline on top
    draw_silhouette_outline(draw, canvas_pts)

    return total_area


# ─── STEP 11: Page chrome (Phase 3 styling from v3/v13) ──────────────────────

def draw_page_chrome(canvas):
    draw = ImageDraw.Draw(canvas)

    f_title  = load_font(52, bold=True)
    f_sub    = load_font(34)
    f_instr  = load_font(25)
    f_footer = load_font(19)

    # Title
    title = "My Singapore Stories Vol.2"
    tw, th = text_size(draw, title, f_title)
    draw.text(((A4_W - tw) // 2, 22), title, fill=(25, 55, 115), font=f_title)

    # Subtitle
    sub = "The Merlion Puzzle"
    sw, sh = text_size(draw, sub, f_sub)
    draw.text(((A4_W - sw) // 2, 22 + th + 6), sub, fill=(215, 75, 55), font=f_sub)

    # Instruction
    instr = "Match each sticker to its place on the Merlion!"
    iw, ih = text_size(draw, instr, f_instr)
    draw.text(((A4_W - iw) // 2, 22 + th + 6 + sh + 6), instr, fill=(75, 75, 95), font=f_instr)

    # Footer
    footer = "Little Dot Book  .  My Singapore Stories Vol.2"
    fw, fh = text_size(draw, footer, f_footer)
    draw.text(((A4_W - fw) // 2, A4_H - fh - 20), footer, fill=(155, 155, 175), font=f_footer)


# ─── Utility: coverage quadrant check ────────────────────────────────────────

def coverage_check(best_centers, sil_poly):
    bounds = sil_poly.bounds
    minx, miny, maxx, maxy = bounds
    mid_x = (minx + maxx) / 2
    mid_y = (miny + maxy) / 2

    tl = tr = bl = br = 0
    for i in range(N_STICKERS):
        cx, cy = best_centers[i]
        if cx <= mid_x and cy <= mid_y:
            tl += 1
        elif cx > mid_x and cy <= mid_y:
            tr += 1
        elif cx <= mid_x and cy > mid_y:
            bl += 1
        else:
            br += 1

    print(f"  Quadrant distribution (mid x={mid_x:.0f}, y={mid_y:.0f}):")
    print(f"    TL={tl}  TR={tr}")
    print(f"    BL={bl}  BR={br}")
    print(f"    Total: {tl+tr+bl+br}")
    return tl, tr, bl, br


def log_center_shifts(lloyd_centers, best_centers):
    """Log per-sticker center shift from Lloyd's position to final relaxed position."""
    print("\n[CENTER SHIFTS] Per-sticker displacement from Lloyd's centers:")
    shifts = []
    for i in range(N_STICKERS):
        sid = i + 1
        ox, oy = lloyd_centers[i]
        nx, ny = best_centers[i]
        d = math.sqrt((nx - ox)**2 + (ny - oy)**2)
        shifts.append(d)
        fname = FILENAME_MAP.get(sid, "?")
        print(f"  #{sid:2d} {fname.replace('.png',''):30s}: shift={d:.1f}px")
    print(f"  Avg shift={sum(shifts)/len(shifts):.1f}px  Max shift={max(shifts):.1f}px")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Merlion Puzzle A4 — v14: UNIFORM Sticker Size")
    print("=" * 60)

    # STEP 1: Load crop sizes
    crop_sizes = load_crop_sizes()

    # STEP 2: Parse silhouette
    print("\n[STEP 2] Parsing SVG silhouette...")
    raw_pts = parse_svg_polygon(SVG_PATH)
    print(f"  {len(raw_pts)} polygon vertices parsed")

    canvas_pts, scale, tx, ty, sil_poly = build_canvas_silhouette(raw_pts)
    print(f"  Scale={scale:.4f}, offset=({tx},{ty})")
    print(f"  Silhouette area: {sil_poly.area:.0f} px^2")
    print(f"  Silhouette bounds: {[int(v) for v in sil_poly.bounds]}")

    # STEP 3: Seed 32 points
    print(f"\n[STEP 3] Seeding {N_STICKERS} points inside silhouette...")
    seed_pts = seed_points_inside(sil_poly, n=N_STICKERS)
    print(f"  Seeded {len(seed_pts)} points.")

    # STEP 4: Lloyd's relaxation
    print(f"\n[STEP 4] Running Lloyd's relaxation ({LLOYD_ITERS} iterations)...")
    lloyd_centers_arr, final_cells = lloyds_relaxation(seed_pts, sil_poly, iters=LLOYD_ITERS)
    lloyd_centers = [list(lloyd_centers_arr[i]) for i in range(N_STICKERS)]
    print(f"  {len(final_cells)} Voronoi cells computed.")

    cell_areas = sorted([c[2] for c in final_cells])
    print(f"  Cell area: min={cell_areas[0]:.0f}  max={cell_areas[-1]:.0f}  "
          f"mean={sum(cell_areas)/len(cell_areas):.0f} px^2")

    # STEP 5-7: Binary search for uniform S + position relaxation
    best_S, best_centers, best_dims, relax_passes = binary_search_uniform_s(
        lloyd_centers, crop_sizes, sil_poly
    )

    if best_S is None:
        raise RuntimeError(f"ABORT: no feasible S found in [{S_MIN}, {S_MAX}]")

    print(f"\n  Best uniform S = {best_S}px  (relax_passes at best S = {relax_passes})")

    if best_S < S_TARGET_FLOOR:
        print(f"  WARNING: best S={best_S}px is below target floor of {S_TARGET_FLOOR}px. "
              f"Proceeding as uniform is preferred over dense.")

    # STEP 8: Verify uniform sizes
    verify_uniform_sizes(best_S, best_dims)

    # STEP 9: Final conflict check
    final_overlaps, final_escapes = count_conflicts(best_centers, best_dims, sil_poly)
    print(f"\n[FINAL CHECK] overlaps={final_overlaps}  escapes={final_escapes}")
    if final_overlaps > 0:
        print(f"  ALERT: {final_overlaps} overlaps remain in final check!")
    if final_escapes > 0:
        print(f"  ALERT: {final_escapes} escapes remain in final check!")

    # Log center shifts
    log_center_shifts(lloyd_centers, best_centers)

    # STEP 10: Render
    print(f"\n[STEP 10] Rendering canvas at uniform S={best_S}px...")
    canvas = Image.new("RGB", (A4_W, A4_H), BG_COLOR)
    draw_page_chrome(canvas)
    total_sticker_area = render_stickers(canvas, best_centers, best_dims, canvas_pts)

    # Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(str(OUTPUT_PATH), "PNG", dpi=(150, 150))
    print(f"\n  Saved: {OUTPUT_PATH}")

    # ─── Final stats ─────────────────────────────────────────────────────────
    sil_area = sil_poly.area
    coverage_pct = total_sticker_area / sil_area * 100 if sil_area > 0 else 0

    print(f"\n[COVERAGE]")
    tl, tr, bl, br = coverage_check(best_centers, sil_poly)

    print("\n" + "=" * 60)
    print(f"DONE: {N_STICKERS}/32 stickers placed at UNIFORM S={best_S}px")
    print(f"FILES: {OUTPUT_PATH}")
    print(f"UNIFORM SIZE (S): {best_S}px — same for all 32 stickers")
    print(f"RELAXATION PASSES: {relax_passes}")
    print(f"OVERLAPS FINAL: {final_overlaps}")
    print(f"ESCAPES FINAL: {final_escapes}")
    print(f"COVERAGE: {coverage_pct:.1f}% silhouette area covered")
    print(f"DISTRIBUTION: TL={tl}  TR={tr}  BL={bl}  BR={br}")
    print("=" * 60)


if __name__ == "__main__":
    main()
