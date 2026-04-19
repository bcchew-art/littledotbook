"""
generate_a4_mockup_v5.py
Merlion Puzzle — A4 print mockup with proper jigsaw tessellation.

Algorithm:
1. Parse SVG polygon → Shapely polygon (silhouette)
2. Scale silhouette to ~1100px wide, centered on A4 canvas with 80px top/bottom margins
3. Lay 4×8 rectangular grid over silhouette bounding box (32 cells)
4. Generate shared jigsaw edges (cubic bezier knobs) between adjacent cells — neighbors share exact same curve so pieces mesh perfectly
5. Clip each cell polygon to silhouette with Shapely intersection
6. If intersection count != 32, nudge grid and retry
7. Render each piece: pastel fill, dark stroke, dashed die-cut line, numbered badge, ghost sticker
8. Page chrome: title, subtitle, legend, footer
"""

import os
import re
import math
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from shapely.geometry import Polygon, MultiPolygon, LinearRing
from shapely.ops import unary_union

# ── Reproducibility ──────────────────────────────────────────────────────────
random.seed(42)

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = r"C:/Users/Admin/Projects/oinio/littledotbook/design-hub/assets"
SVG_PATH  = os.path.join(BASE_DIR, "merlion-silhouette.svg")
ICONS_DIR = os.path.join(BASE_DIR, "icons")
OUTPUT_PATH = os.path.join(BASE_DIR, "merlion-puzzle-a4-v5.png")

# ── Canvas ───────────────────────────────────────────────────────────────────
A4_W, A4_H = 1240, 1754
BG_COLOR   = (253, 251, 245)

# ── Grid spec ────────────────────────────────────────────────────────────────
COLS = 4
ROWS = 8
TARGET_PIECES = 32

# ── Category palette (pastel) ────────────────────────────────────────────────
CATS = {
    "Landmarks": (0xFF, 0xB5, 0xA7),   # coral
    "Transport":  (0xA7, 0xE8, 0xD9),  # teal
    "Food":       (0xFF, 0xCB, 0x8E),  # orange
    "Culture":    (0xD4, 0xB5, 0xE8),  # purple
    "Nature":     (0xB5, 0xE8, 0xC9),  # mint
    "National":   (0xFF, 0xE0, 0x8A),  # gold
}

# ── Icon definitions ──────────────────────────────────────────────────────────
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
    (14, "Chicken Rice",      "Transport"),   # 14 maps to transport per icons list (no #14 Culture)
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
    (26, "Lion Dance",        "Nature"),
    (27, "Botanic Gardens",   "Nature"),
    (28, "Orchid",            "Nature"),
    (29, "Otters",            "Nature"),
    (30, "Community Cat",     "Nature"),
    (31, "Singapore Flag",    "National"),
    (32, "Fireworks",         "National"),
]

# Override categories per spec: 1-8 Landmarks, 9-14 Transport, 15-20 Food, 21-25 Culture, 26-29 Nature, 30-32 National
CAT_BY_NUM = {}
for i in range(1, 9):   CAT_BY_NUM[i] = "Landmarks"
for i in range(9, 15):  CAT_BY_NUM[i] = "Transport"
for i in range(15, 21): CAT_BY_NUM[i] = "Food"
for i in range(21, 26): CAT_BY_NUM[i] = "Culture"
for i in range(26, 30): CAT_BY_NUM[i] = "Nature"
for i in range(30, 33): CAT_BY_NUM[i] = "National"

ICON_LOOKUP = {num: (name, CAT_BY_NUM[num]) for (num, name, _) in ICONS}

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


# ── SVG parsing ───────────────────────────────────────────────────────────────

def parse_svg_polygon(svg_file):
    """Parse the SVG 'd' attribute as absolute M/L/Z path; return list of (x,y) floats."""
    with open(svg_file, "r") as f:
        content = f.read()
    m = re.search(r'\bd="(M[^"]+)"', content, re.DOTALL)
    if not m:
        raise ValueError("Could not find path 'd' in SVG")
    d = m.group(1)
    # Extract all coordinate pairs
    pairs = re.findall(r'([-\d.]+),([-\d.]+)', d)
    return [(float(x), float(y)) for x, y in pairs]


