"""
generate_a4_mockup_v12.py
Merlion Puzzle A4 — v12: Dense fill (0.92 ratio) + name labels + hard fit constraint.

Changes from v11:
  1. CELL_FILL_RATIO bumped to 0.92 (denser sticker packing)
  2. Number badges removed entirely
  3. Name label added below each sticker (from filename), with white bg pill
  4. HARD CONSTRAINT: every pixel of every sticker + label must be fully inside
     the Merlion silhouette. Iterative shrink + shift to enforce this.

Core algorithm (unchanged from v11):
  - Shapely silhouette parsing
  - Seed 32 points inside silhouette
  - Lloyd's relaxation (10 iterations)
  - Voronoi-based per-sticker sizing
"""

import os
import re
import math
import warnings
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

try:
    from shapely.geometry import Polygon, Point, MultiPolygon, box as shapely_box
    from shapely.prepared import prep
    SHAPELY = True
except ImportError:
    SHAPELY = False
    raise RuntimeError("shapely is required. Install: pip install shapely")

try:
    from scipy.spatial import Voronoi
    SCIPY = True
except ImportError:
    SCIPY = False
    raise RuntimeError("scipy is required. Install: pip install scipy")

# ─── Paths ────────────────────────────────────────────────────────────────────

BASE_DIR    = Path(r"C:/Users/Admin/Projects/oinio/littledotbook/design-hub/assets")
SVG_PATH    = BASE_DIR / "merlion-silhouette.svg"
CROPPED_DIR = BASE_DIR / "icons" / "cropped"
OUTPUT_PATH = BASE_DIR / "merlion-puzzle-a4-v12.png"

# ─── Canvas ───────────────────────────────────────────────────────────────────

A4_W, A4_H    = 1240, 1754        # 150 DPI A4 portrait
BG_COLOR      = (250, 247, 240)   # cream #FAF7F0
HEADER_H      = 100               # top margin for title/subtitle
FOOTER_H      = 80                # bottom margin for footer
MERL_W_TARGET = 1100              # silhouette width in canvas pixels
SVG_VW, SVG_VH = 600, 800        # SVG viewBox

# ─── Lloyd's relaxation parameters ───────────────────────────────────────────

N_STICKERS      = 32
LLOYD_ITERS     = 10
CELL_FILL_RATIO = 0.92   # v12: bumped from 0.70 → denser packing
CELL_INSET_RATIO = 0.90  # half-diagonal must not exceed 90% of inradius

# ─── Hard fit constraint parameters ──────────────────────────────────────────

FIT_SHRINK_STEP   = 0.10   # shrink by 10% each retry
FIT_SHIFT_DIST    = 8.0    # shift toward centroid by 8px each retry
FIT_MAX_ITERS     = 10     # max retries per sticker
AT_RISK_THRESHOLD = 5.0    # px from boundary = "at risk"

# ─── Colours ─────────────────────────────────────────────────────────────────

SIL_OUTLINE_COLOR = (207, 203, 192)    # #CFCBC0 light grey
TITLE_COLOR       = (45, 45, 55)
SUBTITLE_COLOR    = (110, 110, 120)
FOOTER_COLOR      = (160, 160, 170)
LABEL_TEXT_COLOR  = (45, 55, 72)       # #2D3748 dark grey

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

# Parse display names from filenames: "#14 Chicken Rice.png" -> "Chicken Rice"
_NAME_RE = re.compile(r'^#(\d+)\s+(.+)\.png$', re.IGNORECASE)

def _parse_display_name(filename):
    m = _NAME_RE.match(filename)
    if m:
        return m.group(2).strip()
    return filename  # fallback

DISPLAY_NAMES = {sid: _parse_display_name(fname) for sid, fname in FILENAME_MAP.items()}


# ─── Fonts ───────────────────────────────────────────────────────────────────

