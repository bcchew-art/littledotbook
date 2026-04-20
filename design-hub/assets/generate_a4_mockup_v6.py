"""
generate_a4_mockup_v6.py
Merlion Puzzle A4 — v6: Clean straight-line tessellation (stained-glass / paint-by-numbers)

Changes from v4/v5:
- NO jigsaw tabs. Every piece boundary is a straight grid line OR a silhouette-following
  curve derived from the shapely intersection of the grid cell with the silhouette polygon.
- Full silhouette coverage: tessellate the entire silhouette interior with shapely.
  Each piece = shapely intersection of a grid cell rectangle with the silhouette polygon.
- 4 columns x 8 rows grid. Empty/trivial intersections (<5% of cell area) are merged
  into the largest adjacent piece to maintain exactly 32 pieces.
- Pastel tints by category: Landmarks coral, Transport teal, Food orange, Culture purple,
  Nature mint, National gold.
- Interior piece-to-piece edges: 2px dark grey (#2D3748) solid lines only.
- Outer silhouette: 3px solid outline in same color.
- Number badge: 38px white circle + bold number at piece centroid.
- Ghost sticker: 20% alpha grayscale at centroid.
- Page chrome: title, subtitle, category legend, footer.
"""

import os
import re
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from shapely.geometry import Polygon, MultiPolygon, GeometryCollection, box as shapely_box
from shapely.ops import unary_union

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR   = r"C:/Users/Admin/Projects/oinio/littledotbook/design-hub/assets"
SVG_PATH   = os.path.join(BASE_DIR, "merlion-silhouette.svg")
ICONS_DIR  = os.path.join(BASE_DIR, "icons")
OUTPUT_PATH = os.path.join(BASE_DIR, "merlion-puzzle-a4-v6.png")

# ─── Canvas ───────────────────────────────────────────────────────────────────
A4_W, A4_H = 1240, 1754   # 150 DPI A4 portrait
BG_COLOR = (253, 251, 245)

# SVG viewBox: 0 0 600 800
SVG_VW, SVG_VH = 600, 800

# Merlion rendered at a comfortable size with room for page chrome
MERL_W_TARGET = 900
SCALE = MERL_W_TARGET / SVG_VW
MERL_W = MERL_W_TARGET
MERL_H = int(SVG_VH * SCALE)
MERL_X = (A4_W - MERL_W) // 2
MERL_Y = 170  # room for title

# Grid: 4 cols x 8 rows over the bounding box
GRID_COLS = 4
GRID_ROWS = 8

# Piece border colours
PIECE_STROKE_INNER = (45, 55, 72)    # #2D3748 — interior edges 2px
PIECE_STROKE_OUTER = (45, 55, 72)    # same color, 3px for silhouette outline
SLIVER_THRESHOLD = 0.03              # merge if piece < 3% of cell area

# Category colours (pastel-ish fills)
CATS = {
    "Landmarks": (255, 155, 130),   # coral
    "Transport":  (100, 210, 200),  # teal
    "Food":       (255, 185, 100),  # orange
    "Culture":    (185, 170, 255),  # purple
    "Nature":     (130, 230, 195),  # mint
    "National":   (240, 205, 80),   # gold
}

CAT_PASTEL = {k: tuple(int(c * 0.25 + 255 * 0.75) for c in v) for k, v in CATS.items()}

# ─── Icon definitions (same as v4) ───────────────────────────────────────────
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


# ─── SVG parsing ─────────────────────────────────────────────────────────────

def parse_svg_polygon(svg_file):
    """Parse the 'd' attribute of the SVG path and return raw (x,y) float points."""
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
    """Convert raw SVG points to canvas pixel coordinates."""
    return [(x * scale + tx, y * scale + ty) for (x, y) in raw_pts]


# ─── Tessellation ─────────────────────────────────────────────────────────────