def build_silhouette(svg_w=600, svg_h=800, target_w=1100, top_margin=80, bottom_margin=80):
    """
    Parse SVG, scale uniformly so width = target_w, center horizontally on A4,
    top of silhouette at top_margin + title_area.
    Returns: shapely Polygon (canvas coords), scale, tx, ty
    """
    raw_pts = parse_svg_polygon(SVG_PATH)
    print(f"  Parsed {len(raw_pts)} polygon vertices from SVG")

    # Raw bounds
    xs = [p[0] for p in raw_pts]
    ys = [p[1] for p in raw_pts]
    raw_x0, raw_x1 = min(xs), max(xs)
    raw_y0, raw_y1 = min(ys), max(ys)
    raw_w = raw_x1 - raw_x0
    raw_h = raw_y1 - raw_y0
    print(f"  SVG bounds: x={raw_x0:.1f}–{raw_x1:.1f}, y={raw_y0:.1f}–{raw_y1:.1f}")
    print(f"  SVG size: {raw_w:.1f} x {raw_h:.1f}")

    scale = target_w / raw_w
    scaled_h = raw_h * scale
    print(f"  Scale: {scale:.4f}, scaled silhouette: {target_w:.0f} x {scaled_h:.0f}")

    # Title area ~160px, center horizontally
    title_area = 160
    tx = (A4_W - target_w) / 2 - raw_x0 * scale
    # Position so top of silhouette is at title_area + top_margin
    ty = title_area + top_margin - raw_y0 * scale

    canvas_pts = [(x * scale + tx, y * scale + ty) for (x, y) in raw_pts]
    poly = Polygon(canvas_pts)
    if not poly.is_valid:
        poly = poly.buffer(0)
    print(f"  Silhouette polygon valid: {poly.is_valid}, area: {poly.area:.0f} px²")
    return poly, scale, tx, ty, canvas_pts


# ── Jigsaw edge generation ────────────────────────────────────────────────────