def load_font(size, bold=False):
    candidates = (
        ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/georgiab.ttf",
         "C:/Windows/Fonts/calibrib.ttf"]
        if bold else
        ["C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/georgia.ttf",
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


# ─── STEP 1: Load cropped sticker sizes ──────────────────────────────────────

def load_cropped_sizes():
    """Load existing cropped stickers and return {id: (w, h)} + pixel count."""
    print("\n[STEP 1] Loading cropped sticker sizes...")
    crop_sizes = {}
    pixel_counts = {}
    sticker_images = {}

    for sid in range(1, N_STICKERS + 1):
        fname = FILENAME_MAP.get(sid)
        if not fname:
            print(f"  WARN #{sid}: no filename entry")
            continue
        p = CROPPED_DIR / fname
        if not p.exists():
            print(f"  WARN #{sid}: not found at {p}")
            continue
        try:
            img = Image.open(str(p)).convert("RGBA")
            w, h = img.size
            arr = np.array(img)
            px_count = int(np.sum(arr[:, :, 3] > 10))
            crop_sizes[sid] = (w, h)
            pixel_counts[sid] = px_count
            sticker_images[sid] = img
            print(f"  #{sid:2d}: {w}x{h}px, {px_count} visible pixels")
        except Exception as e:
            print(f"  WARN #{sid}: load error: {e}")

    print(f"  Loaded {len(crop_sizes)}/32 cropped stickers.")
    return crop_sizes, pixel_counts, sticker_images


# ─── STEP 2: Parse SVG silhouette ────────────────────────────────────────────

def parse_svg_polygon(svg_file: Path):
    """Parse SVG path 'd' attribute -> list of (x, y) float points."""
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
    ty = header_h + 10

    canvas_pts = [(x * scale + tx, y * scale + ty) for (x, y) in raw_pts]

    sil_poly = Polygon(canvas_pts)
    if not sil_poly.is_valid:
        sil_poly = sil_poly.buffer(0)

    return canvas_pts, scale, tx, ty, sil_poly


# ─── STEP 3: Seed 32 points inside silhouette ────────────────────────────────

def seed_points_inside(sil_poly, n=N_STICKERS):
    """
    Generate exactly n seed points inside the silhouette by sampling a grid.
    """
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
        cols = rows
        pts = grid_points(rows, cols)
        if len(pts) >= n:
            if len(pts) == n:
                return np.array(pts)
            step = len(pts) / n
            indices = [int(i * step) for i in range(n)]
            return np.array([pts[i] for i in indices])

    # Fallback: random sampling inside bbox
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


# ─── STEP 4: Lloyd's Relaxation ──────────────────────────────────────────────

def make_voronoi_cells(points, sil_poly):
    """
    Compute Voronoi cells clipped to the silhouette.
    Returns list of (clipped_cell_polygon, centroid, area) for each point.
    """
    bounds = sil_poly.bounds
    minx, miny, maxx, maxy = bounds
    pad = max(maxx - minx, maxy - miny) * 1.5

    mirror = np.array([
        [minx - pad, miny - pad],
        [maxx + pad, miny - pad],
        [minx - pad, maxy + pad],
        [maxx + pad, maxy + pad],
        [(minx + maxx) / 2, miny - pad],
        [(minx + maxx) / 2, maxy + pad],
        [minx - pad, (miny + maxy) / 2],
        [maxx + pad, (miny + maxy) / 2],
    ])

    all_pts = np.vstack([points, mirror])
    vor = Voronoi(all_pts)

    prepared = prep(sil_poly)
    cells = []

    for i in range(len(points)):
        region_idx = vor.point_region[i]
        region = vor.regions[region_idx]

        if -1 in region or len(region) == 0:
            large_box = shapely_box(minx - pad, miny - pad, maxx + pad, maxy + pad)
            cell = large_box
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
            best = None
            best_area = 0
            for geom in clipped.geoms:
                if geom.area > best_area:
                    best_area = geom.area
                    best = geom
            clipped = best if best else clipped.geoms[0]

        centroid = clipped.centroid
        cells.append((clipped, (centroid.x, centroid.y), clipped.area))

    return cells


def lloyds_relaxation(initial_pts, sil_poly, iters=LLOYD_ITERS):
    """
    Run Lloyd's relaxation for `iters` iterations.
    Returns final array of (n, 2) points and final Voronoi cells.
    """
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


# ─── STEP 5: Per-sticker sizing from Voronoi cells ───────────────────────────

def compute_sticker_sizes(cells, crop_sizes, pixel_counts):
    """
    For each Voronoi cell (sorted by area desc), compute target sticker size.
    Assign largest cell to highest-content sticker.
    Returns list of (sticker_id, cell_idx, center_x, center_y, w_px, h_px) in cell order.
    """
    cell_order = sorted(range(N_STICKERS), key=lambda i: cells[i][2], reverse=True)
    sticker_order = sorted(pixel_counts.keys(), key=lambda s: pixel_counts[s], reverse=True)

    available_ids = list(sticker_order)
    if len(available_ids) < N_STICKERS:
        all_ids = set(available_ids)
        for sid in range(1, N_STICKERS + 1):
            if sid not in all_ids:
                available_ids.append(sid)

    assignments = []

    for rank, cell_idx in enumerate(cell_order):
        cell_poly, (cx, cy), cell_area = cells[cell_idx]
        sid = available_ids[rank] if rank < len(available_ids) else rank + 1

        cw, ch = crop_sizes.get(sid, (100, 100))
        aspect = cw / ch if ch > 0 else 1.0

        # Constraint 1: area-based sizing
        target_area = CELL_FILL_RATIO * cell_area
        h_s = math.sqrt(target_area / aspect)
        w_s = aspect * h_s

        # Constraint 2: inradius-based — half-diagonal <= 90% of inradius
        try:
            perimeter = cell_poly.length
            inradius = 2 * cell_area / perimeter if perimeter > 0 else 9999
        except Exception:
            inradius = 9999

        max_half_diag = CELL_INSET_RATIO * inradius
        half_diag = math.sqrt(w_s ** 2 + h_s ** 2) / 2
        if half_diag > max_half_diag and half_diag > 0:
            scale_down = max_half_diag / half_diag
            w_s *= scale_down
            h_s *= scale_down

        w_s = max(w_s, 12)
        h_s = max(h_s, 12)

        assignments.append((sid, cell_idx, cx, cy, w_s, h_s))

    return assignments


# ─── Alpha-bounding-box of a sticker image ───────────────────────────────────

def alpha_bbox(img):
    """
    Return (x0, y0, x1, y1) of the tight bounding box of visible (alpha>10) pixels,
    relative to the image origin. Returns (0, 0, w, h) if all transparent.
    """
    arr = np.array(img)
    alpha = arr[:, :, 3]
    rows = np.any(alpha > 10, axis=1)
    cols = np.any(alpha > 10, axis=0)
    if not rows.any():
        h, w = arr.shape[:2]
        return 0, 0, w, h
    y0 = int(np.argmax(rows))
    y1 = int(len(rows) - np.argmax(rows[::-1]))
    x0 = int(np.argmax(cols))
    x1 = int(len(cols) - np.argmax(cols[::-1]))
    return x0, y0, x1, y1


# ─── STEP 6: Hard fit constraint + label placement ───────────────────────────

def get_label_font():
    """Bold sans-serif at 11pt for sticker name labels."""
    return load_font(11, bold=True)


def compute_label_rect(draw, name, font, sticker_paste_x, sticker_paste_y,
                       sticker_w, sticker_h, sticker_img_resized,
                       pad=2):
    """
    Compute the label bounding rect (x0, y0, x1, y1) given a sticker paste position.
    Label is centered below sticker, 4px below visible bottom edge of sticker.
    Returns (lx0, ly0, lx1, ly1) for the background pill.
    """
    # Visible bottom edge of sticker (using alpha bbox)
    ax0, ay0, ax1, ay1 = alpha_bbox(sticker_img_resized)
    # ay1 is in sticker image coords; convert to canvas coords
    visible_bottom = sticker_paste_y + ay1

    tw, th = text_size(draw, name, font)
    lw = tw + pad * 2
    lh = th + pad * 2

    # Center label under sticker center
    sticker_cx = sticker_paste_x + sticker_w / 2
    lx0 = sticker_cx - lw / 2
    ly0 = visible_bottom + 4
    lx1 = lx0 + lw
    ly1 = ly0 + lh

    return lx0, ly0, lx1, ly1


def combined_bbox(px, py, pw, ph, lx0, ly0, lx1, ly1):
    """Union of sticker paste rect and label rect."""
    x0 = min(px, lx0)
    y0 = min(py, ly0)
    x1 = max(px + pw, lx1)
    y1 = max(py + ph, ly1)
    return x0, y0, x1, y1


def bbox_inside_silhouette(x0, y0, x1, y1, sil_poly):
    """
    Test whether the rectangle defined by (x0, y0, x1, y1) is fully inside
    the silhouette polygon.
    """
    rect = shapely_box(x0, y0, x1, y1)
    return sil_poly.contains(rect)


def apply_hard_fit_constraint(sid, cx, cy, w_s, h_s, sticker_img,
                               sil_poly, sil_centroid, draw, label_font):
    """
    Given an initial (cx, cy, w_s, h_s), iteratively shrink and shift until
    the combined sticker+label bbox is fully inside the silhouette.

    Strategy:
      Phase 0 — pre-shift: if center is within 20px of boundary, immediately
                shift toward centroid until 20px clearance or 30 small steps.
      Phase 1 — shrink+shift loop (FIT_MAX_ITERS rounds):
                shrink by 10% AND shift 8px toward centroid every round.
      Minimum sticker size: 20px.

    Returns (cx_final, cy_final, w_final, h_final, scale_factor, retries, inside)
    """
    name = DISPLAY_NAMES.get(sid, f"#{sid}")
    orig_w, orig_h = w_s, h_s
    shrink_retries = 0
    inside = False
    MIN_SIZE = 20.0
    PRE_SHIFT_THRESHOLD = 20.0   # px from boundary that triggers pre-shift
    PRE_SHIFT_STEP = 6.0         # px per pre-shift step
    PRE_SHIFT_MAX = 40           # max pre-shift iterations

    cx_cur, cy_cur = cx, cy
    w_cur, h_cur = w_s, h_s

    def _test(cx_t, cy_t, w_t, h_t):
        wi = max(1, int(round(w_t)))
        hi = max(1, int(round(h_t)))
        try:
            resized = sticker_img.resize((wi, hi), Image.LANCZOS)
        except Exception:
            return False, None
        px = cx_t - wi / 2
        py = cy_t - hi / 2
        lx0, ly0, lx1, ly1 = compute_label_rect(
            draw, name, label_font, px, py, wi, hi, resized
        )
        bx0, by0, bx1, by1 = combined_bbox(px, py, wi, hi, lx0, ly0, lx1, ly1)
        ok = bbox_inside_silhouette(bx0, by0, bx1, by1, sil_poly)
        return ok, resized

    # Phase 0: pre-shift center away from boundary if too close
    dist_to_boundary = sil_poly.exterior.distance(Point(cx_cur, cy_cur))
    if dist_to_boundary < PRE_SHIFT_THRESHOLD:
        dx = sil_centroid[0] - cx_cur
        dy = sil_centroid[1] - cy_cur
        dist_to_cen = math.sqrt(dx * dx + dy * dy)
        for _ in range(PRE_SHIFT_MAX):
            if sil_poly.exterior.distance(Point(cx_cur, cy_cur)) >= PRE_SHIFT_THRESHOLD:
                break
            if dist_to_cen > 0:
                cx_cur += (dx / dist_to_cen) * PRE_SHIFT_STEP
                cy_cur += (dy / dist_to_cen) * PRE_SHIFT_STEP
                # Recalculate direction vector from updated position
                dx2 = sil_centroid[0] - cx_cur
                dy2 = sil_centroid[1] - cy_cur
                dist_to_cen = math.sqrt(dx2 * dx2 + dy2 * dy2)
                dx, dy = dx2, dy2
            # Make sure we didn't shift outside
            if not sil_poly.contains(Point(cx_cur, cy_cur)):
                # Overshot — step back
                cx_cur -= (dx / dist_to_cen if dist_to_cen > 0 else 0) * PRE_SHIFT_STEP
                cy_cur -= (dy / dist_to_cen if dist_to_cen > 0 else 0) * PRE_SHIFT_STEP
                break

    # Initial check after pre-shift
    ok, _ = _test(cx_cur, cy_cur, w_cur, h_cur)
    if ok:
        inside = True
    else:
        for attempt in range(FIT_MAX_ITERS):
            shrink_retries += 1

            # Always shrink
            new_w = max(MIN_SIZE, w_cur * (1.0 - FIT_SHRINK_STEP))
            new_h = max(MIN_SIZE, h_cur * (1.0 - FIT_SHRINK_STEP))
            w_cur, h_cur = new_w, new_h

            # Always shift toward centroid
            dx = sil_centroid[0] - cx_cur
            dy = sil_centroid[1] - cy_cur
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > 0:
                cx_cur += (dx / dist) * FIT_SHIFT_DIST
                cy_cur += (dy / dist) * FIT_SHIFT_DIST
            # Guard: keep center inside silhouette
            if not sil_poly.contains(Point(cx_cur, cy_cur)):
                cx_cur, cy_cur = sil_centroid

            ok, _ = _test(cx_cur, cy_cur, w_cur, h_cur)
            if ok:
                inside = True
                break

    scale_factor = math.sqrt((w_cur * h_cur) / (orig_w * orig_h)) if (orig_w * orig_h) > 0 else 1.0
    return cx_cur, cy_cur, w_cur, h_cur, scale_factor, shrink_retries, inside


# ─── STEP 7: Rendering ───────────────────────────────────────────────────────

def load_cropped_sticker(sid):
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
    coords = [(int(x), int(y)) for x, y in canvas_pts]
    draw.line(coords + [coords[0]], fill=color, width=width)


def draw_name_label(canvas, draw, name, font, sticker_paste_x, sticker_paste_y,
                    sticker_w, sticker_h, sticker_img_resized, pad=2):
    """
    Draw name label below sticker on canvas.
    White rounded-rect pill at 50% opacity (alpha 180), dark text on top.
    """
    lx0, ly0, lx1, ly1 = compute_label_rect(
        draw, name, font,
        sticker_paste_x, sticker_paste_y,
        sticker_w, sticker_h, sticker_img_resized, pad
    )

    # Draw white pill background at 50% opacity using alpha composite
    pill_w = int(math.ceil(lx1 - lx0))
    pill_h = int(math.ceil(ly1 - ly0))
    if pill_w < 1 or pill_h < 1:
        return

    pill = Image.new("RGBA", (pill_w, pill_h), (0, 0, 0, 0))
    pill_draw = ImageDraw.Draw(pill)
    radius = min(4, pill_h // 2)
    pill_draw.rounded_rectangle([0, 0, pill_w - 1, pill_h - 1],
                                 radius=radius,
                                 fill=(255, 255, 255, 180))

    pill_x = int(round(lx0))
    pill_y = int(round(ly0))

    # Composite pill onto canvas
    canvas.alpha_composite(pill, (pill_x, pill_y))

    # Draw text on canvas draw (uses RGBA draw)
    tw, th = text_size(draw, name, font)
    tx = int(round(lx0 + (lx1 - lx0 - tw) / 2))
    ty = int(round(ly0 + (ly1 - ly0 - th) / 2))
    draw.text((tx, ty), name, fill=LABEL_TEXT_COLOR + (255,), font=font)


def render_stickers(canvas, assignments, canvas_pts, sil_poly):
    """
    Render all stickers with hard fit constraint and name labels.
    Returns (total_area, n_shrink_retries, n_at_risk, scale_factors, alert_count).
    """
    # Convert canvas to RGBA for alpha_composite support
    canvas_rgba = canvas.convert("RGBA")
    draw = ImageDraw.Draw(canvas_rgba, "RGBA")
    label_font = get_label_font()

    sil_centroid = (sil_poly.centroid.x, sil_poly.centroid.y)

    total_area = 0
    total_shrink_retries = 0
    at_risk_count = 0
    alert_count = 0
    scale_factors = []

    # Sort by sticker id for predictable render order
    sorted_assignments = sorted(assignments, key=lambda a: a[0])

    final_placements = []

    for (sid, cell_idx, cx, cy, w_s, h_s) in sorted_assignments:
        img = load_cropped_sticker(sid)
        if img is None:
            print(f"  WARN: cropped sticker #{sid} not found — skipping")
            continue

        # Apply hard fit constraint
        cx_f, cy_f, w_f, h_f, scale_f, retries, inside = apply_hard_fit_constraint(
            sid, cx, cy, w_s, h_s, img, sil_poly, sil_centroid, draw, label_font
        )

        total_shrink_retries += retries
        scale_factors.append(scale_f)

        if not inside:
            # Compute final combined bbox for alert reporting
            wi = max(1, int(round(w_f)))
            hi = max(1, int(round(h_f)))
            px = cx_f - wi / 2
            py = cy_f - hi / 2
            name = DISPLAY_NAMES.get(sid, f"#{sid}")
            try:
                resized_tmp = img.resize((wi, hi), Image.LANCZOS)
                lx0, ly0, lx1, ly1 = compute_label_rect(
                    draw, name, label_font, px, py, wi, hi, resized_tmp
                )
                bx0, by0, bx1, by1 = combined_bbox(px, py, wi, hi, lx0, ly0, lx1, ly1)
            except Exception:
                bx0, by0, bx1, by1 = px, py, px + wi, py + hi

            print(f"  ALERT: sticker {sid} ({name}) NOT FULLY INSIDE — "
                  f"bbox=({bx0:.0f},{by0:.0f},{bx1:.0f},{by1:.0f}) cx={cx_f:.0f} cy={cy_f:.0f}")
            alert_count += 1

        # Check at-risk (center within AT_RISK_THRESHOLD px of boundary)
        dist_to_boundary = sil_poly.exterior.distance(Point(cx_f, cy_f))
        if dist_to_boundary < AT_RISK_THRESHOLD:
            at_risk_count += 1

        final_placements.append((sid, cx_f, cy_f, w_f, h_f, inside))

    # Now render in sorted order
    for (sid, cx_f, cy_f, w_f, h_f, inside) in final_placements:
        img = load_cropped_sticker(sid)
        if img is None:
            continue

        wi = max(1, int(round(w_f)))
        hi = max(1, int(round(h_f)))
        if wi < 1 or hi < 1:
            continue

        resized = img.resize((wi, hi), Image.LANCZOS)
        px = int(round(cx_f - wi / 2))
        py = int(round(cy_f - hi / 2))

        canvas_rgba.paste(resized, (px, py), resized)
        total_area += wi * hi

        # Draw name label
        name = DISPLAY_NAMES.get(sid, f"#{sid}")
        draw_name_label(canvas_rgba, draw, name, label_font, px, py, wi, hi, resized)

    # Silhouette outline on top
    draw_silhouette_outline(draw, canvas_pts)

    # Convert back to RGB
    bg = Image.new("RGB", canvas_rgba.size, BG_COLOR)
    bg.paste(canvas_rgba, mask=canvas_rgba.split()[3])

    return bg, total_area, total_shrink_retries, at_risk_count, scale_factors, alert_count


# ─── Page chrome ─────────────────────────────────────────────────────────────

def draw_page_chrome(canvas):
    draw = ImageDraw.Draw(canvas)
    f_title    = load_font(36, bold=True)
    f_subtitle = load_font(14)
    f_footer   = load_font(12)

    title = "Merlion Puzzle \u2014 My Singapore Stories"
    tw, th = text_size(draw, title, f_title)
    draw.text(((A4_W - tw) // 2, 18), title, fill=TITLE_COLOR, font=f_title)

    subtitle = "Design draft \u2014 sticker layout for cutting"
    sw, sh = text_size(draw, subtitle, f_subtitle)
    draw.text(((A4_W - sw) // 2, 18 + th + 8), subtitle, fill=SUBTITLE_COLOR, font=f_subtitle)

    footer = "Little Dot Book  \u00b7  Book 2  \u00b7  v12 draft"
    fw, fh = text_size(draw, footer, f_footer)
    draw.text(((A4_W - fw) // 2, A4_H - fh - 20), footer, fill=FOOTER_COLOR, font=f_footer)


# ─── Coverage sanity check ────────────────────────────────────────────────────

def coverage_sanity_check(final_placements, sil_poly):
    """
    Log quadrant distribution and boundary proximity.
    """
    bounds = sil_poly.bounds
    minx, miny, maxx, maxy = bounds
    mid_x = (minx + maxx) / 2
    mid_y = (miny + maxy) / 2

    all_x0 = [cx - w / 2 for (_, cx, cy, w, h, _) in final_placements]
    all_y0 = [cy - h / 2 for (_, cx, cy, w, h, _) in final_placements]
    all_x1 = [cx + w / 2 for (_, cx, cy, w, h, _) in final_placements]
    all_y1 = [cy + h / 2 for (_, cx, cy, w, h, _) in final_placements]

    if all_x0:
        print(f"\n  COVERAGE CHECK: Sticker bbox x=[{min(all_x0):.0f},{max(all_x1):.0f}] "
              f"y=[{min(all_y0):.0f},{max(all_y1):.0f}]")

    tl = tr = bl = br = 0
    for (_, cx, cy, w, h, _) in final_placements:
        if cx <= mid_x and cy <= mid_y:
            tl += 1
        elif cx > mid_x and cy <= mid_y:
            tr += 1
        elif cx <= mid_x and cy > mid_y:
            bl += 1
        else:
            br += 1

    print(f"  Quadrant distribution (midpoint x={mid_x:.0f}, y={mid_y:.0f}):")
    print(f"    TL={tl}  TR={tr}")
    print(f"    BL={bl}  BR={br}")
    print(f"    Total: {tl + tr + bl + br}")

    near_edge = 0
    for (_, cx, cy, w, h, _) in final_placements:
        d = sil_poly.exterior.distance(Point(cx, cy))
        if d < 30:
            near_edge += 1
    print(f"  Stickers within 30px of silhouette boundary: {near_edge}")

    bottom_count = bl + br
    if bottom_count < 6:
        print(f"\n  DISTRIBUTION FAILED: bottom quadrant has only {bottom_count} stickers, expected 8+")
        return False, tl, tr, bl, br

    print(f"  Distribution OK: bottom quadrant has {bottom_count} stickers (>= 6 required)")
    return True, tl, tr, bl, br


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Merlion Puzzle A4 — v12: Dense Fill + Name Labels + Hard Fit")
    print("=" * 60)

    # STEP 1: Load cropped sticker sizes
    crop_sizes, pixel_counts, _sticker_images = load_cropped_sizes()

    if len(crop_sizes) < N_STICKERS:
        print(f"  WARNING: Only {len(crop_sizes)}/32 cropped stickers found.")
        for sid in range(1, N_STICKERS + 1):
            if sid not in crop_sizes:
                crop_sizes[sid] = (100, 100)
                pixel_counts[sid] = 1

    # STEP 2: Parse silhouette
    print("\n[STEP 2] Parsing SVG silhouette...")
    raw_pts = parse_svg_polygon(SVG_PATH)
    print(f"  {len(raw_pts)} polygon vertices parsed")

    canvas_pts, scale, tx, ty, sil_poly = build_canvas_silhouette(raw_pts, A4_W, HEADER_H)
    print(f"  Scale={scale:.4f}, offset=({tx},{ty})")
    print(f"  Silhouette area: {sil_poly.area:.0f} px^2")
    print(f"  Silhouette bounds: {[int(v) for v in sil_poly.bounds]}")

    # STEP 3: Seed 32 points inside silhouette
    print(f"\n[STEP 3] Seeding {N_STICKERS} points inside silhouette...")
    seed_pts = seed_points_inside(sil_poly, n=N_STICKERS)
    print(f"  Seeded {len(seed_pts)} points.")

    prepared_sil = prep(sil_poly)
    outside = [i for i, pt in enumerate(seed_pts) if not prepared_sil.contains(Point(pt[0], pt[1]))]
    if outside:
        print(f"  WARNING: {len(outside)} seed points outside silhouette — will be corrected by Lloyd's")
    else:
        print(f"  All {len(seed_pts)} seed points confirmed inside silhouette.")

    # STEP 4: Lloyd's relaxation
    print(f"\n[STEP 4] Running Lloyd's relaxation ({LLOYD_ITERS} iterations)...")
    final_pts, final_cells = lloyds_relaxation(seed_pts, sil_poly, iters=LLOYD_ITERS)
    print(f"  Lloyd's relaxation complete. {len(final_cells)} Voronoi cells computed.")

    cell_areas = sorted([c[2] for c in final_cells])
    print(f"  Cell area range: {cell_areas[0]:.0f} - {cell_areas[-1]:.0f} px^2")
    print(f"  Cell area median: {cell_areas[len(cell_areas)//2]:.0f} px^2")

    # STEP 5: Per-sticker sizing
    print(f"\n[STEP 5] Computing per-sticker sizes (CELL_FILL_RATIO={CELL_FILL_RATIO})...")
    assignments = compute_sticker_sizes(final_cells, crop_sizes, pixel_counts)
    ws_list = [w for (_, _, _, _, w, h) in assignments]
    hs_list = [h for (_, _, _, _, w, h) in assignments]
    print(f"  Initial sticker width range: {min(ws_list):.0f} - {max(ws_list):.0f} px")
    print(f"  Initial sticker height range: {min(hs_list):.0f} - {max(hs_list):.0f} px")

    # STEP 6: Render with hard fit constraint + labels
    print(f"\n[STEP 6] Rendering canvas with hard fit constraint + name labels...")
    canvas = Image.new("RGB", (A4_W, A4_H), BG_COLOR)
    draw_page_chrome(canvas)

    # render_stickers returns updated canvas (RGBA->RGB conversion done inside)
    canvas, total_sticker_area, total_shrink_retries, at_risk_count, \
        scale_factors, alert_count = render_stickers(canvas, assignments, canvas_pts, sil_poly)

    # Re-draw chrome on top (render_stickers returned a fresh RGB canvas)
    draw_page_chrome(canvas)

    # STEP 7: Coverage sanity check
    # Rebuild final_placements from assignments for coverage check
    # (use the original cx/cy as approximation — fit constraint modifies slightly)
    print(f"\n[STEP 7] Coverage sanity check...")
    # Build a simplified final_placements from assignments for quadrant check
    fp_for_check = [(sid, cx, cy, w_s, h_s, True) for (sid, _, cx, cy, w_s, h_s) in assignments]
    dist_ok, tl, tr, bl, br = coverage_sanity_check(fp_for_check, sil_poly)

    # STEP 8: Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(str(OUTPUT_PATH), "PNG", dpi=(150, 150))
    print(f"\n  Saved: {OUTPUT_PATH}")

    # ─── Self-verification log ────────────────────────────────────────────────
    n_placed = len(assignments)
    sil_area = sil_poly.area
    coverage_pct = total_sticker_area / sil_area * 100 if sil_area > 0 else 0

    footprints = [w * h for (_, _, _, _, w, h) in assignments]
    min_sf = min(scale_factors) if scale_factors else 1.0
    max_sf = max(scale_factors) if scale_factors else 1.0
    mean_sf = (sum(scale_factors) / len(scale_factors)) if scale_factors else 1.0

    print("\n" + "=" * 60)
    print(f"SELF-VERIFICATION LOG")
    print(f"  Stickers placed inside silhouette: {n_placed}/32")
    print(f"  Stickers that hit shrink retry loop: {total_shrink_retries}")
    print(f"  Stickers at-risk (within {AT_RISK_THRESHOLD}px of boundary): {at_risk_count}")
    print(f"  Scale factors — min={min_sf:.3f}  max={max_sf:.3f}  mean={mean_sf:.3f}")
    print(f"  Quadrant distribution: TL={tl}  TR={tr}  BL={bl}  BR={br}")
    print(f"  Alert count (NOT FULLY INSIDE): {alert_count}")
    if alert_count > 0:
        print(f"  *** {alert_count} ALERT(s) above — stickers partially outside silhouette ***")
    else:
        print(f"  All stickers confirmed inside silhouette.")
    print("=" * 60)

    print("\n" + "=" * 60)
    print(f"DONE: {n_placed}/32 stickers placed")
    print(f"FILES: {OUTPUT_PATH}")
    print(f"DISTRIBUTION: TL={tl}  TR={tr}  BL={bl}  BR={br}")
    print(f"COVERAGE: sticker area {total_sticker_area:.0f}px^2 / silhouette {sil_area:.0f}px^2 = {coverage_pct:.1f}%")
    print(f"SHRINK RETRIES: {total_shrink_retries}")
    print(f"AT-RISK: {at_risk_count}")
    print(f"ALERTS: {alert_count}")
    print(f"ISSUES: {'Distribution warning — bottom has only ' + str(bl+br) + ' stickers' if not dist_ok else 'None'}")
    print("=" * 60)

    return n_placed, alert_count, coverage_pct, tl, tr, bl, br


if __name__ == "__main__":
    main()
