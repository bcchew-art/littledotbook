"""
Merlion A4 Sticker Puzzle Mockup — v2 (final)
Tight packing: all 32 stickers inside the silhouette, dense fill.

Key insight from shape analysis:
- Crown at y=0-10%: very narrow (53px) — no stickers here
- Head at y=10-30%: 422px wide — mane/landmark stickers + hero
- Notch at y=20-30%: two segments; left fin (~210-335) + main body (358-711)
- Body y=30-80%: full width (~500-650px) — chest, belly, lower body
- Tail bumps y=50-80%: right-side protrusions (x=567-795)
- Base y=80-100%: tapers to nothing
"""

import re
import math
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import cv2
from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────────────────────
ASSETS    = Path("C:/Users/Admin/Projects/nexsprint/oinio/littledotbook/design-hub/assets")
ICONS_DIR = ASSETS / "icons" / "labeled"
OUT_PATH  = ASSETS / "merlion-puzzle-a4-mockup.png"

# ─── Canvas & Silhouette Scale ────────────────────────────────────────────────
A4_W, A4_H   = 1240, 1754
SVG_VW       = 600
MERLION_W    = 900                       # render width in canvas px
SCALE        = MERLION_W / SVG_VW        # 1.5
MERLION_H    = int(800 * SCALE)          # 1200
OFFSET_X     = (A4_W - MERLION_W) // 2  # 170 — left edge of silhouette on canvas
OFFSET_Y     = 130                       # top edge

# Safe-zone erosion — smaller = more slots in narrow areas
SAFE_ERODE = 8   # px — smaller = more usable area in narrow zones

# Sticker sizes (mask/canvas px)
SIZE_HERO    = 210
SIZE_DEFAULT = 178
SIZE_MIN     = 85

random.seed(13)

# ─── Icon index ───────────────────────────────────────────────────────────────
ICON_FILES = {}
for f in ICONS_DIR.iterdir():
    m = re.match(r"#(\d+)\s", f.name)
    if m:
        ICON_FILES[int(m.group(1))] = f

