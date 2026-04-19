"""
Bubble Letter Label Script for Little Dot Book Icons
Creates chunky bubble letter labels on all 32 sticker icons.
"""

import os
import re
from PIL import Image, ImageDraw, ImageFont

ICONS_DIR = r"C:/Users/Admin/Projects/nexsprint/oinio/littledotbook/design-hub/assets/icons"
OUTPUT_DIR = r"C:/Users/Admin/Projects/nexsprint/oinio/littledotbook/design-hub/assets/icons/labeled"

# The 32 canonical icons with their labels
ICON_MAP = {
    "#1 Merlion.png": "Merlion",
    "#2 MBS.png": "MBS",
    "#3 Esplanade.png": "Esplanade",
    "#4 Gardens by the Bay.png": "Gardens by the Bay",
    "#5 Singapore Flyer.png": "Singapore Flyer",
    "#6 Changi Jewel.png": "Changi Jewel",
    "#7 National Museum.png": "National Museum",
    "#8 Chinatown Gate.png": "Chinatown Gate",
    "#9 MRT Train.png": "MRT Train",
    "#10 SBS Bus.png": "SBS Bus",
    "#11 Bumboat.png": "Bumboat",
    "#12 Cable Car.png": "Cable Car",
    "#13 Taxi.png": "Taxi",
    "#14 Chicken Rice.png": "Chicken Rice",
    "#15 Laksa.png": "Laksa",
    "#16 Ice Kacang.png": "Ice Kacang",
    "#17 Roti Prata.png": "Roti Prata",
    "#18 Satay.png": "Satay",
    "#19 Kaya Toast + Kopi.png": "Kaya Toast + Kopi",
    "#20 HDB Flat.png": "HDB Flat",
    "#21 Void Deck.png": "Void Deck",
    "#22 Dragon Playground.png": "Dragon Playground",
    "#23 Kopitiam.png": "Kopitiam",
    "#24 Pasar Malam.png": "Pasar Malam",
    "#25 Ang Bao.png": "Ang Bao",
    "#26 Lion Dance Head.png": "Lion Dance Head",
    "#27 Botanic Gardens.png": "Botanic Gardens",
    "#28 Orchid.png": "Orchid",
    "#29 Otters.png": "Otters",
    "#30 Community Cat.png": "Community Cat",
    "#31 Singapore Flag.png": "Singapore Flag",
    "#32 National Day Fireworks.png": "National Day Fireworks",
}

# Font candidates -- boldest/roundest first
FONT_CANDIDATES = [
    "Comic Sans MS Bold",
    "comicsansms",
    "Comic Sans MS",
    "Arial Rounded MT Bold",
    "arialroundedmtbold",
    "Arial Black",
    "arialblack",
    "Impact",
    "Arial Bold",
    "Arial",
]

# Windows font paths to try
FONT_PATHS = [
    r"C:\Windows\Fonts\comicbd.ttf",       # Comic Sans MS Bold
    r"C:\Windows\Fonts\comic.ttf",         # Comic Sans MS
    r"C:\Windows\Fonts\ARLRDBD.TTF",       # Arial Rounded MT Bold
    r"C:\Windows\Fonts\ariblk.ttf",        # Arial Black
    r"C:\Windows\Fonts\impact.ttf",        # Impact
    r"C:\Windows\Fonts\arialbd.ttf",       # Arial Bold
    r"C:\Windows\Fonts\arial.ttf",         # Arial
]


def get_font(size):
    """Try font paths in order, return the first that works at given size."""
    for path in FONT_PATHS:
        if os.path.exists(path):
            try:
                font = ImageFont.truetype(path, size)
                return font, path
            except Exception:
                continue
    # Last resort: default font (no size control)
    return ImageFont.load_default(), None


def get_text_bbox(draw, text, font):
    """Get bounding box of text."""
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        return w, h
    except Exception:
        # Older Pillow fallback
        w, h = draw.textsize(text, font=font)
        return w, h