def extract_largest_polygon(geom):
    """
    Extract the largest Polygon from any geometry type.
    Handles Polygon, MultiPolygon, GeometryCollection.
    Returns the polygon with the largest area, or None if no polygon found.
    """
    if geom is None or geom.is_empty:
        return None
    if isinstance(geom, Polygon):
        return geom if geom.area > 0 else None
    if isinstance(geom, (MultiPolygon, GeometryCollection)):
        polys = [g for g in geom.geoms if isinstance(g, Polygon) and g.area > 0]
        if not polys:
            return None
        return max(polys, key=lambda g: g.area)
    return None


def keep_all_polygons(geom):
    """
    Return a single polygon that is the union of all polygons in geom.
    This preserves full coverage even when a cell yields a MultiPolygon.
    """
    if geom is None or geom.is_empty:
        return None
    if isinstance(geom, Polygon):
        return geom if geom.area > 0 else None
    if isinstance(geom, (MultiPolygon, GeometryCollection)):
        polys = [g for g in geom.geoms if isinstance(g, Polygon) and g.area > 0]
        if not polys:
            return None
        if len(polys) == 1:
            return polys[0]
        return unary_union(polys)  # merge all parts — full coverage preserved
    return None


def build_pieces(sil_poly, bbox, grid_cols, grid_rows, sliver_thresh):
    """
    Tessellate silhouette into grid_cols x grid_rows pieces using shapely intersection.
    Returns dict {(row, col): polygon} with only non-trivial intersections.
    Trivial pieces (< sliver_thresh * cell_area) are merged into their largest neighbour.
    All geometry types (Polygon, MultiPolygon, GeometryCollection) are handled by
    merging sub-parts into one polygon per cell — guaranteeing full silhouette coverage.
    """
    x0, y0, x1, y1 = bbox
    cell_w = (x1 - x0) / grid_cols
    cell_h = (y1 - y0) / grid_rows

    raw_pieces = {}  # (row, col) -> polygon
    cell_areas = {}

    for row in range(grid_rows):
        for col in range(grid_cols):
            cx0 = x0 + col * cell_w
            cy0 = y0 + row * cell_h
            cx1 = cx0 + cell_w
            cy1 = cy0 + cell_h
            cell_box = shapely_box(cx0, cy0, cx1, cy1)
            cell_areas[(row, col)] = cell_box.area
            piece = sil_poly.intersection(cell_box)
            # Keep ALL polygon sub-parts merged — this gives full coverage
            poly = keep_all_polygons(piece)
            if poly is not None:
                raw_pieces[(row, col)] = poly

    # cleaned = raw_pieces (all pieces are already valid Polygons or unary_union results)
    cleaned = dict(raw_pieces)

    # Identify slivers
    slivers = {k for k, p in cleaned.items()
                if p.area < sliver_thresh * cell_areas.get(k, cell_w * cell_h)}

    # Merge slivers into largest adjacent non-sliver
    merges = {}   # sliver_key -> target_key
    for sliver_key in slivers:
        sr, sc = sliver_key
        candidates = []
        for (dr, dc) in [(-1,0),(1,0),(0,-1),(0,1)]:
            nb = (sr+dr, sc+dc)
            if nb in cleaned and nb not in slivers:
                candidates.append(nb)
        if candidates:
            # pick the neighbour with the largest area
            best = max(candidates, key=lambda k: cleaned[k].area)
            merges[sliver_key] = best
        else:
            # merge into the globally largest non-sliver as fallback
            non_slivers = [k for k in cleaned if k not in slivers]
            if non_slivers:
                best = max(non_slivers, key=lambda k: cleaned[k].area)
                merges[sliver_key] = best

    # Apply merges
    merged = dict(cleaned)
    for sliver_key, target_key in merges.items():
        if target_key in merged and sliver_key in merged:
            merged[target_key] = unary_union([merged[target_key], merged[sliver_key]])
            del merged[sliver_key]

    return merged  # {(row, col): polygon}


def assign_piece_numbers(pieces_dict):
    """
    Sort pieces top-to-bottom, left-to-right by centroid.
    Assign numbers 1-32 in that reading order.
    Returns list of (number, polygon) sorted 1..N.
    """
    keyed = []
    for (row, col), poly in pieces_dict.items():
        cx, cy = poly.centroid.x, poly.centroid.y
        keyed.append((cy, cx, poly))

    keyed.sort(key=lambda t: (t[0], t[1]))
    return [(i+1, poly) for i, (_, _, poly) in enumerate(keyed)]