# ─── SVG path ─────────────────────────────────────────────────────────────────
SVG_PATH_D = (
    "M 451.06,123.52 L 422.68,122.61 L 421.76,121.69 L 416.27,121.69 L 415.35,120.77 "
    "L 402.54,118.94 L 360.42,104.3 L 357.68,104.3 L 351.27,101.55 L 348.52,101.55 "
    "L 336.62,97.89 L 324.72,96.97 L 323.8,96.06 L 318.31,96.06 L 317.39,95.14 "
    "L 282.61,95.14 L 281.69,96.06 L 267.04,97.89 L 263.38,99.72 L 255.14,101.55 "
    "L 236.83,110.7 L 230.42,115.28 L 219.44,126.27 L 212.11,139.08 L 208.45,142.75 "
    "L 203.87,142.75 L 198.38,144.58 L 191.97,144.58 L 186.48,146.41 L 180.99,146.41 "
    "L 170.92,149.15 L 166.34,149.15 L 162.68,150.99 L 158.1,150.99 L 154.44,152.82 "
    "L 151.69,152.82 L 139.79,156.48 L 133.38,159.23 L 130.63,161.97 L 130.63,168.38 "
    "L 135.21,178.45 L 136.13,183.03 L 132.46,186.69 L 128.8,188.52 L 128.8,198.59 "
    "L 132.46,206.83 L 141.62,218.73 L 145.28,220.56 L 148.94,219.65 L 150.77,216.9 "
    "L 150.77,215.07 L 153.52,212.32 L 161.76,215.99 L 164.51,215.99 L 183.73,221.48 "
    "L 190.14,225.14 L 194.72,231.55 L 194.72,236.13 L 192.89,239.79 L 185.56,247.11 "
    "L 175.49,252.61 L 148.03,261.76 L 142.54,264.51 L 139.79,268.17 L 139.79,273.66 "
    "L 141.62,279.15 L 146.2,287.39 L 155.35,298.38 L 162.68,302.96 L 169.08,302.96 "
    "L 172.75,301.13 L 177.32,296.55 L 186.48,290.14 L 233.17,274.58 L 260.63,261.76 "
    "L 275.28,251.69 L 285.35,241.62 L 290.85,234.3 L 297.25,221.48 L 299.08,219.65 "
    "L 300.92,221.48 L 298.17,230.63 L 289.93,244.37 L 276.2,257.18 L 257.89,268.17 "
    "L 222.18,286.48 L 213.03,291.97 L 205.7,298.38 L 194.72,302.96 L 192.89,304.79 "
    "L 172.75,314.86 L 166.34,319.44 L 145.28,330.42 L 111.41,352.39 L 102.25,356.97 "
    "L 102.25,359.72 L 104.08,361.55 L 107.75,362.46 L 117.82,367.96 L 122.39,368.87 "
    "L 124.23,370.7 L 122.39,372.54 L 114.15,373.45 L 109.58,376.2 L 109.58,378.03 "
    "L 112.32,380.77 L 116.9,389.01 L 119.65,397.25 L 121.48,410.07 L 122.39,410.99 "
    "L 122.39,416.48 L 123.31,417.39 L 123.31,438.45 L 122.39,439.37 L 122.39,444.86 "
    "L 121.48,445.77 L 120.56,452.18 L 115.99,465.0 L 110.49,473.24 L 110.49,475.07 "
    "L 89.44,491.55 L 74.79,506.2 L 62.89,520.85 L 56.48,530.92 L 50.07,543.73 "
    "L 44.58,559.3 L 42.75,570.28 L 41.83,571.2 L 41.83,575.77 L 40.92,576.69 "
    "L 40.92,587.68 L 40.0,588.59 L 41.83,612.39 L 47.32,631.62 L 52.82,642.61 "
    "L 61.97,655.42 L 72.04,665.49 L 80.28,671.9 L 93.1,680.14 L 117.82,691.13 "
    "L 137.04,696.62 L 162.68,700.28 L 163.59,701.2 L 173.66,701.2 L 174.58,702.11 "
    "L 215.77,702.11 L 216.69,701.2 L 224.01,701.2 L 224.93,700.28 L 230.42,700.28 "
    "L 232.25,699.37 L 233.17,700.28 L 237.75,700.28 L 238.66,701.2 L 243.24,701.2 "
    "L 249.65,703.03 L 273.45,703.94 L 274.37,704.86 L 304.58,704.86 L 305.49,703.94 "
    "L 325.63,703.03 L 326.55,702.11 L 332.04,702.11 L 332.96,701.2 L 348.52,699.37 "
    "L 349.44,698.45 L 363.17,695.7 L 369.58,692.96 L 372.32,692.96 L 386.97,687.46 "
    "L 401.62,680.14 L 419.01,669.15 L 432.75,658.17 L 443.73,647.18 L 455.63,632.54 "
    "L 467.54,612.39 L 467.54,610.56 L 473.94,597.75 L 474.86,592.25 L 476.69,589.51 "
    "L 476.69,586.76 L 478.52,584.01 L 482.18,563.87 L 483.1,562.96 L 484.01,548.31 "
    "L 484.93,547.39 L 484.93,525.42 L 484.01,523.59 L 486.76,520.85 L 491.34,519.01 "
    "L 499.58,513.52 L 512.39,499.79 L 520.63,486.06 L 520.63,484.23 L 525.21,475.99 "
    "L 530.7,458.59 L 538.03,443.03 L 550.85,430.21 L 560.0,422.89 L 560.0,420.14 "
    "L 546.27,412.82 L 534.37,409.15 L 524.3,408.24 L 523.38,407.32 L 504.15,408.24 "
    "L 503.24,409.15 L 495.92,410.07 L 478.52,416.48 L 465.7,425.63 L 455.63,435.7 "
    "L 446.48,440.28 L 442.82,437.54 L 438.24,429.3 L 427.25,421.06 L 410.77,413.73 "
    "L 399.79,411.9 L 398.87,410.99 L 393.38,410.99 L 392.46,410.07 L 367.75,410.07 "
    "L 366.83,410.99 L 360.42,410.99 L 354.93,413.73 L 354.93,416.48 L 359.51,423.8 "
    "L 359.51,425.63 L 361.34,427.46 L 367.75,441.2 L 369.58,443.03 L 372.32,450.35 "
    "L 374.15,452.18 L 380.56,465.92 L 382.39,467.75 L 385.14,475.07 L 387.89,478.73 "
    "L 394.3,492.46 L 396.13,494.3 L 405.28,513.52 L 407.11,515.35 L 405.28,525.42 "
    "L 398.87,540.99 L 385.14,555.63 L 375.07,561.13 L 373.24,559.3 L 377.82,543.73 "
    "L 378.73,530.0 L 379.65,529.08 L 379.65,514.44 L 378.73,513.52 L 378.73,507.11 "
    "L 377.82,506.2 L 376.9,497.04 L 375.07,492.46 L 375.07,486.97 L 368.66,473.24 "
    "L 368.66,471.41 L 365.0,465.0 L 360.42,452.18 L 358.59,450.35 L 354.01,438.45 "
    "L 348.52,428.38 L 348.52,426.55 L 346.69,424.72 L 346.69,422.89 L 338.45,408.24 "
    "L 338.45,406.41 L 340.28,404.58 L 355.85,401.83 L 356.76,400.92 L 361.34,400.92 "
    "L 362.25,400.0 L 368.66,400.0 L 369.58,399.08 L 399.79,399.08 L 400.7,400.0 "
    "L 406.2,400.0 L 407.11,400.92 L 415.35,401.83 L 426.34,405.49 L 440.99,413.73 "
    "L 442.82,412.82 L 442.82,408.24 L 427.25,350.56 L 429.08,348.73 L 434.58,348.73 "
    "L 435.49,349.65 L 440.99,349.65 L 441.9,350.56 L 458.38,350.56 L 459.3,351.48 "
    "L 465.7,351.48 L 468.45,349.65 L 467.54,334.08 L 466.62,333.17 L 463.87,309.37 "
    "L 462.04,304.79 L 462.04,300.21 L 457.46,282.82 L 457.46,279.15 L 456.55,278.24 "
    "L 456.55,274.58 L 455.63,273.66 L 455.63,270.0 L 453.8,265.42 L 451.06,249.86 "
    "L 452.89,248.03 L 486.76,239.79 L 486.76,236.13 L 451.97,183.94 L 441.9,173.87 "
    "L 419.93,157.39 L 421.76,155.56 L 429.08,153.73 L 436.41,150.07 L 444.65,143.66 "
    "L 451.06,136.34 L 453.8,130.85 L 453.8,125.35 Z"
)