def jigsaw_knob_points(p0, p1, direction=1, n_pts=32):
    """
    Generate points for a jigsaw knob between p0 and p1.
    direction=+1 means knob protrudes toward 'right' of the p0→p1 vector,
    direction=-1 means inward (blank).
    Returns list of (x,y) points approximating the bezier curve.

    Classic jigsaw shape: slight neck narrowing before/after the round bump.
    """
    dx = p1[0] - p0[0]
    dy = p1[1] - p0[1]
    length = math.hypot(dx, dy)

    if length < 1e-6:
        return [p0, p1]

    # Unit vectors along and perpendicular to the edge
    ux, uy = dx / length, dy / length
    # Perpendicular: rotate 90° CCW
    nx, ny = -uy, ux

    # Knob parameters as fraction of edge length
    # The knob occupies the center 30% of the edge width
    # Neck width: 10% of edge length; knob height: 22% of edge length
    neck_frac  = 0.10   # width of neck (each side of center)
    bump_frac  = 0.30   # total width of bump
    bump_h_frac = 0.22  # height of bump (perpendicular to edge)
    neck_h_frac = 0.08  # slight neck constriction height

    # Key fractions along the edge: start_neck, center, end_neck
    f_neck0  = 0.5 - bump_frac / 2
    f_bump0  = 0.5 - neck_frac
    f_center = 0.5
    f_bump1  = 0.5 + neck_frac
    f_neck1  = 0.5 + bump_frac / 2

    # Bezier curve: use cubic bezier approximation
    # Points along the edge at key fractions
    def pt_along(f, perp_offset=0.0):
        return (
            p0[0] + f * dx + perp_offset * nx * length,
            p0[1] + f * dy + perp_offset * ny * length,
        )

    # Build the knob path using cubic bezier segments
    # We'll use numpy to sample cubic beziers
    # Segment 1: p0 → neck0 (straight)
    # Segment 2: neck0 → bump: cubic bezier with neck constriction
    # Segment 3: bump → bump center: cubic bezier round top
    # Segment 4: bump center → neck1: mirror
    # Segment 5: neck1 → p1: straight

    d = direction

    # Control points for the knob shape
    # Pt A: start of neck (slightly inward for neck constriction)
    A = pt_along(f_neck0, -d * neck_h_frac)
    # Pt B: base of bump on near side
    B = pt_along(f_bump0,  d * 0.0)
    # Pt C: top of bump on near side
    C = pt_along(f_bump0,  d * bump_h_frac)
    # Pt D: center top of bump
    D = pt_along(f_center, d * bump_h_frac)
    # Pt E: top of bump far side
    E = pt_along(f_bump1,  d * bump_h_frac)
    # Pt F: base of bump far side
    F = pt_along(f_bump1,  d * 0.0)
    # Pt G: end of neck (slightly inward)
    G = pt_along(f_neck1, -d * neck_h_frac)

    def cubic_bezier_pts(pa, pb, pc, pd, n=8):
        """Sample cubic bezier with control points pa, pb, pc, pd."""
        pts = []
        for i in range(n + 1):
            t = i / n
            mt = 1 - t
            x = mt**3*pa[0] + 3*mt**2*t*pb[0] + 3*mt*t**2*pc[0] + t**3*pd[0]
            y = mt**3*pa[1] + 3*mt**2*t*pb[1] + 3*mt*t**2*pc[1] + t**3*pd[1]
            pts.append((x, y))
        return pts

    # Assemble: straight to neck0, then bezier through knob, straight to p1
    pts = []

    # Straight segment: p0 → A
    steps = max(2, int(f_neck0 * n_pts))
    for i in range(steps):
        t = i / steps
        pts.append((p0[0] + t * (A[0] - p0[0]), p0[1] + t * (A[1] - p0[1])))

    # Bezier: A → C (entry arc with neck constriction)
    ctrl1 = pt_along(f_neck0, d * 0.0)   # pull away from neck constriction
    ctrl2 = pt_along(f_bump0 - 0.03, d * bump_h_frac * 0.5)
    pts += cubic_bezier_pts(A, ctrl1, ctrl2, C, n=6)

    # Bezier: C → D → E (round top of bump)
    ctrl_cd1 = pt_along(f_bump0 + 0.02, d * bump_h_frac * 1.1)
    ctrl_de1 = pt_along(f_center, d * bump_h_frac * 1.05)
    ctrl_de2 = pt_along(f_center, d * bump_h_frac * 1.05)
    ctrl_ef1 = pt_along(f_bump1 - 0.02, d * bump_h_frac * 1.1)
    # One cubic from C to D
    pts += cubic_bezier_pts(C, ctrl_cd1, ctrl_de1, D, n=6)
    # One cubic from D to E
    pts += cubic_bezier_pts(D, ctrl_de2, ctrl_ef1, E, n=6)

    # Bezier: E → G (exit arc with neck constriction, mirror of entry)
    ctrl_eg1 = pt_along(f_bump1 + 0.03, d * bump_h_frac * 0.5)
    ctrl_eg2 = pt_along(f_neck1, d * 0.0)
    pts += cubic_bezier_pts(E, ctrl_eg1, ctrl_eg2, G, n=6)

    # Straight segment: G → p1
    pts.append(G)
    pts.append(p1)

    return pts


def build_cell_polygon(r, c, grid_x0, grid_y0, cell_w, cell_h,
                       h_edges, v_edges):
    """
    Build the polygon for cell (r, c) using shared edge curves.

    Edge storage:
      h_edges[(r, c)] = points for horizontal edge between row r-1 and row r, at column c
                         Points go LEFT → RIGHT (increasing x)
      v_edges[(r, c)] = points for vertical edge between col c-1 and col c, at row r
                         Points go TOP → BOTTOM (increasing y)

    Cell boundary traversal (clockwise):
      Top edge:    h_edges[(r,   c)] — left to right  (shared with row above)
      Right edge:  v_edges[(r, c+1)] — top to bottom  (shared with col to right)
      Bottom edge: h_edges[(r+1, c)] — right to left  (reversed, shared with row below)
      Left edge:   v_edges[(r,   c)] — bottom to top  (reversed, shared with col to left)
    """
    pts = []

    # Top edge (left to right)
    top = h_edges[(r, c)]
    pts.extend(top)

    # Right edge (top to bottom)
    right = v_edges[(r, c + 1)]
    pts.extend(right[1:])  # skip first point (already added as last of top)

    # Bottom edge (right to left — reverse of h_edges[(r+1, c)])
    bottom = h_edges[(r + 1, c)]
    pts.extend(reversed(bottom[1:]))

    # Left edge (bottom to top — reverse of v_edges[(r, c)])
    left = v_edges[(r, c)]
    pts.extend(list(reversed(left))[1:])

    # Close (back to first pt of top)
    # Don't re-add pts[0], Shapely handles closure

    return Polygon(pts)


