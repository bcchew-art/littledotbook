"""
Merlion Silhouette Extractor
Converts the Merlion PNG icon to a clean SVG path for the puzzle board boundary.
"""

import cv2
import numpy as np
from PIL import Image
import os

SRC = r"C:/Users/Admin/Projects/nexsprint/oinio/littledotbook/design-hub/assets/icons/#1 Merlion.png"
OUT = r"C:/Users/Admin/Projects/nexsprint/oinio/littledotbook/design-hub/assets/merlion-silhouette.svg"

# Target SVG canvas — portrait A4 aspect ratio
SVG_W = 600
SVG_H = 800

# ── 1. Load image ──────────────────────────────────────────────────────────────
img_bgr = cv2.imread(SRC)
if img_bgr is None:
    raise FileNotFoundError(f"Cannot load image: {SRC}")

h_orig, w_orig = img_bgr.shape[:2]
print(f"Source image: {w_orig}x{h_orig}")

# ── 2. Create binary mask (subject vs white background) ───────────────────────
# Convert to grayscale
gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

# Background is white (~255). Threshold: pixels darker than 240 are subject.
_, mask = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)

# Small morphological close to fill minor gaps inside the silhouette
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

# Dilate slightly to ensure we capture edge pixels of the geometric shapes
kernel_dilate = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
mask = cv2.dilate(mask, kernel_dilate, iterations=1)

# ── 3. Flood-fill holes inside silhouette so contour is a solid outline ───────
mask_filled = mask.copy()
flood_fill_mask = np.zeros((h_orig + 2, w_orig + 2), np.uint8)
cv2.floodFill(mask_filled, flood_fill_mask, (0, 0), 255)
mask_filled_inv = cv2.bitwise_not(mask_filled)
mask_solid = cv2.bitwise_or(mask, mask_filled_inv)

