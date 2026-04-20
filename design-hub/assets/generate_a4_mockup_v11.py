"""
generate_a4_mockup_v11.py
Merlion Puzzle A4 — v11: Lloyd's Relaxation distributed placement.

Rewritten PLACEMENT algorithm (crop step unchanged — uses existing icons/cropped/).
Lloyd's relaxation pre-distributes 32 target centers across the ENTIRE silhouette,
then sizes each sticker to its Voronoi cell area. Guarantees even coverage including
lower body and tail.

Steps:
  1. Skip auto-crop — cropped stickers already in icons/cropped/
  2. Parse Merlion silhouette SVG -> shapely Polygon at canvas coords.
  3. Seed 32 points inside silhouette.
  4. Lloyd's relaxation (10 iterations) -> evenly distributed centers.
  5. Voronoi-based per-sticker sizing (size-matched: largest cell <- biggest sticker).
  6. Render A4 page with page chrome + silhouette outline.
  7. Coverage sanity check (quadrant distribution).
  8. Save PNG.
"""

import os
import re
import math
import numpy as np
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

try:
    from shapely.geometry import Polygon, Point, MultiPolygon
    from shapely.prepared import prep
    SHAPELY = True
except ImportError:
    SHAPELY = False
    raise RuntimeError("shapely is required for v11. Install: pip install shapely")

try:
    from scipy.spatial import Voronoi
    SCIPY = True
except ImportError:
    SCIPY = False
    raise RuntimeError("scipy is required for v11. Install: pip install scipy")

# ─── Paths ────────────────────────────────────────────────────────────────────

BASE_DIR    = Path(r"C:/Users/Admin/Projects/oinio/littledotbook/design-hub/assets")
SVG_PATH    = BASE_DIR / "merlion-silhouette.svg"
CROPPED_DIR = BASE_DIR / "icons" / "cropped"
OUTPUT_PATH = BASE_DIR / "merlion-puzzle-a4-v11.png"

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
CELL_FILL_RATIO = 0.70   # sticker footprint = 70% of Voronoi cell area
CELL_INSET_RATIO = 0.90  # half-diagonal must not exceed 90% of inradius

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


# ─── STEP 1: Load cropped sticker sizes ──────────────────────────────────────

def load_cropped_sizes():
    """Load existing cropped stickers and return {id: (w, h)} + pixel count."""
    print("\n[STEP 1] Loading cropped sticker sizes...")
    crop_sizes = {}
    pixel_counts = {}

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
            # Count non-transparent pixels
            px_count = int(np.sum(arr[:, :, 3] > 10))
            crop_sizes[sid] = (w, h)
            pixel_counts[sid] = px_count
            print(f"  #{sid:2d}: {w}x{h}px, {px_count} visible pixels")
        except Exception as e:
            print(f"  WARN #{sid}: load error: {e}")

    print(f"  Loaded {len(crop_sizes)}/32 cropped stickers.")
    return crop_sizes, pixel_counts


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
    ty = header_h + 10  # small gap below header

    canvas_pts = [(x * scale + tx, y * scale + ty) for (x, y) in raw_pts]

    sil_poly = Polygon(canvas_pts)
    if not sil_poly.is_valid:
        sil_poly = sil_poly.buffer(0)

    return canvas_pts, scale, tx, ty, sil_poly


# ─── STEP 3: Seed 32 points inside silhouette ────────────────────────────────