def build_jigsaw_grid(grid_x0, grid_y0, cell_w, cell_h, cols, rows):
    """
    Build all shared edge curves for a cols×rows jigsaw grid.
    Returns h_edges, v_edges dicts.
    """
    # h_edges[(r, c)] = horizontal edge between row r-1 and row r, for column c
    #   r=0 is top border, r=rows is bottom border
    #   Points: left corner (grid_x0 + c*cell_w, grid_y0 + r*cell_h) → right corner
    h_edges = {}
    for r in range(rows + 1):
        for c in range(cols):
            x0 = grid_x0 + c * cell_w
            x1 = grid_x0 + (c + 1) * cell_w
            y  = grid_y0 + r * cell_h
            p0 = (x0, y)
            p1 = (x1, y)

            if r == 0 or r == rows:
                # Border: straight
                h_edges[(r, c)] = [p0, p1]
            else:
                # Interior: jigsaw knob
                # direction: +1 = knob goes downward (positive y), -1 = upward
                # Randomize per edge (reproducible via seed)
                direction = random.choice([-1, 1])
                pts = jigsaw_knob_points(p0, p1, direction=direction)
                h_edges[(r, c)] = pts

    # v_edges[(r, c)] = vertical edge between col c-1 and col c, for row r
    #   c=0 is left border, c=cols is right border
    #   Points: top corner → bottom corner
    v_edges = {}
    for c in range(cols + 1):
        for r in range(rows):
            x  = grid_x0 + c * cell_w
            y0 = grid_y0 + r * cell_h
            y1 = grid_y0 + (r + 1) * cell_h
            p0 = (x, y0)
            p1 = (x, y1)

            if c == 0 or c == cols:
                # Border: straight
                v_edges[(r, c)] = [p0, p1]
            else:
                # Interior: jigsaw knob
                # For vertical edges, perpendicular is horizontal
                # direction: +1 = knob goes rightward, -1 = leftward
                direction = random.choice([-1, 1])
                pts = jigsaw_knob_points(p0, p1, direction=direction)
                v_edges[(r, c)] = pts

    return h_edges, v_edges


# ── Font helpers ─────────────────────────────────────────────────────────────

def load_font(size, bold=False):
    candidates = (
        ["C:/Windows/Fonts/georgiab.ttf", "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/calibrib.ttf"]
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


# ── Sticker loading ───────────────────────────────────────────────────────────

def load_stickers():
    stickers = {}
    for icon_id, fname in FILENAME_MAP.items():
        fpath = os.path.join(ICONS_DIR, fname)
        if os.path.exists(fpath):
            try:
                stickers[icon_id] = Image.open(fpath).convert("RGBA")
            except Exception as e:
                print(f"  WARNING sticker {icon_id}: {e}")
        else:
            print(f"  WARNING missing sticker: {fpath}")
    print(f"  Loaded {len(stickers)}/32 stickers")
    return stickers


def make_ghost(img, w, h):
    """Return a grayscale 20%-alpha version of img sized w×h."""
    img = img.resize((w, h), Image.LANCZOS)
    arr = np.array(img.convert("RGBA"), dtype=np.float32)
    # Detect foreground (non-white/non-transparent)
    alpha = arr[:, :, 3]
    gray = 0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]
    gray_u8 = gray.astype(np.uint8)
    new_alpha = (alpha * 0.20).astype(np.uint8)
    ghost_arr = np.stack([gray_u8, gray_u8, gray_u8, new_alpha], axis=2)
    return Image.fromarray(ghost_arr, "RGBA")


# ── Polygon → PIL drawing ─────────────────────────────────────────────────────

def shapely_to_pil_coords(poly):
    """Convert shapely exterior coords to PIL flat tuple list."""
    coords = list(poly.exterior.coords)
    return [(int(x), int(y)) for x, y in coords]