# ─────────────────────────────────────────────────────────────────────────────
# Mask
# ─────────────────────────────────────────────────────────────────────────────

def parse_path(d):
    tokens = re.findall(r'[MLZmlz]|[-+]?[0-9]*\.?[0-9]+', d)
    pts = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t in ('M', 'L'):
            i += 1
            while i < len(tokens) and not tokens[i].isalpha():
                pts.append((float(tokens[i]), float(tokens[i+1])))
                i += 2
        elif t in ('Z', 'z'):
            i += 1
        else:
            i += 1
    return pts


def build_masks():
    pts = parse_path(SVG_PATH_D)
    scaled = np.array([(int(x * SCALE), int(y * SCALE)) for x, y in pts], dtype=np.int32)
    full = np.zeros((MERLION_H, MERLION_W), dtype=np.uint8)
    cv2.fillPoly(full, [scaled], 255)
    k = np.ones((SAFE_ERODE * 2 + 1, SAFE_ERODE * 2 + 1), np.uint8)
    safe = cv2.erode(full, k, iterations=1)
    return full, safe


def get_bounds(mask):
    rows = np.any(mask > 0, axis=1)
    cols = np.any(mask > 0, axis=0)
    y0, y1 = int(np.where(rows)[0][0]),  int(np.where(rows)[0][-1])
    x0, x1 = int(np.where(cols)[0][0]),  int(np.where(cols)[0][-1])
    return x0, y0, x1, y1