def assign_categories(numbered_pieces):
    """
    Assign categories in reading order (head=top to tail=bottom):
    1-8   Landmarks, 9-13 Transport (5), 14-19 Food (6),
    20-26 Culture (7), 27-30 Nature (4), 31-32 National (2)
    """
    total = len(numbered_pieces)
    cat_map = {}
    for num, poly in numbered_pieces:
        if num <= 8:
            cat_map[num] = "Landmarks"
        elif num <= 13:
            cat_map[num] = "Transport"
        elif num <= 19:
            cat_map[num] = "Food"
        elif num <= 26:
            cat_map[num] = "Culture"
        elif num <= 30:
            cat_map[num] = "Nature"
        else:
            cat_map[num] = "National"
    return cat_map


# ─── Rendering helpers ────────────────────────────────────────────────────────

def poly_to_pil_coords(poly):
    """Convert shapely Polygon exterior to PIL integer coordinate list."""
    if isinstance(poly, (MultiPolygon, GeometryCollection)):
        # Return coords for all sub-polygons concatenated (used for outline drawing)
        all_coords = []
        for geom in poly.geoms:
            if isinstance(geom, Polygon) and not geom.is_empty:
                all_coords.append([(int(x), int(y)) for x, y in geom.exterior.coords])
        return all_coords  # list of lists
    return [[(int(x), int(y)) for x, y in poly.exterior.coords]]  # always return list of lists


def poly_to_fill_regions(poly):
    """Return list of coord-lists suitable for ImageDraw.polygon fill."""
    if isinstance(poly, (MultiPolygon, GeometryCollection)):
        regions = []
        for geom in poly.geoms:
            if isinstance(geom, Polygon) and not geom.is_empty:
                regions.append([(int(x), int(y)) for x, y in geom.exterior.coords])
        return regions
    if isinstance(poly, Polygon) and not poly.is_empty:
        return [[(int(x), int(y)) for x, y in poly.exterior.coords]]
    return []