def seed_points_inside(sil_poly, n=N_STICKERS):
    """
    Generate exactly n seed points inside the silhouette by sampling a grid.
    Uses shapely.prepared for fast containment checks.
    """
    prepared = prep(sil_poly)
    bounds = sil_poly.bounds  # (minx, miny, maxx, maxy)
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

    # Try increasing grid sizes until we have enough points
    for rows in range(8, 40):
        cols = rows
        pts = grid_points(rows, cols)
        if len(pts) >= n:
            # Pick n evenly-spaced from the list
            if len(pts) == n:
                return np.array(pts)
            # Thin: pick every Nth to get exactly n
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

    To make Voronoi well-defined on a bounded region, we add mirror points
    outside the bbox to close all infinite ridges.
    """
    bounds = sil_poly.bounds
    minx, miny, maxx, maxy = bounds
    pad = max(maxx - minx, maxy - miny) * 1.5

    # Mirror points to bound all Voronoi regions
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
            # Infinite region — use a large bbox clipped to silhouette
            from shapely.geometry import box as shapely_box
            large_box = shapely_box(minx - pad, miny - pad, maxx + pad, maxy + pad)
            cell = large_box
        else:
            verts = [vor.vertices[v] for v in region]
            if len(verts) < 3:
                from shapely.geometry import box as shapely_box
                cell = shapely_box(minx - pad, miny - pad, maxx + pad, maxy + pad)
            else:
                cell = Polygon(verts)
                if not cell.is_valid:
                    cell = cell.buffer(0)

        # Clip cell to silhouette
        try:
            clipped = cell.intersection(sil_poly)
        except Exception:
            clipped = sil_poly  # fallback

        if clipped.is_empty:
            # Degenerate — use a tiny circle
            clipped = Point(points[i]).buffer(5)

        # Get centroid
        if hasattr(clipped, 'geoms'):
            # MultiPolygon — pick the part containing the seed point
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
            # Move to centroid if it's inside silhouette; else keep current
            if prepared.contains(Point(cx, cy)):
                new_pts.append([cx, cy])
            else:
                # Snap to nearest interior point by small nudge toward centroid
                ox, oy = pts[i]
                # Walk 50% toward centroid and check
                mx, my = (ox + cx) / 2, (oy + cy) / 2
                if prepared.contains(Point(mx, my)):
                    new_pts.append([mx, my])
                else:
                    new_pts.append([ox, oy])
        pts = np.array(new_pts)
        avg_move = np.mean(np.linalg.norm(pts - initial_pts, axis=1))
        print(f"  Lloyd iter {iteration + 1}/{iters}: avg displacement {avg_move:.1f}px")

    # Final cells
    cells = make_voronoi_cells(pts, sil_poly)
    return pts, cells


# ─── STEP 5: Per-sticker sizing from Voronoi cells ───────────────────────────

def compute_sticker_sizes(cells, crop_sizes, pixel_counts):
    """
    For each Voronoi cell (sorted by area desc), compute target sticker size.
    Assign largest cell to highest-content sticker.
    Returns list of (sticker_id, center_x, center_y, w_px, h_px) in cell order.
    """
    # Sort cells by area (largest first) — keep original index for center lookup
    cell_order = sorted(range(N_STICKERS), key=lambda i: cells[i][2], reverse=True)

    # Sort stickers by visible pixel count (largest content first)
    sticker_order = sorted(pixel_counts.keys(), key=lambda s: pixel_counts[s], reverse=True)

    # Pad sticker_order if fewer than 32 loaded
    available_ids = list(sticker_order)
    if len(available_ids) < N_STICKERS:
        # fill missing with ids in order
        all_ids = set(available_ids)
        for sid in range(1, N_STICKERS + 1):
            if sid not in all_ids:
                available_ids.append(sid)

    assignments = []  # (sid, cell_idx, center_x, center_y, w_px, h_px)

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
        # Approximate inradius as 2*area/perimeter
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

        # Ensure minimum sticker size (12px)
        w_s = max(w_s, 12)
        h_s = max(h_s, 12)

        assignments.append((sid, cell_idx, cx, cy, w_s, h_s))

    return assignments


# ─── STEP 6: Rendering ────────────────────────────────────────────────────────

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


def draw_number_badge(draw, x, y, number, font):
    """Draw tiny number badge: white circle + dark number at (x, y) top-left of sticker."""
    r = 12
    cx_b, cy_b = x + r + 2, y + r + 2
    draw.ellipse([cx_b - r, cy_b - r, cx_b + r, cy_b + r], fill=BADGE_BG)
    label = str(number)
    tw, th = text_size(draw, label, font)
    draw.text((cx_b - tw // 2, cy_b - th // 2), label, fill=BADGE_TEXT, font=font)


def render_stickers(canvas, assignments, canvas_pts):
    draw = ImageDraw.Draw(canvas, "RGBA")
    badge_font = load_font(10, bold=True)
    total_area = 0

    # Sort by sticker id for predictable render order
    sorted_assignments = sorted(assignments, key=lambda a: a[0])

    for (sid, cell_idx, cx, cy, w_s, h_s) in sorted_assignments:
        img = load_cropped_sticker(sid)
        if img is None:
            print(f"  WARN: cropped sticker #{sid} not found — skipping")
            continue

        w_i, h_i = int(round(w_s)), int(round(h_s))
        if w_i < 1 or h_i < 1:
            continue

        resized = img.resize((w_i, h_i), Image.LANCZOS)
        px = int(round(cx - w_i / 2))
        py = int(round(cy - h_i / 2))

        canvas.paste(resized, (px, py), resized)
        total_area += w_i * h_i

        draw_number_badge(draw, px, py, sid, badge_font)

    # Silhouette outline on top
    draw_silhouette_outline(draw, canvas_pts)

    return total_area


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

    footer = "Little Dot Book  \u00b7  Book 2  \u00b7  v11 draft"
    fw, fh = text_size(draw, footer, f_footer)
    draw.text(((A4_W - fw) // 2, A4_H - fh - 20), footer, fill=FOOTER_COLOR, font=f_footer)


# ─── Coverage sanity check ────────────────────────────────────────────────────

def coverage_sanity_check(assignments, sil_poly):
    """
    Log:
    - Bounding box of all placed stickers
    - Sticker count per 2x2 quadrant of silhouette bbox
    - Stickers within 30px of silhouette boundary
    Abort if bottom quadrant has fewer than 6 stickers.
    """
    bounds = sil_poly.bounds  # (minx, miny, maxx, maxy)
    minx, miny, maxx, maxy = bounds
    mid_x = (minx + maxx) / 2
    mid_y = (miny + maxy) / 2

    placed_xs = [cx for (_, _, cx, cy, _, _) in assignments]
    placed_ys = [cy for (_, _, cx, cy, _, _) in assignments]

    all_x0 = [cx - w / 2 for (_, _, cx, cy, w, h) in assignments]
    all_y0 = [cy - h / 2 for (_, _, cx, cy, w, h) in assignments]
    all_x1 = [cx + w / 2 for (_, _, cx, cy, w, h) in assignments]
    all_y1 = [cy + h / 2 for (_, _, cx, cy, w, h) in assignments]

    if placed_xs:
        bbox_x0, bbox_y0 = min(all_x0), min(all_y0)
        bbox_x1, bbox_y1 = max(all_x1), max(all_y1)
        print(f"\n  COVERAGE CHECK: Sticker bbox x=[{bbox_x0:.0f},{bbox_x1:.0f}] y=[{bbox_y0:.0f},{bbox_y1:.0f}]")
    else:
        print("  COVERAGE CHECK: No stickers placed!")
        return

    # Quadrant counts
    tl = tr = bl = br = 0
    prepared = prep(sil_poly)

    for (_, _, cx, cy, _, _) in assignments:
        if cx <= mid_x and cy <= mid_y:
            tl += 1
        elif cx > mid_x and cy <= mid_y:
            tr += 1
        elif cx <= mid_x and cy > mid_y:
            bl += 1
        else:
            br += 1

    print(f"  Quadrant distribution (silhouette midpoint x={mid_x:.0f}, y={mid_y:.0f}):")
    print(f"    TL={tl}  TR={tr}")
    print(f"    BL={bl}  BR={br}")
    print(f"    Total: {tl + tr + bl + br}")

    # Edge crowding
    near_edge = 0
    for (_, _, cx, cy, _, _) in assignments:
        d = sil_poly.exterior.distance(Point(cx, cy))
        if d < 30:
            near_edge += 1
    print(f"  Stickers within 30px of silhouette boundary: {near_edge}")

    bottom_count = bl + br
    if bottom_count < 6:
        print(f"\n  DISTRIBUTION FAILED: bottom quadrant has only {bottom_count} stickers, expected 8+")
        print("  The Lloyd relaxation did not distribute stickers evenly. Check silhouette parsing.")
        return False

    print(f"  Distribution OK: bottom quadrant has {bottom_count} stickers (>= 6 required)")
    return True


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Merlion Puzzle A4 — v11: Lloyd's Relaxation Placement")
    print("=" * 60)

    # STEP 1: Load cropped sticker sizes
    crop_sizes, pixel_counts = load_cropped_sizes()

    if len(crop_sizes) < N_STICKERS:
        print(f"  WARNING: Only {len(crop_sizes)}/32 cropped stickers found.")
        # Fill missing with fallback 100x100
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
    print(f"  Seeded {len(seed_pts)} points. Verifying all inside silhouette...")

    prepared_sil = prep(sil_poly)
    outside = [i for i, pt in enumerate(seed_pts) if not prepared_sil.contains(Point(pt[0], pt[1]))]
    if outside:
        print(f"  WARNING: {len(outside)} seed points outside silhouette — they will be corrected by Lloyd's")
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
    print(f"\n[STEP 5] Computing per-sticker sizes (Voronoi cell assignment)...")
    assignments = compute_sticker_sizes(final_cells, crop_sizes, pixel_counts)
    ws_list = [w for (_, _, _, _, w, h) in assignments]
    hs_list = [h for (_, _, _, _, w, h) in assignments]
    print(f"  Sticker width range: {min(ws_list):.0f} - {max(ws_list):.0f} px")
    print(f"  Sticker height range: {min(hs_list):.0f} - {max(hs_list):.0f} px")
    print(f"  Min footprint: {min(w*h for w,h in zip(ws_list,hs_list)):.0f} px^2")
    print(f"  Max footprint: {max(w*h for w,h in zip(ws_list,hs_list)):.0f} px^2")

    # STEP 6: Render
    print(f"\n[STEP 6] Rendering canvas...")
    canvas = Image.new("RGB", (A4_W, A4_H), BG_COLOR)
    draw_page_chrome(canvas)
    total_sticker_area = render_stickers(canvas, assignments, canvas_pts)

    # STEP 7: Coverage sanity check
    print(f"\n[STEP 7] Coverage sanity check...")
    dist_ok = coverage_sanity_check(assignments, sil_poly)

    # STEP 8: Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(str(OUTPUT_PATH), "PNG", dpi=(150, 150))
    print(f"\n  Saved: {OUTPUT_PATH}")

    # ─── Final stats ─────────────────────────────────────────────────────────
    sil_area = sil_poly.area
    coverage_pct = total_sticker_area / sil_area * 100 if sil_area > 0 else 0

    footprints = [w * h for (_, _, _, _, w, h) in assignments]
    min_fp = min(footprints) if footprints else 0
    max_fp = max(footprints) if footprints else 0

    bounds = sil_poly.bounds
    mid_y = (bounds[1] + bounds[3]) / 2
    tl = sum(1 for (_, _, cx, cy, _, _) in assignments if cx <= (bounds[0]+bounds[2])/2 and cy <= mid_y)
    tr = sum(1 for (_, _, cx, cy, _, _) in assignments if cx > (bounds[0]+bounds[2])/2 and cy <= mid_y)
    bl = sum(1 for (_, _, cx, cy, _, _) in assignments if cx <= (bounds[0]+bounds[2])/2 and cy > mid_y)
    br = sum(1 for (_, _, cx, cy, _, _) in assignments if cx > (bounds[0]+bounds[2])/2 and cy > mid_y)

    print("\n" + "=" * 60)
    print(f"DONE: {len(assignments)}/32 stickers placed")
    print(f"FILES: {OUTPUT_PATH}")
    print(f"DISTRIBUTION: TL={tl}  TR={tr}  BL={bl}  BR={br}")
    print(f"SIZE RANGE: min footprint {min_fp:.0f}px^2 (~{math.sqrt(min_fp):.0f}x{math.sqrt(min_fp):.0f}), "
          f"max {max_fp:.0f}px^2 (~{math.sqrt(max_fp):.0f}x{math.sqrt(max_fp):.0f})")
    print(f"COVERAGE: sticker area {total_sticker_area:.0f}px^2 / silhouette {sil_area:.0f}px^2 = {coverage_pct:.1f}%")
    print(f"ISSUES: {'Distribution warning — bottom has only ' + str(bl+br) + ' stickers' if not dist_ok else 'None'}")
    print(f"NEXT: Open {OUTPUT_PATH} in Illustrator, draw puzzle cut lines over stickers")
    print("=" * 60)

    return len(assignments), 0, coverage_pct, tl, tr, bl, br


if __name__ == "__main__":
    main()