# ─────────────────────────────────────────────────────────────────────────────
# Sticker fit check
# ─────────────────────────────────────────────────────────────────────────────

def fits(mask, cx, cy, half, frac=0.88):
    h = int(half * frac)
    x0, y0, x1, y1 = cx - h, cy - h, cx + h, cy + h
    if x0 < 0 or y0 < 0 or x1 >= mask.shape[1] or y1 >= mask.shape[0]:
        return False
    return bool(np.all(mask[y0:y1, x0:x1] > 0))


def best_size(mask, cx, cy, base):
    for s in range(base, SIZE_MIN - 1, -6):
        if fits(mask, cx, cy, s // 2, frac=0.82):
            return s
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Region definitions — in absolute mask pixel coordinates
# Derived from shape analysis:
#   Bounds: x=60-840 (780w), y=142-1057 (915h)
#   y=10%=233, y=20%=325, y=30%=416, y=40%=508, y=50%=599
#   y=60%=691, y=70%=782, y=80%=874
#
# Tail bumps are on the RIGHT side:
#   y=50% (599): x=600-660
#   y=60% (691): x=567-795
#   y=70% (782): x=604-754
#   y=80% (874): merged back into main body
# ─────────────────────────────────────────────────────────────────────────────

# Region name → (icon_ids, y_frac_lo, y_frac_hi, x_frac_lo, x_frac_hi)
# All fracs are relative to silhouette bounding box (bx0,by0,bx1,by1)
REGIONS = [
    # Hero icon — dead center of head
    ("head_hero",  [1],                          0.07, 0.22, 0.22, 0.72),
    # Mane — wide head area, landmarks fan across
    ("mane",       [2, 3, 4, 5, 6, 7, 8],        0.08, 0.40, 0.04, 0.85),
    # Chest — upper body, wide
    ("chest",      [9, 10, 11, 12, 13, 31, 32],  0.30, 0.54, 0.06, 0.72),
    # Belly — mid body (wider x range)
    ("belly",      [14, 15, 16, 17, 18, 19],      0.46, 0.66, 0.06, 0.72),
    # Lower body (wider x range)
    ("lower_body", [20, 21, 22, 23, 24, 25, 26],  0.60, 0.84, 0.02, 0.68),
    # Tail — RIGHT-side bumps (x=56-100%, y=44-84%)
    ("tail",       [27, 28, 29, 30],               0.44, 0.84, 0.56, 1.00),
]


# ─────────────────────────────────────────────────────────────────────────────
# Build dense slot pool per region
# ─────────────────────────────────────────────────────────────────────────────

def region_slots(safe_mask, sil_bounds, region_def, sticker_size):
    """Return all safe slots inside this region, sorted by distance from centroid."""
    name, _, yf0, yf1, xf0, xf1 = region_def
    bx0, by0, bx1, by1 = sil_bounds
    bw, bh = bx1 - bx0, by1 - by0

    rx0 = int(bx0 + xf0 * bw)
    rx1 = int(bx0 + xf1 * bw)
    ry0 = int(by0 + yf0 * bh)
    ry1 = int(by0 + yf1 * bh)

    half_min = max(SIZE_MIN // 2, 20)
    step = max(14, half_min // 3)

    slots = []
    for cy in range(ry0, ry1, step):
        for cx in range(rx0, rx1, step):
            if fits(safe_mask, cx, cy, half_min, frac=0.80):
                slots.append((cx, cy))

    # Sort: closest to region centroid first
    rcx = (rx0 + rx1) // 2
    rcy = (ry0 + ry1) // 2
    slots.sort(key=lambda s: math.hypot(s[0] - rcx, s[1] - rcy))
    return slots


# ─────────────────────────────────────────────────────────────────────────────
# Greedy placement
# ─────────────────────────────────────────────────────────────────────────────

def pack(safe_mask, sil_bounds):
    placements = []

    def occupied(cx, cy, size):
        """True if this position center is nearly identical to an existing sticker center."""
        # Only block if centers overlap by more than 55% — allows tight collage packing
        thresh = size * 0.30
        for p in placements:
            if math.hypot(cx - p['cx'], cy - p['cy']) < thresh:
                return True
        return False

    for region_def in REGIONS:
        name = region_def[0]
        icon_ids = region_def[1]
        base = SIZE_HERO if name == "head_hero" else SIZE_DEFAULT

        slots = region_slots(safe_mask, sil_bounds, region_def, base)
        print(f"  Region '{name}': {len(icon_ids)} icons, {len(slots)} slots available")

        for icon_id in icon_ids:
            placed = False

            # Pick the slot that maximises minimum distance from all already-placed stickers
            # (max-spread placement) — ensures even coverage across the region
            best_slot = None
            best_score = -1
            candidates = [s for s in slots if not occupied(s[0], s[1], base)]

            for (cx, cy) in candidates:
                if not placements:
                    # First sticker: pick from near region centroid
                    score = -math.hypot(cx - (slots[0][0] if slots else cx),
                                        cy - (slots[0][1] if slots else cy))
                else:
                    # Maximise minimum distance to any existing sticker
                    min_d = min(math.hypot(cx - p['cx'], cy - p['cy']) for p in placements)
                    score = min_d
                if score > best_score:
                    sz = best_size(safe_mask, cx, cy, base)
                    if sz is not None:
                        best_score = score
                        best_slot = (cx, cy, sz)

            if best_slot:
                cx, cy, sz = best_slot
                placements.append({'icon_id': icon_id, 'cx': cx, 'cy': cy,
                                   'size': sz, 'region': name})
                placed = True

            if not placed:
                # Fallback: scan ALL safe pixels in region for any valid position
                print(f"    Fallback scan for icon #{icon_id}...")
                name2, _, yf0, yf1, xf0, xf1 = region_def
                bx0, by0, bx1, by1 = sil_bounds
                bw, bh = bx1 - bx0, by1 - by0
                rx0 = int(bx0 + xf0 * bw)
                rx1 = int(bx0 + xf1 * bw)
                ry0 = int(by0 + yf0 * bh)
                ry1 = int(by0 + yf1 * bh)
                sub = safe_mask[ry0:ry1, rx0:rx1]
                ys, xs = np.where(sub > 0)
                indices = list(range(len(xs)))
                random.shuffle(indices)
                for i in indices[:500]:
                    cx2 = int(xs[i]) + rx0
                    cy2 = int(ys[i]) + ry0
                    if occupied(cx2, cy2, base):
                        continue
                    sz = best_size(safe_mask, cx2, cy2, base)
                    if sz:
                        placements.append({'icon_id': icon_id, 'cx': cx2, 'cy': cy2,
                                           'size': sz, 'region': name})
                        placed = True
                        break

            if not placed:
                print(f"    SKIPPED icon #{icon_id} — no valid slot found")

    return placements


# ─────────────────────────────────────────────────────────────────────────────
# Gap-fill nudge
# ─────────────────────────────────────────────────────────────────────────────

def nudge(placements, safe_mask, iters=8):
    for _ in range(iters):
        occ = np.zeros(safe_mask.shape, dtype=np.uint8)
        for p in placements:
            h = p['size'] // 2
            x0 = max(0, p['cx'] - h);  y0 = max(0, p['cy'] - h)
            x1 = min(safe_mask.shape[1], p['cx'] + h)
            y1 = min(safe_mask.shape[0], p['cy'] + h)
            occ[y0:y1, x0:x1] = 255

        empty = (safe_mask > 0) & (occ == 0)
        if not np.any(empty):
            break
        eys, exs = np.where(empty)
        ecx, ecy = int(exs.mean()), int(eys.mean())

        best_p = min(placements, key=lambda p: math.hypot(p['cx'] - ecx, p['cy'] - ecy))
        dx = ecx - best_p['cx'];  dy = ecy - best_p['cy']
        mag = math.hypot(dx, dy)
        if mag < 1:
            continue
        step = 12
        nx = best_p['cx'] + int(step * dx / mag)
        ny = best_p['cy'] + int(step * dy / mag)
        if fits(safe_mask, nx, ny, best_p['size'] // 2):
            best_p['cx'] = nx;  best_p['cy'] = ny
    return placements


# ─────────────────────────────────────────────────────────────────────────────
# Verify
# ─────────────────────────────────────────────────────────────────────────────

def verify(placements, full_mask, safe_mask):
    n_full = sum(1 for p in placements if fits(full_mask, p['cx'], p['cy'], p['size']//2, 0.92))
    n_safe = sum(1 for p in placements if fits(safe_mask, p['cx'], p['cy'], p['size']//2, 0.85))
    n_down = sum(1 for p in placements
                 if p['size'] < ((SIZE_HERO if p['region']=='head_hero' else SIZE_DEFAULT) * 0.82))

    occ = np.zeros(full_mask.shape, dtype=np.uint8)
    for p in placements:
        h = p['size'] // 2
        x0, y0 = max(0, p['cx']-h), max(0, p['cy']-h)
        x1, y1 = min(full_mask.shape[1], p['cx']+h), min(full_mask.shape[0], p['cy']+h)
        occ[y0:y1, x0:x1] = 255

    sil  = int(np.sum(full_mask > 0))
    cov  = int(np.sum((full_mask > 0) & (occ > 0)))
    fill = cov / sil if sil else 0
    return {'n': len(placements), 'n_full': n_full, 'n_safe': n_safe,
            'n_down': n_down, 'fill': fill}


# ─────────────────────────────────────────────────────────────────────────────
# Load icon with dashed border
# ─────────────────────────────────────────────────────────────────────────────

def load_icon(icon_id, size):
    path = ICON_FILES.get(icon_id)
    img = (Image.open(path).convert("RGBA") if (path and path.exists())
           else Image.new("RGBA", (size, size), (180, 180, 180, 150)))
    img = img.resize((size, size), Image.LANCZOS)

    draw = ImageDraw.Draw(img)
    m = 5;  dash = 8;  gap = 5;  lw = 2
    col = (100, 100, 100, 170)

    def dl(x0, y0, x1, y1):
        dx, dy = x1-x0, y1-y0
        L = math.hypot(dx, dy)
        if L == 0: return
        n = int(L / (dash + gap))
        for i in range(n):
            t0 = i * (dash+gap) / L
            t1 = min((i*(dash+gap)+dash) / L, 1.0)
            draw.line([(x0+dx*t0, y0+dy*t0), (x0+dx*t1, y0+dy*t1)], fill=col, width=lw)

    dl(m, m, size-m, m);       dl(size-m, m, size-m, size-m)
    dl(size-m, size-m, m, size-m); dl(m, size-m, m, m)
    return img


# ─────────────────────────────────────────────────────────────────────────────
# Render
# ─────────────────────────────────────────────────────────────────────────────

def render(placements, full_mask):
    canvas = Image.new("RGBA", (A4_W, A4_H), (252, 250, 245, 255))
    draw   = ImageDraw.Draw(canvas)

    def font(name, size):
        try:    return ImageFont.truetype(f"C:/Windows/Fonts/{name}", size)
        except: return ImageFont.load_default()

    ft = font("arialbd.ttf", 54);  fs = font("arialbd.ttf", 36);  ff = font("arial.ttf", 26)

    def ctext(txt, f, y, col):
        bb = draw.textbbox((0,0), txt, font=f)
        draw.text(((A4_W - (bb[2]-bb[0])) // 2, y), txt, fill=col, font=f)

    ctext("My Singapore Stories Vol.2", ft, 36, (26, 54, 93, 255))
    ctext("Merlion Sticker Puzzle",      fs, 98, (210, 60, 45, 255))

    # Silhouette fill
    fa = np.zeros((MERLION_H, MERLION_W, 4), dtype=np.uint8)
    fa[full_mask > 0] = [232, 240, 252, 60]
    fi = Image.fromarray(fa, "RGBA")
    canvas.paste(fi, (OFFSET_X, OFFSET_Y), fi)

    # Outline
    cntrs, _ = cv2.findContours(full_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    oa = np.zeros((MERLION_H, MERLION_W, 4), dtype=np.uint8)
    cv2.drawContours(oa, cntrs, -1, (44, 62, 80, 255), thickness=4)
    oi = Image.fromarray(oa, "RGBA")
    canvas.paste(oi, (OFFSET_X, OFFSET_Y), oi)

    # Draw stickers back-to-front
    order = ["tail", "lower_body", "belly", "chest", "mane", "head_hero"]
    sorted_p = sorted(placements,
                      key=lambda p: order.index(p['region']) if p['region'] in order else 99)

    for p in sorted_p:
        angle = random.uniform(-7, 7)
        icon  = load_icon(p['icon_id'], p['size'])
        rot   = icon.rotate(angle, expand=True, resample=Image.BICUBIC)
        px = OFFSET_X + p['cx'] - rot.width  // 2
        py = OFFSET_Y + p['cy'] - rot.height // 2
        canvas.paste(rot, (px, py), rot)

    ctext("Little Dot Book  .  My Singapore Stories Vol.2", ff, A4_H - 56, (110, 110, 110, 255))

    canvas.convert("RGB").save(OUT_PATH, "PNG", dpi=(150, 150))
    print(f"Saved: {OUT_PATH}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    print("Step 1: Building silhouette mask...")
    full_mask, safe_mask = build_masks()
    bounds = get_bounds(full_mask)
    bx0, by0, bx1, by1 = bounds
    print(f"  Bounds: x={bx0}-{bx1} ({bx1-bx0}w), y={by0}-{by1} ({by1-by0}h)")
    print(f"  Silhouette: {int(np.sum(full_mask>0)):,} px | Safe zone: {int(np.sum(safe_mask>0)):,} px")

    print("\nStep 2: Packing stickers...")
    placements = pack(safe_mask, bounds)
    print(f"\n  Total placed: {len(placements)}/32")

    print("\nStep 3: Gap-fill nudge...")
    placements = nudge(placements, safe_mask)

    print("\nStep 4: Verification...")
    s = verify(placements, full_mask, safe_mask)
    print(f"  Placed: {s['n']}/32")
    print(f"  Fully inside silhouette: {s['n_full']}/32")
    print(f"  Inside safe zone:        {s['n_safe']}/32")
    print(f"  Downsized:               {s['n_down']}")
    print(f"  Fill ratio:              {s['fill']:.1%}")

    if s['n_full'] < s['n']:
        bad = [p['icon_id'] for p in placements
               if not fits(full_mask, p['cx'], p['cy'], p['size']//2, 0.92)]
        print(f"  Not fully inside: icons {bad}")

    print("\nStep 5: Rendering...")
    render(placements, full_mask)

    print("\n=== FINAL STATS ===")
    print(f"Stickers placed:         {s['n']}/32")
    print(f"Inside silhouette:       {s['n_full']}/32")
    print(f"Inside safe zone:        {s['n_safe']}/32")
    print(f"Downsized:               {s['n_down']}")
    print(f"Fill ratio:              {s['fill']:.1%}")
    print(f"Output: {OUT_PATH}")


if __name__ == "__main__":
    main()