def fit_font_to_width(label, img_width, draw, max_size=56, min_size=28, padding_ratio=0.85):
    """Find the largest font size that fits within img_width * padding_ratio."""
    max_text_width = int(img_width * padding_ratio)

    # Try sizes from max down to min
    for size in range(max_size, min_size - 1, -2):
        font, path = get_font(size)
        tw, th = get_text_bbox(draw, label, font)
        if tw <= max_text_width:
            return font, size, tw, th

    # Force min size
    font, path = get_font(min_size)
    tw, th = get_text_bbox(draw, label, font)
    return font, min_size, tw, th


def draw_bubble_text(draw, text, font, x, y, stroke_width=6, fill_color='white', stroke_color='black'):
    """
    Draw bubble letter text:
    1. Render black outline by drawing text at offsets in a circle pattern
    2. Render white fill on top
    """
    # Draw the thick black stroke using circular offset pattern
    for ox in range(-stroke_width, stroke_width + 1):
        for oy in range(-stroke_width, stroke_width + 1):
            if ox * ox + oy * oy <= stroke_width * stroke_width:
                draw.text((x + ox, y + oy), text, font=font, fill=stroke_color)

    # Draw the white fill on top
    draw.text((x, y), text, font=font, fill=fill_color)


def process_icon(filename, label, icons_dir, output_dir):
    """Process a single icon: add bubble letter label."""
    src_path = os.path.join(icons_dir, filename)

    if not os.path.exists(src_path):
        print(f"  SKIP (not found): {filename}")
        return False

    # Open original image
    img = Image.open(src_path).convert("RGBA")
    img_w, img_h = img.size

    # Create a draw object on a copy
    labeled = img.copy()
    draw = ImageDraw.Draw(labeled)

    # Determine font size that fits
    # Base size for 1024x1024 is 56px, scale proportionally for other sizes
    scale = img_w / 1024.0
    max_size = max(28, int(56 * scale))
    min_size = max(20, int(28 * scale))
    stroke_width = max(4, int(6 * scale))

    font, actual_size, tw, th = fit_font_to_width(
        label, img_w, draw,
        max_size=max_size,
        min_size=min_size,
        padding_ratio=0.88
    )

    # Center horizontally
    x = (img_w - tw) // 2

    # Position at 87% of image height (near bottom, not clipped)
    # We want the TOP of the text to be at ~87% height
    # But ensure bottom of text + stroke doesn't exceed image height
    stroke_pad = stroke_width + 2
    y_target = int(img_h * 0.87)
    y = y_target

    # Clamp so text doesn't go off-screen
    max_y = img_h - th - stroke_pad
    if y > max_y:
        y = max_y
    min_y = int(img_h * 0.70)  # Don't go higher than 70%
    if y < min_y:
        y = min_y

    # Draw bubble text
    draw_bubble_text(
        draw, label, font, x, y,
        stroke_width=stroke_width,
        fill_color='white',
        stroke_color='black'
    )

    # Save to output directory
    out_path = os.path.join(output_dir, filename)
    labeled.save(out_path, "PNG")

    print(f"  OK  [{actual_size}px, {img_w}x{img_h}] {filename} -> '{label}'")
    return True


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Pillow version: from PIL import __version__")
    from PIL import __version__ as pil_version
    print(f"Pillow version: {pil_version}")

    # Check which font we'll use
    print("\nFont check:")
    for path in FONT_PATHS:
        exists = os.path.exists(path)
        print(f"  {'FOUND' if exists else 'missing'}: {path}")

    print(f"\nProcessing {len(ICON_MAP)} icons...")
    print(f"  Source: {ICONS_DIR}")
    print(f"  Output: {OUTPUT_DIR}\n")

    success = 0
    failed = 0

    for filename, label in ICON_MAP.items():
        ok = process_icon(filename, label, ICONS_DIR, OUTPUT_DIR)
        if ok:
            success += 1
        else:
            failed += 1

    print(f"\nDone: {success} labeled, {failed} skipped/failed")

    # List output files
    out_files = sorted(os.listdir(OUTPUT_DIR))
    print(f"\nOutput directory contains {len(out_files)} files:")
    for f in out_files:
        print(f"  {f}")


if __name__ == "__main__":
    main()