def draw_dashed_polygon(draw, coords, color, width=1, dash=6, gap=4):
    """Draw a dashed outline following polygon edges."""
    n = len(coords)
    period = dash + gap
    for i in range(n):
        p0 = coords[i]
        p1 = coords[(i + 1) % n]
        dx = p1[0] - p0[0]
        dy = p1[1] - p0[1]
        length = math.hypot(dx, dy)
        if length < 1:
            continue
        ux, uy = dx / length, dy / length
        pos = 0.0
        drawing = True
        while pos < length:
            seg_len = dash if drawing else gap
            end_pos = min(pos + seg_len, length)
            if drawing:
                sx = p0[0] + pos * ux
                sy = p0[1] + pos * uy
                ex = p0[0] + end_pos * ux
                ey = p0[1] + end_pos * uy
                draw.line([(sx, sy), (ex, ey)], fill=color, width=width)
            pos = end_pos
            drawing = not drawing


def render_piece(canvas, draw, piece_poly, icon_num, stickers):
    """Render one puzzle piece onto the canvas."""
    name, cat = ICON_LOOKUP[icon_num]
    fill_color = CATS[cat]

    coords = shapely_to_pil_coords(piece_poly)
    if len(coords) < 3:
        return

    # -- Fill --
    draw.polygon(coords, fill=fill_color)

    # -- Ghost sticker (20% alpha grayscale) --
    if icon_num in stickers:
        bbox = piece_poly.bounds  # (minx, miny, maxx, maxy)
        pw = int(bbox[2] - bbox[0])
        ph = int(bbox[3] - bbox[1])
        ghost_size = max(20, min(pw, ph) - 20)
        centroid = piece_poly.centroid
        cx_int, cy_int = int(centroid.x), int(centroid.y)
        ghost = make_ghost(stickers[icon_num], ghost_size, ghost_size)
        gx = cx_int - ghost_size // 2
        gy = cy_int - ghost_size // 2
        try:
            canvas.paste(ghost, (gx, gy), ghost)
        except Exception:
            pass

    # -- Dark grey 2px solid outline --
    draw.polygon(coords, outline=(55, 55, 55), width=2)

    # -- Dashed die-cut line (1px, inset 2px) --
    # Inset polygon slightly
    try:
        inset_poly = piece_poly.buffer(-2)
        if not inset_poly.is_empty and inset_poly.geom_type == 'Polygon':
            inset_coords = shapely_to_pil_coords(inset_poly)
            draw_dashed_polygon(draw, inset_coords, (120, 120, 120), width=1, dash=6, gap=4)
    except Exception:
        pass

    # -- Number badge --
    centroid = piece_poly.centroid
    cx_int, cy_int = int(centroid.x), int(centroid.y)
    badge_r = 19
    badge_box = [cx_int - badge_r, cy_int - badge_r, cx_int + badge_r, cy_int + badge_r]
    draw.ellipse(badge_box, fill=(255, 255, 255), outline=(55, 55, 55), width=1)

    font_num = load_font(18, bold=True)
    ns = str(icon_num)
    nw, nh = text_size(draw, ns, font_num)
    draw.text(
        (cx_int - nw // 2, cy_int - nh // 2 - 1),
        ns,
        fill=(30, 30, 30),
        font=font_num
    )


# ── Page chrome ───────────────────────────────────────────────────────────────

def draw_page_chrome(canvas):
    draw = ImageDraw.Draw(canvas)

    # Title
    f_title = load_font(36, bold=True)
    f_sub   = load_font(18)
    title = "Merlion Puzzle — My Singapore Stories"
    tw, _ = text_size(draw, title, f_title)
    draw.text(((A4_W - tw) // 2, 28), title, fill=(25, 55, 115), font=f_title)

    # Subtitle
    sub = "Match each sticker to its puzzle piece!"
    sw, _ = text_size(draw, sub, f_sub)
    draw.text(((A4_W - sw) // 2, 82), sub, fill=(90, 90, 110), font=f_sub)

    # Legend
    f_leg  = load_font(15)
    f_lhd  = load_font(15, bold=True)
    swatch = 14
    pad    = 6
    y_leg  = A4_H - 70

    items = list(CATS.items())
    total_w = sum(swatch + pad + text_size(draw, cat, f_leg)[0] + 20 for cat, _ in items)
    head = "Category key: "
    hw, _ = text_size(draw, head, f_lhd)
    x = (A4_W - total_w - hw) // 2
    draw.text((x, y_leg + 1), head, fill=(70, 70, 90), font=f_lhd)
    x += hw

    for cat, color in items:
        draw.rectangle([x, y_leg + 3, x + swatch, y_leg + swatch + 3], fill=color, outline=(80, 80, 80), width=1)
        cw, _ = text_size(draw, cat, f_leg)
        draw.text((x + swatch + pad, y_leg), cat, fill=(60, 60, 80), font=f_leg)
        x += swatch + pad + cw + 20

    # Footer
    f_foot = load_font(14)
    foot = "Little Dot Book  ·  Book 2"
    fw, _ = text_size(draw, foot, f_foot)
    draw.text(((A4_W - fw) // 2, A4_H - 32), foot, fill=(160, 160, 180), font=f_foot)


# ── Grid fitting ──────────────────────────────────────────────────────────────

def try_grid(silhouette_poly, grid_x0, grid_y0, cell_w, cell_h):
    """
    Attempt jigsaw grid at given position/size.
    Returns list of (piece_poly, grid_row, grid_col) for pieces with non-trivial intersection.
    """
    h_edges, v_edges = build_jigsaw_grid(grid_x0, grid_y0, cell_w, cell_h, COLS, ROWS)

    pieces = []
    for r in range(ROWS):
        for c in range(COLS):
            try:
                cell_poly = build_cell_polygon(r, c, grid_x0, grid_y0, cell_w, cell_h, h_edges, v_edges)
                if not cell_poly.is_valid:
                    cell_poly = cell_poly.buffer(0)

                intersection = cell_poly.intersection(silhouette_poly)

                if intersection.is_empty:
                    continue

                # Keep largest piece if MultiPolygon
                if intersection.geom_type == 'MultiPolygon':
                    parts = list(intersection.geoms)
                    intersection = max(parts, key=lambda p: p.area)

                # Must have meaningful area (> 5% of cell area)
                cell_area = cell_w * cell_h
                if intersection.area < cell_area * 0.05:
                    continue

                pieces.append((intersection, r, c))
            except Exception as e:
                print(f"    Cell ({r},{c}) error: {e}")
                continue

    return pieces, h_edges, v_edges


def assign_numbers(pieces):
    """
    Assign sticker numbers 1–N to pieces in reading order (top-to-bottom, left-to-right by centroid).
    """
    def sort_key(item):
        poly, r, c = item
        centroid = poly.centroid
        return (centroid.y, centroid.x)

    sorted_pieces = sorted(pieces, key=sort_key)
    return [(poly, num + 1) for num, (poly, r, c) in enumerate(sorted_pieces)]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Merlion Puzzle v5 — Jigsaw Tessellation")
    print("=" * 60)

    # 1. Build silhouette
    print("\n[1] Building silhouette...")
    silhouette_poly, scale, tx, ty, canvas_pts = build_silhouette(
        target_w=1100, top_margin=80, bottom_margin=80
    )

    sil_bounds = silhouette_poly.bounds  # (minx, miny, maxx, maxy)
    sil_w = sil_bounds[2] - sil_bounds[0]
    sil_h = sil_bounds[3] - sil_bounds[1]
    print(f"  Canvas bounds: x={sil_bounds[0]:.0f}–{sil_bounds[2]:.0f}, y={sil_bounds[1]:.0f}–{sil_bounds[3]:.0f}")
    print(f"  Silhouette: {sil_w:.0f} x {sil_h:.0f} px")

    # 2. Find grid that yields exactly 32 pieces
    print("\n[2] Finding 32-piece grid...")

    # Initial grid covers silhouette bounding box
    cell_w = sil_w / COLS
    cell_h = sil_h / ROWS
    grid_x0 = sil_bounds[0]
    grid_y0 = sil_bounds[1]

    print(f"  Cell size: {cell_w:.1f} x {cell_h:.1f} px")
    print(f"  Grid origin: ({grid_x0:.1f}, {grid_y0:.1f})")

    best_pieces = None
    best_h_edges = None
    best_v_edges = None
    best_count = 0

    # Try nudging grid to get exactly 32 pieces
    nudge_attempts = [
        (0, 0),
        (-cell_w * 0.1, 0), (cell_w * 0.1, 0),
        (0, -cell_h * 0.1), (0, cell_h * 0.1),
        (-cell_w * 0.15, -cell_h * 0.05),
        (cell_w * 0.15, -cell_h * 0.05),
        (-cell_w * 0.05, cell_h * 0.1),
        (cell_w * 0.05, cell_h * 0.1),
        # Try expanding grid slightly to ensure all 32 intersect
        (-cell_w * 0.05, -cell_h * 0.05),  # with larger cells
    ]

    # Also try with slightly different cell sizes
    size_variants = [
        (cell_w, cell_h),
        (cell_w * 1.05, cell_h * 1.05),
        (cell_w * 0.95, cell_h * 0.95),
        (cell_w * 1.1, cell_h * 1.0),
        (cell_w * 1.0, cell_h * 1.1),
    ]

    for cw, ch in size_variants:
        for dx, dy in nudge_attempts:
            gx0 = grid_x0 + dx - (cw - cell_w) * COLS / 2
            gy0 = grid_y0 + dy - (ch - cell_h) * ROWS / 2

            pieces, h_edges, v_edges = try_grid(silhouette_poly, gx0, gy0, cw, ch)
            count = len(pieces)

            if abs(count - TARGET_PIECES) < abs(best_count - TARGET_PIECES):
                best_pieces = pieces
                best_h_edges = h_edges
                best_v_edges = v_edges
                best_count = count
                best_params = (gx0, gy0, cw, ch)

            if count == TARGET_PIECES:
                print(f"  Found {count} pieces with dx={dx:.1f}, dy={dy:.1f}, cw={cw:.1f}, ch={ch:.1f}")
                break
        else:
            continue
        break

    if best_count != TARGET_PIECES:
        print(f"  WARNING: Best attempt yielded {best_count} pieces (target {TARGET_PIECES})")
        print(f"  Proceeding with {best_count} pieces...")
    else:
        print(f"  Grid confirmed: {best_count} pieces")

    print(f"  Final grid: origin=({best_params[0]:.1f}, {best_params[1]:.1f}), cell=({best_params[2]:.1f} x {best_params[3]:.1f})")

    # 3. Assign numbers
    print("\n[3] Assigning piece numbers...")
    numbered_pieces = assign_numbers(best_pieces)
    print(f"  {len(numbered_pieces)} pieces numbered")

    # 4. Load stickers
    print("\n[4] Loading stickers...")
    stickers = load_stickers()

    # 5. Render
    print("\n[5] Rendering...")
    canvas = Image.new("RGB", (A4_W, A4_H), BG_COLOR)
    draw = ImageDraw.Draw(canvas)

    # Draw page chrome (titles, etc.)
    draw_page_chrome(canvas)

    # Draw silhouette fill (light blue-grey background)
    sil_coords = [(int(x), int(y)) for (x, y) in canvas_pts]
    draw.polygon(sil_coords, fill=(220, 230, 245))

    # Draw all pieces
    draw = ImageDraw.Draw(canvas)
    for poly, icon_num in numbered_pieces:
        if icon_num <= 32:  # safety
            render_piece(canvas, draw, poly, icon_num, stickers)

    # Redraw silhouette outline on top
    draw.line(sil_coords + [sil_coords[0]], fill=(30, 60, 120), width=3)

    # 6. Save
    canvas.save(OUTPUT_PATH, "PNG", dpi=(150, 150))
    print(f"\n  Saved: {OUTPUT_PATH}")
    file_size_kb = os.path.getsize(OUTPUT_PATH) // 1024
    print(f"  File size: {file_size_kb} KB")

    # 7. Stats
    piece_count = len(numbered_pieces)
    print("\n" + "=" * 60)
    print(f"DONE: {piece_count} pieces rendered")
    print(f"FILES: {OUTPUT_PATH} ({file_size_kb} KB)")
    print(f"PIECE COUNT: {piece_count}")

    if piece_count != TARGET_PIECES:
        print(f"ISSUES: Got {piece_count} pieces instead of {TARGET_PIECES} — grid nudge needed")
    else:
        print("ISSUES: None — exactly 32 pieces")

    print(f"NEXT: Open {OUTPUT_PATH} to review jigsaw tessellation and piece clipping")
    print("=" * 60)

    return piece_count


if __name__ == "__main__":
    main()