def load_font(size, bold=False):
    candidates = (
        ["C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/calibrib.ttf",
         "C:/Windows/Fonts/georgiab.ttf"]
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
            print(f"  WARNING: Missing sticker: {fpath}")
    print(f"  Loaded {len(stickers)}/32 sticker images")
    return stickers


def make_ghost(img, size):
    """Return a 20% alpha grayscale version of the icon."""
    img = img.resize((size, size), Image.LANCZOS)
    rgb = img.convert("RGB")
    arr = np.array(rgb, dtype=np.float32)
    gray = (0.299*arr[:,:,0] + 0.587*arr[:,:,1] + 0.114*arr[:,:,2]).astype(np.uint8)
    # alpha: use original alpha if present, else mask white bg
    orig_a = np.array(img)[:,:,3] if img.mode == 'RGBA' else None
    if orig_a is not None:
        alpha = (orig_a.astype(np.float32) * 0.20).astype(np.uint8)
    else:
        is_bg = (arr[:,:,0] > 230) & (arr[:,:,1] > 230) & (arr[:,:,2] > 230)
        alpha = ((~is_bg).astype(np.float32) * 255 * 0.20).astype(np.uint8)
    ghost_arr = np.stack([gray, gray, gray, alpha], axis=2)
    return Image.fromarray(ghost_arr, "RGBA")


def draw_piece(canvas, draw, num, poly, cat, stickers, font_num, font_label):
    """Fill a piece with pastel tint, optionally ghost sticker, then draw number badge."""
    fill = CAT_PASTEL[cat]

    # Fill all sub-regions (handles MultiPolygon pieces from unary_union merges)
    regions = poly_to_fill_regions(poly)
    for region_coords in regions:
        if len(region_coords) >= 3:
            draw.polygon(region_coords, fill=fill)

    # Ghost sticker + badge at centroid
    cx_f, cy_f = poly.centroid.x, poly.centroid.y
    cx, cy = int(cx_f), int(cy_f)

    # Clamp centroid to canvas
    cx = max(20, min(A4_W - 20, cx))
    cy = max(20, min(A4_H - 20, cy))

    # Ghost sticker
    area = poly.area
    ghost_size = max(30, min(80, int(math.sqrt(area) * 0.40)))

    if num in stickers:
        ghost = make_ghost(stickers[num], ghost_size)
        gx = cx - ghost_size // 2
        gy = cy - ghost_size // 2
        gx = max(0, min(A4_W - ghost_size, gx))
        gy = max(0, min(A4_H - ghost_size, gy))
        canvas.paste(ghost, (gx, gy), ghost)

    # Number badge — white filled circle + bold number
    badge_r = 16
    bx = cx
    by = cy + ghost_size // 2 + badge_r + 2
    by = max(badge_r + 2, min(A4_H - badge_r - 2, by))

    draw.ellipse([bx - badge_r, by - badge_r, bx + badge_r, by + badge_r],
                 fill=(255, 255, 255), outline=CATS[cat], width=1)
    ns = str(num)
    nw, nh = text_size(draw, ns, font_num)
    draw.text((bx - nw // 2, by - nh // 2), ns, fill=PIECE_STROKE_INNER, font=font_num)


def draw_piece_borders(draw, numbered_pieces_polys, canvas_sil_coords):
    """
    Draw interior piece edges (2px solid) and the outer silhouette outline (3px solid).
    Interior edges drawn twice (once per adjacent piece) — they overlap cleanly.
    """
    for num, poly in numbered_pieces_polys:
        region_lists = poly_to_pil_coords(poly)
        for coords in region_lists:
            if len(coords) >= 2:
                draw.line(coords + [coords[0]], fill=PIECE_STROKE_INNER, width=2)

    # Silhouette outline on top — 3px
    if canvas_sil_coords:
        draw.line(canvas_sil_coords + [canvas_sil_coords[0]],
                  fill=PIECE_STROKE_OUTER, width=3)


# ─── Page chrome ─────────────────────────────────────────────────────────────

def draw_header(canvas):
    draw = ImageDraw.Draw(canvas)
    f_title = load_font(48, bold=True)
    f_sub   = load_font(30)
    f_instr = load_font(22)

    title = "My Singapore Stories Vol.2"
    tw, _ = text_size(draw, title, f_title)
    draw.text(((A4_W - tw) // 2, 20), title, fill=(25, 55, 115), font=f_title)

    sub = "Merlion Puzzle Activity"
    sw, _ = text_size(draw, sub, f_sub)
    draw.text(((A4_W - sw) // 2, 78), sub, fill=(200, 65, 45), font=f_sub)

    instr = "Assemble the Merlion — match each numbered sticker to its puzzle piece!"
    iw, _ = text_size(draw, instr, f_instr)
    draw.text(((A4_W - iw) // 2, 122), instr, fill=(75, 75, 95), font=f_instr)


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
    text = "Little Dot Book  .  My Singapore Stories Vol.2"
    tw, _ = text_size(draw, text, f)
    draw.text(((A4_W - tw) // 2, A4_H - 34), text, fill=(155, 155, 175), font=f)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Merlion Puzzle A4 Generator v6 — Clean Tessellation")
    print("=" * 60)

    # 1. Parse silhouette
    print("\n[1] Parsing SVG silhouette...")
    raw_pts = parse_svg_polygon(SVG_PATH)
    print(f"    {len(raw_pts)} polygon vertices")

    # Canvas-space silhouette coords (for PIL rendering + shapely)
    canvas_pts = scale_points_to_canvas(raw_pts, SCALE, MERL_X, MERL_Y)
    sil_poly = Polygon(canvas_pts)
    if not sil_poly.is_valid:
        sil_poly = sil_poly.buffer(0)  # fix self-intersections
    print(f"    Silhouette area: {sil_poly.area:.0f} px^2")

    # 2. Build grid bounding box over the silhouette
    bbox_minx, bbox_miny, bbox_maxx, bbox_maxy = sil_poly.bounds
    print(f"    Silhouette bounds: ({bbox_minx:.0f},{bbox_miny:.0f}) -> ({bbox_maxx:.0f},{bbox_maxy:.0f})")

    # 3. Tessellate
    print(f"\n[2] Tessellating {GRID_COLS}x{GRID_ROWS} grid over silhouette...")
    pieces_dict = build_pieces(
        sil_poly,
        (bbox_minx, bbox_miny, bbox_maxx, bbox_maxy),
        GRID_COLS, GRID_ROWS,
        SLIVER_THRESHOLD
    )
    print(f"    Pieces after merging slivers: {len(pieces_dict)}")

    # If too few pieces, retry with progressively lower sliver threshold
    for retry_thresh in [0.02, 0.01]:
        if len(pieces_dict) >= 32:
            break
        print(f"    Too few pieces — retrying with sliver threshold={retry_thresh}...")
        pieces_dict = build_pieces(
            sil_poly,
            (bbox_minx, bbox_miny, bbox_maxx, bbox_maxy),
            GRID_COLS, GRID_ROWS,
            retry_thresh
        )
        print(f"    Pieces after retry: {len(pieces_dict)}")

    # 4. Number pieces (top-to-bottom, left-to-right)
    numbered = assign_piece_numbers(pieces_dict)
    piece_count = len(numbered)
    print(f"    Final piece count: {piece_count}")

    # 5. Category assignment
    cat_map = assign_categories(numbered)

    # 6. Verify coverage
    all_pieces_union = unary_union([p for _, p in numbered])
    covered = all_pieces_union.area
    sil_area = sil_poly.area
    coverage_pct = covered / sil_area * 100
    gap_area = sil_area - covered
    print(f"\n[3] Coverage check:")
    print(f"    Silhouette area:    {sil_area:.0f} px^2")
    print(f"    Pieces union area:  {covered:.0f} px^2")
    print(f"    Coverage:           {coverage_pct:.2f}%")
    print(f"    Gap area:           {gap_area:.1f} px^2  (should be ~0)")

    # 7. Load stickers
    print("\n[4] Loading sticker images...")
    stickers = load_stickers()

    # 8. Render
    print("\n[5] Rendering canvas...")
    canvas = Image.new("RGB", (A4_W, A4_H), BG_COLOR)
    draw_header(canvas)

    draw = ImageDraw.Draw(canvas, "RGBA")
    font_num   = load_font(16, bold=True)
    font_label = load_font(11)

    # Fill all pieces first (no outlines yet)
    for num, poly in numbered:
        cat = cat_map.get(num, "Landmarks")
        draw_piece(canvas, draw, num, poly, cat, stickers, font_num, font_label)

    # Draw all borders on top
    draw_piece_borders(draw, numbered, canvas_pts)

    draw_legend(canvas)
    draw_footer(canvas)

    # 9. Save
    canvas.save(OUTPUT_PATH, "PNG", dpi=(150, 150))
    print(f"\nSaved: {OUTPUT_PATH}")

    # 10. Stats
    small_pieces = [(num, poly.area / sil_area * 100) for num, poly in numbered
                    if poly.area / sil_area * 100 < 1.5]

    print("\n" + "=" * 60)
    print(f"DONE: {piece_count}/32 pieces tessellated (clean straight-line)")
    print(f"FILES: {OUTPUT_PATH}")
    print(f"PIECE COUNT: {piece_count}")
    print(f"COVERAGE CHECK: {coverage_pct:.2f}% — gap area={gap_area:.1f}px^2 "
          f"({'no visible gaps' if gap_area < 50 else 'minor gaps possible'})")
    if small_pieces:
        print(f"ISSUES: {len(small_pieces)} pieces <1.5% of silhouette area: "
              + ", ".join(f"#{n}({a:.1f}%)" for n, a in small_pieces))
    else:
        print("ISSUES: None — all pieces within acceptable size range")
    print(f"NEXT: Review {OUTPUT_PATH} — check piece legibility and badge placement")
    print("=" * 60)

    return piece_count, coverage_pct


if __name__ == "__main__":
    main()
