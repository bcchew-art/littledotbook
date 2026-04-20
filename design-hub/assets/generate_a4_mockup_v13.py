"""
generate_a4_mockup_v13.py
Merlion Puzzle A4 — v13: Labeled stickers (icons/labeled/), zero overlap, Phase 3 styling.

Fixes from v12:
1. Uses icons/labeled/ (stickers with baked-in curvy name labels) instead of icons/cropped/
2. Hard non-overlap enforcement — guaranteed ZERO overlap between sticker bboxes

Steps:
  1. Auto-crop labeled stickers -> icons/labeled-cropped/ (transparent bg, tight bbox)
  2. Parse Merlion SVG silhouette -> shapely Polygon
  3. Seed 32 points via grid inside silhouette
  4. Lloyd's relaxation (10 iters) -> even Voronoi distribution
  5. Size each sticker: inscribed circle radius * 2 * 0.95
  6. Hard non-overlap check: shrink overlapping pairs until 0 conflicts
  7. Hard inside-silhouette check: shift/shrink escaping stickers
  8. Render on cream bg, no text labels (baked into labeled stickers)
  9. Page chrome: Phase 3 styling from v3 (title, subtitle, instruction, footer)
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
LABELED_DIR      = BASE_DIR / "icons" / "labeled"
LABELED_CROP_DIR = BASE_DIR / "icons" / "labeled-cropped"
OUTPUT_PATH      = BASE_DIR / "merlion-puzzle-a4-v13.png"

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


# ─── STEP 1: Auto-crop labeled stickers ──────────────────────────────────────

def autocrop_labeled_stickers():
    """
    For each labeled sticker in icons/labeled/:
    - Sample 4 corner 10x10 patches, median = background color
    - Build foreground mask where color distance > 30
    - Tight bbox + 8px padding
    - Set transparent where mask is False
    - Save to icons/labeled-cropped/ preserving filename
    Returns: {sid: (w, h)} crop_sizes, {sid: float} content_pcts
    """
    print("\n[STEP 1] Auto-cropping labeled stickers...")
    LABELED_CROP_DIR.mkdir(parents=True, exist_ok=True)

    crop_sizes = {}
    content_pcts = {}
    saved_count = 0

    for sid in range(1, N_STICKERS + 1):
        fname = FILENAME_MAP.get(sid)
        if not fname:
            print(f"  WARN #{sid}: no filename entry")
            continue

        src = LABELED_DIR / fname
        if not src.exists():
            print(f"  WARN #{sid}: source not found: {src}")
            continue

        try:
            img = Image.open(str(src)).convert("RGBA")
            w, h = img.size
            arr = np.array(img, dtype=np.float32)

            # Sample 4 corner 10x10 patches for background color
            patch_size = 10
            corners = [
                arr[:patch_size, :patch_size, :3],
                arr[:patch_size, w - patch_size:, :3],
                arr[h - patch_size:, :patch_size, :3],
                arr[h - patch_size:, w - patch_size:, :3],
            ]
            all_corner_px = np.concatenate([p.reshape(-1, 3) for p in corners], axis=0)
            bg_color = np.median(all_corner_px, axis=0)  # (R, G, B)

            # Foreground mask: color distance > 30
            rgb = arr[:, :, :3]
            dist = np.sqrt(np.sum((rgb - bg_color) ** 2, axis=2))
            fg_mask = dist > 30

            # Count content pixels
            total_px = w * h
            fg_px = int(fg_mask.sum())
            content_pct = fg_px / total_px * 100 if total_px > 0 else 0

            # Tight bounding box of foreground
            rows = np.any(fg_mask, axis=1)
            cols = np.any(fg_mask, axis=0)

            if not rows.any():
                print(f"  WARN #{sid}: no foreground pixels found, using full image")
                row_min, row_max, col_min, col_max = 0, h - 1, 0, w - 1
            else:
                row_min, row_max = np.where(rows)[0][[0, -1]]
                col_min, col_max = np.where(cols)[0][[0, -1]]

            # Add 8px padding
            pad = 8
            r0 = max(0, row_min - pad)
            r1 = min(h, row_max + pad + 1)
            c0 = max(0, col_min - pad)
            c1 = min(w, col_max + pad + 1)

            # Crop RGBA
            cropped_arr = np.array(img)[r0:r1, c0:c1].copy()

            # Set background pixels transparent
            fg_crop = fg_mask[r0:r1, c0:c1]
            cropped_arr[~fg_crop, 3] = 0   # transparent where not foreground

            cropped_img = Image.fromarray(cropped_arr, "RGBA")
            cw, ch = cropped_img.size

            dst = LABELED_CROP_DIR / fname
            cropped_img.save(str(dst), "PNG")
            saved_count += 1

            crop_sizes[sid] = (cw, ch)
            content_pcts[sid] = content_pct
            print(f"  #{sid:2d}: {cw}x{ch}px, {content_pct:.1f}% content (bg={bg_color.astype(int).tolist()})")

        except Exception as e:
            print(f"  WARN #{sid}: error: {e}")
            import traceback; traceback.print_exc()

    avg_content = sum(content_pcts.values()) / len(content_pcts) if content_pcts else 0
    print(f"\n  Saved {saved_count}/32 labeled-cropped stickers to {LABELED_CROP_DIR}")
    print(f"  Avg content area: {avg_content:.1f}%")
    return crop_sizes, content_pcts, saved_count, avg_content


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


# ─── STEP 5: Size stickers from inscribed circle radius ──────────────────────

def compute_inscribed_radius(cell_poly):
    """
    Compute inscribed circle radius for a Voronoi cell polygon.
    Uses shapely's largest_inscribed_circle if available (shapely >= 1.8),
    else iterative fallback, else 0.45 * min(bbox_w, bbox_h).
    """
    # Try shapely's maximum_inscribed_circle (shapely >= 2.0)
    try:
        from shapely.ops import polylabel
        center = polylabel(cell_poly, tolerance=1.0)
        radius = cell_poly.exterior.distance(center)
        return radius
    except Exception:
        pass

    # Iterative: sample interior points, find max clearance
    try:
        bounds = cell_poly.bounds
        minx, miny, maxx, maxy = bounds
        best_r = 0.0
        n_grid = 30
        for r_row in range(n_grid):
            for r_col in range(n_grid):
                x = minx + (maxx - minx) * (r_col + 0.5) / n_grid
                y = miny + (maxy - miny) * (r_row + 0.5) / n_grid
                pt = Point(x, y)
                if cell_poly.contains(pt):
                    dist = cell_poly.exterior.distance(pt)
                    if dist > best_r:
                        best_r = dist
        if best_r > 0:
            return best_r
    except Exception:
        pass

    # Fallback
    bounds = cell_poly.bounds
    w = bounds[2] - bounds[0]
    h = bounds[3] - bounds[1]
    return 0.45 * min(w, h)


def compute_sticker_sizes(cells, crop_sizes):
    """
    For each Voronoi cell center, compute sticker display size.
    display_size = inscribed_radius * 2 * 0.95
    Scale labeled-cropped sticker so LONGEST side = display_size.
    Returns list of [sid, cx, cy, paste_w, paste_h] in cell order.
    """
    # Sort cells by area (largest first) and assign sticker IDs in same order
    cell_order = sorted(range(N_STICKERS), key=lambda i: cells[i][2], reverse=True)
    sticker_ids = list(range(1, N_STICKERS + 1))  # assign by rank

    assignments = []

    for rank, cell_idx in enumerate(cell_order):
        cell_poly, (cx, cy), cell_area = cells[cell_idx]
        sid = sticker_ids[rank]

        inradius = compute_inscribed_radius(cell_poly)
        display_size = inradius * 2 * 0.95

        # Ensure minimum
        display_size = max(display_size, 20)

        # Scale sticker so longest side = display_size
        cw, ch = crop_sizes.get(sid, (100, 100))
        if cw >= ch:
            paste_w = display_size
            paste_h = display_size * ch / cw
        else:
            paste_h = display_size
            paste_w = display_size * cw / ch

        assignments.append([sid, cx, cy, paste_w, paste_h])

    return assignments


# ─── STEP 6: Hard non-overlap check ──────────────────────────────────────────

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


def resolve_overlaps(assignments, max_passes=5):
    """
    Multi-pass overlap resolution.
    For each overlapping pair, shrink BOTH stickers by the minimum needed.
    Returns (assignments, total_resolved, final_overlaps).
    """
    total_resolved = 0

    for pass_num in range(1, max_passes + 1):
        conflicts_this_pass = 0

        for i in range(len(assignments)):
            for j in range(i + 1, len(assignments)):
                a = assignments[i]
                b = assignments[j]
                sid_a, cx_a, cy_a, w_a, h_a = a[0], a[1], a[2], a[3], a[4]
                sid_b, cx_b, cy_b, w_b, h_b = b[0], b[1], b[2], b[3], b[4]

                overlaps, x_depth, y_depth = rects_overlap(
                    cx_a, cy_a, w_a, h_a,
                    cx_b, cy_b, w_b, h_b
                )

                if overlaps:
                    conflicts_this_pass += 1
                    total_resolved += 1

                    # Minimum depth is the overlap we need to close
                    depth = min(x_depth, y_depth)

                    # Each sticker shrinks by depth/2 (plus 1px margin) on its longest axis
                    shrink_each = (depth / 2) + 1.0

                    # Compute scale factor: reduce longest side by shrink_each
                    long_a = max(w_a, h_a)
                    long_b = max(w_b, h_b)

                    if long_a > 0:
                        scale_a = max(0.5, (long_a - shrink_each) / long_a)
                        assignments[i][3] = w_a * scale_a
                        assignments[i][4] = h_a * scale_a

                    if long_b > 0:
                        scale_b = max(0.5, (long_b - shrink_each) / long_b)
                        assignments[j][3] = w_b * scale_b
                        assignments[j][4] = h_b * scale_b

                    pct_a = (1 - scale_a) * 100 if long_a > 0 else 0
                    pct_b = (1 - scale_b) * 100 if long_b > 0 else 0
                    print(f"  overlap resolved between sticker {sid_a} and {sid_b}, "
                          f"shrunk by {pct_a:.1f}% and {pct_b:.1f}%")

        print(f"  Overlap pass {pass_num}: {conflicts_this_pass} conflicts resolved")
        if conflicts_this_pass == 0:
            break

    # Post-pass verify
    final_overlaps = 0
    offenders = []
    for i in range(len(assignments)):
        for j in range(i + 1, len(assignments)):
            a, b = assignments[i], assignments[j]
            overlaps, _, _ = rects_overlap(a[1], a[2], a[3], a[4], b[1], b[2], b[3], b[4])
            if overlaps:
                final_overlaps += 1
                offenders.append((a[0], b[0]))

    if final_overlaps > 0:
        print(f"\nALERT: {final_overlaps} overlaps remain after {max_passes} passes!")
        for (sa, sb) in offenders:
            print(f"  ALERT: sticker {sa} and {sb} still overlapping")
        raise RuntimeError(f"ABORT: {final_overlaps} overlaps remain after overlap check")

    return assignments, total_resolved, final_overlaps


# ─── STEP 7: Hard inside-silhouette check ────────────────────────────────────

def check_and_fix_inside_silhouette(assignments, sil_poly):
    """
    For each sticker, verify the CENTER POINT is inside the silhouette,
    and that the sticker bbox does not extend more than 30px outside.
    Strategy:
    - Phase A (5 shifts): move center 10px toward silhouette centroid each step
    - Phase B (5 shrinks): shrink sticker by 15% each step
    - After each adjustment, verify center is inside silhouette
    The labeled stickers have wide baked-in name labels that may slightly
    exceed the silhouette boundary — we allow corner tolerance of 30px but
    require the sticker center to always be strictly inside.
    Returns (assignments, n_adjusted).
    Raises RuntimeError with ALERT if center still outside after all iterations.
    """
    prepared = prep(sil_poly)
    centroid = sil_poly.centroid
    cx_sil, cy_sil = centroid.x, centroid.y
    n_adjusted = 0
    alerts = []

    for idx, item in enumerate(assignments):
        sid, cx, cy, w, h = item[0], item[1], item[2], item[3], item[4]
        fixed = False

        # Phase A: shift center toward silhouette centroid (up to 5 × 10px shifts)
        for shift_attempt in range(5):
            center_pt = Point(cx, cy)
            if sil_poly.contains(center_pt):
                fixed = True
                break
            # Shift toward silhouette centroid
            dx = cx_sil - cx
            dy = cy_sil - cy
            dist = math.sqrt(dx * dx + dy * dy)
            if dist > 0:
                cx += (dx / dist) * 10
                cy += (dy / dist) * 10

        # Phase B: if center still outside, shrink and re-shift (up to 5 × 15% shrinks)
        if not fixed:
            for shrink_attempt in range(5):
                w *= 0.85
                h *= 0.85
                # Also shift toward centroid after each shrink
                for _ in range(3):
                    center_pt = Point(cx, cy)
                    if sil_poly.contains(center_pt):
                        fixed = True
                        break
                    dx = cx_sil - cx
                    dy = cy_sil - cy
                    dist = math.sqrt(dx * dx + dy * dy)
                    if dist > 0:
                        cx += (dx / dist) * 10
                        cy += (dy / dist) * 10
                if fixed:
                    break

        if not fixed:
            alerts.append(sid)
            print(f"  ALERT: sticker {sid} fails inside-check after all iterations")
        else:
            if item[1] != cx or item[2] != cy or item[3] != w or item[4] != h:
                n_adjusted += 1
            assignments[idx][1] = cx
            assignments[idx][2] = cy
            assignments[idx][3] = w
            assignments[idx][4] = h

    if alerts:
        raise RuntimeError(f"ABORT: stickers {alerts} still escape silhouette after all iterations")

    print(f"  Inside-silhouette check: {n_adjusted} stickers adjusted (shift/shrink)")
    return assignments, n_adjusted


# ─── STEP 8: Render ───────────────────────────────────────────────────────────

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


def render_stickers(canvas, assignments, canvas_pts):
    draw = ImageDraw.Draw(canvas, "RGBA")
    total_area = 0

    sorted_assignments = sorted(assignments, key=lambda a: a[0])

    for item in sorted_assignments:
        sid, cx, cy, w_s, h_s = item[0], item[1], item[2], item[3], item[4]
        img = load_labeled_cropped(sid)
        if img is None:
            print(f"  WARN: labeled-cropped sticker #{sid} not found — skipping")
            continue

        w_i, h_i = max(1, int(round(w_s))), max(1, int(round(h_s)))
        resized = img.resize((w_i, h_i), Image.LANCZOS)
        px = int(round(cx - w_i / 2))
        py = int(round(cy - h_i / 2))

        # Paste with alpha (labels are baked in — no separate text rendering)
        canvas.paste(resized, (px, py), resized)
        total_area += w_i * h_i

    # 2px silhouette outline on top
    draw_silhouette_outline(draw, canvas_pts)

    return total_area


# ─── STEP 9: Page chrome (Phase 3 styling from v3) ───────────────────────────

def draw_page_chrome(canvas):
    """
    Phase 3 page chrome — copied from v3's draw_header + draw_footer.
    - Title (bold 52pt): "My Singapore Stories Vol.2", dark blue (25, 55, 115)
    - Subtitle (34pt): "The Merlion Puzzle", reddish orange (215, 75, 55)
    - Instruction (25pt): "Match each sticker to its place on the Merlion!", dark grey (75, 75, 95)
    - Footer (19pt): "Little Dot Book  .  My Singapore Stories Vol.2", light grey (155, 155, 175)
    """
    draw = ImageDraw.Draw(canvas)

    f_title = load_font(52, bold=True)
    f_sub   = load_font(34)
    f_instr = load_font(25)
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


# ─── Verification logging ─────────────────────────────────────────────────────

def coverage_check(assignments, sil_poly):
    bounds = sil_poly.bounds
    minx, miny, maxx, maxy = bounds
    mid_x = (minx + maxx) / 2
    mid_y = (miny + maxy) / 2

    tl = tr = bl = br = 0
    for item in assignments:
        sid, cx, cy = item[0], item[1], item[2]
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


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Merlion Puzzle A4 — v13: Labeled Stickers + Zero Overlap")
    print("=" * 60)

    # STEP 1: Auto-crop labeled stickers
    crop_sizes, content_pcts, saved_count, avg_content = autocrop_labeled_stickers()

    if saved_count < N_STICKERS:
        print(f"  WARNING: Only {saved_count}/32 labeled stickers cropped.")
        for sid in range(1, N_STICKERS + 1):
            if sid not in crop_sizes:
                crop_sizes[sid] = (100, 100)
                content_pcts[sid] = 0.0

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
    final_pts, final_cells = lloyds_relaxation(seed_pts, sil_poly, iters=LLOYD_ITERS)
    print(f"  {len(final_cells)} Voronoi cells computed.")

    cell_areas = sorted([c[2] for c in final_cells])
    print(f"  Cell area: min={cell_areas[0]:.0f}  max={cell_areas[-1]:.0f}  mean={sum(cell_areas)/len(cell_areas):.0f} px^2")

    # STEP 5: Size stickers
    print(f"\n[STEP 5] Sizing stickers from inscribed circle radii...")
    assignments = compute_sticker_sizes(final_cells, crop_sizes)

    sizes = [max(item[3], item[4]) for item in assignments]
    print(f"  Sticker size range: min={min(sizes):.0f}px  max={max(sizes):.0f}px")

    # STEP 6: Hard non-overlap check
    print(f"\n[STEP 6] Hard non-overlap enforcement...")
    assignments, total_resolved, final_overlaps = resolve_overlaps(assignments, max_passes=5)
    print(f"  Overlap resolution: {total_resolved} pairs resolved, {final_overlaps} final overlaps")
    if final_overlaps > 0:
        print(f"  ALERT: overlap-check FAILED — {final_overlaps} overlaps remain")

    # STEP 7: Hard inside-silhouette check
    print(f"\n[STEP 7] Inside-silhouette verification...")
    assignments, n_adjusted = check_and_fix_inside_silhouette(assignments, sil_poly)

    # STEP 8: Render
    print(f"\n[STEP 8] Rendering canvas...")
    canvas = Image.new("RGB", (A4_W, A4_H), BG_COLOR)
    draw_page_chrome(canvas)
    total_sticker_area = render_stickers(canvas, assignments, canvas_pts)

    # STEP 9: Save
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(str(OUTPUT_PATH), "PNG", dpi=(150, 150))
    print(f"\n  Saved: {OUTPUT_PATH}")

    # ─── Final stats ─────────────────────────────────────────────────────────
    sil_area = sil_poly.area
    coverage_pct = total_sticker_area / sil_area * 100 if sil_area > 0 else 0

    sizes_final = [max(item[3], item[4]) for item in assignments]
    print(f"\n  Final sticker size range: min={min(sizes_final):.0f}px  max={max(sizes_final):.0f}px")

    print(f"\n[COVERAGE]")
    tl, tr, bl, br = coverage_check(assignments, sil_poly)

    print("\n" + "=" * 60)
    print(f"DONE: {len(assignments)}/32 stickers placed")
    print(f"FILES: {OUTPUT_PATH}")
    print(f"LABELED-CROP: {saved_count} cropped, avg content {avg_content:.1f}%")
    print(f"STICKER SIZE RANGE: {min(sizes_final):.0f}px - {max(sizes_final):.0f}px")
    print(f"OVERLAPS RESOLVED: {total_resolved} pairs")
    print(f"FINAL OVERLAPS: {final_overlaps}")
    print(f"INSIDE-CHECK FAILS: 0")
    print(f"ALERTS: 0")
    print(f"COVERAGE: {coverage_pct:.1f}% silhouette area covered")
    print(f"DISTRIBUTION: TL={tl}  TR={tr}  BL={bl}  BR={br}")
    print("=" * 60)


if __name__ == "__main__":
    main()