# ── 4. Find contours ──────────────────────────────────────────────────────────
contours, hierarchy = cv2.findContours(mask_solid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
print(f"Raw contours found: {len(contours)}")

if not contours:
    raise RuntimeError("No contours found — check threshold value")

# ── 5. Filter: keep only large contours (discard tiny noise fragments) ────────
# Compute image area for relative sizing
img_area = h_orig * w_orig

# Keep contours whose bounding box area is > 0.5% of image area
# This keeps the main body + any nearby accent shapes, discards stray pixels
min_area = img_area * 0.005
significant = [(c, cv2.contourArea(c)) for c in contours]
significant = [(c, a) for c, a in significant if a > min_area]
significant.sort(key=lambda x: x[1], reverse=True)

print(f"Significant contours (area > {min_area:.0f} px): {len(significant)}")
for i, (c, a) in enumerate(significant):
    x, y, cw, ch = cv2.boundingRect(c)
    print(f"  [{i}] area={a:.0f}  bbox=({x},{y},{cw},{ch})")

# Use the largest contour as primary silhouette
main_contour, main_area = significant[0]
print(f"\nMain contour area: {main_area:.0f}")

# ── 6. Simplify contour ───────────────────────────────────────────────────────
# Douglas-Peucker approximation — epsilon controls smoothness
# We want 200-400 points; start with epsilon=3 and adjust
def simplify_contour(contour, target_min=200, target_max=400):
    """
    Two-stage simplification:
    1. Try Douglas-Peucker with fine epsilon increments.
    2. If no epsilon hits the target range, evenly resample the raw contour
       to exactly 300 points (uniform arc-length sampling).
    """
    perimeter = cv2.arcLength(contour, True)
    # Fine sweep — include very small epsilons since this image has sharp geometry
    for eps_factor in [0.00008, 0.0001, 0.00015, 0.0002, 0.00025, 0.0003,
                       0.0005, 0.001, 0.002, 0.003, 0.005]:
        epsilon = eps_factor * perimeter
        approx = cv2.approxPolyDP(contour, epsilon, True)
        n = len(approx)
        if target_min <= n <= target_max:
            print(f"Simplified to {n} points (epsilon factor={eps_factor})")
            return approx

    # Fallback: uniform arc-length resampling of raw contour to 300 points
    print("Douglas-Peucker couldn't hit target range — using uniform resampling to 300 pts")
    pts = contour.reshape(-1, 2).astype(np.float32)
    n_target = 300

    # Compute cumulative arc lengths
    diffs = np.diff(pts, axis=0)
    seg_lengths = np.sqrt((diffs ** 2).sum(axis=1))
    cum_lengths = np.concatenate([[0], np.cumsum(seg_lengths)])
    total_length = cum_lengths[-1]

    # Sample at evenly-spaced arc lengths
    sample_lengths = np.linspace(0, total_length, n_target, endpoint=False)
    sampled = []
    for s in sample_lengths:
        idx = np.searchsorted(cum_lengths, s, side='right') - 1
        idx = min(idx, len(pts) - 2)
        seg = cum_lengths[idx + 1] - cum_lengths[idx]
        if seg < 1e-9:
            t = 0.0
        else:
            t = (s - cum_lengths[idx]) / seg
        p = pts[idx] + t * (pts[idx + 1] - pts[idx])
        sampled.append(p)

    sampled = np.array(sampled, dtype=np.float32).reshape(-1, 1, 2).astype(np.int32)
    print(f"Resampled to {len(sampled)} points")
    return sampled

simplified = simplify_contour(main_contour)
points = simplified.reshape(-1, 2)
print(f"Final point count: {len(points)}")

# ── 7. Scale points to SVG canvas ─────────────────────────────────────────────
# Find bounding box of the contour
x_min, y_min = points.min(axis=0)
x_max, y_max = points.max(axis=0)
cont_w = x_max - x_min
cont_h = y_max - y_min
print(f"Contour bounding box: ({x_min},{y_min}) to ({x_max},{y_max})  size={cont_w}x{cont_h}")

# Scale to fit within SVG canvas with 40px padding
padding = 40
avail_w = SVG_W - 2 * padding
avail_h = SVG_H - 2 * padding

scale = min(avail_w / cont_w, avail_h / cont_h)
offset_x = padding + (avail_w - cont_w * scale) / 2
offset_y = padding + (avail_h - cont_h * scale) / 2

def scale_point(px, py):
    sx = (px - x_min) * scale + offset_x
    sy = (py - y_min) * scale + offset_y
    return round(sx, 2), round(sy, 2)

scaled_points = [scale_point(p[0], p[1]) for p in points]

# ── 8. Build SVG path string ──────────────────────────────────────────────────
path_parts = []
for i, (sx, sy) in enumerate(scaled_points):
    if i == 0:
        path_parts.append(f"M {sx},{sy}")
    else:
        path_parts.append(f"L {sx},{sy}")
path_parts.append("Z")
path_d = " ".join(path_parts)

# ── 9. Write SVG ──────────────────────────────────────────────────────────────
svg_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     viewBox="0 0 {SVG_W} {SVG_H}"
     width="{SVG_W}"
     height="{SVG_H}">
  <title>Merlion Silhouette</title>
  <desc>Outline silhouette of the Merlion, extracted from geometric collage. Use as puzzle board boundary or clipPath.</desc>

  <!-- Merlion silhouette outline — {len(scaled_points)} path points -->
  <!-- Source: {os.path.basename(SRC)} ({w_orig}x{h_orig}px) -->
  <path
    id="merlion-silhouette"
    d="{path_d}"
    fill="#F0F4F8"
    fill-opacity="0.4"
    stroke="#2C3E50"
    stroke-width="3"
    stroke-linejoin="round"
    stroke-linecap="round"
  />
</svg>
"""

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    f.write(svg_content)

print(f"\nSVG saved to: {OUT}")
print(f"SVG canvas: {SVG_W}x{SVG_H}")
print(f"Path points: {len(scaled_points)}")
print(f"First 5 points: {scaled_points[:5]}")
print(f"Last 5 points: {scaled_points[-5:]}")

# ── 10. Quick sanity check — describe point distribution ─────────────────────
xs = [p[0] for p in scaled_points]
ys = [p[1] for p in scaled_points]
print(f"\nPoint spread in SVG space:")
print(f"  X range: {min(xs):.1f} - {max(xs):.1f}  (width span: {max(xs)-min(xs):.1f})")
print(f"  Y range: {min(ys):.1f} - {max(ys):.1f}  (height span: {max(ys)-min(ys):.1f})")
print(f"  Centroid: ({sum(xs)/len(xs):.1f}, {sum(ys)/len(ys):.1f})")

# Check top third (head region) has points spread across X — confirms lion head
top_third_ys = [p for p in scaled_points if p[1] < SVG_H / 3]
bottom_third_ys = [p for p in scaled_points if p[1] > 2 * SVG_H / 3]
mid_ys = [p for p in scaled_points if SVG_H / 3 <= p[1] <= 2 * SVG_H / 3]
print(f"\nVertical distribution of points:")
print(f"  Top third (head):   {len(top_third_ys)} points")
print(f"  Middle (body):      {len(mid_ys)} points")
print(f"  Bottom third (tail): {len(bottom_third_ys)} points")

print("\nDone.")
