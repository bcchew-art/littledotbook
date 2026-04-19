"""
curved_bubble_labels.py
Generates curved bubble-text labeled versions of all 32 sticker icons.
Text follows a smile/arc curve, overlapping the bottom of the sticker.
"""

import math
import os
from PIL import Image, ImageDraw, ImageFont

ICONS_DIR = "C:/Users/Admin/Projects/nexsprint/oinio/littledotbook/design-hub/assets/icons"
OUTPUT_DIR = "C:/Users/Admin/Projects/nexsprint/oinio/littledotbook/design-hub/assets/icons/labeled"
FONT_PATH = "C:/Windows/Fonts/comicbd.ttf"

# The 32 canonical icons: filename -> label
ICONS = [
    ("#1 Merlion.png",              "Merlion"),
    ("#2 MBS.png",                  "MBS"),
    ("#3 Esplanade.png",            "Esplanade"),
    ("#4 Gardens by the Bay.png",   "Gardens by the Bay"),
    ("#5 Singapore Flyer.png",      "Singapore Flyer"),
    ("#6 Changi Jewel.png",         "Changi Jewel"),
    ("#7 National Museum.png",      "National Museum"),
    ("#8 Chinatown Gate.png",       "Chinatown Gate"),
    ("#9 MRT Train.png",            "MRT Train"),
    ("#10 SBS Bus.png",             "SBS Bus"),
    ("#11 Bumboat.png",             "Bumboat"),
    ("#12 Cable Car.png",           "Cable Car"),
    ("#13 Taxi.png",                "Taxi"),
    ("#14 Chicken Rice.png",        "Chicken Rice"),
    ("#15 Laksa.png",               "Laksa"),
    ("#16 Ice Kacang.png",          "Ice Kacang"),
    ("#17 Roti Prata.png",          "Roti Prata"),
    ("#18 Satay.png",               "Satay"),
    ("#19 Kaya Toast + Kopi.png",   "Kaya Toast + Kopi"),
    ("#20 HDB Flat.png",            "HDB Flat"),
    ("#21 Void Deck.png",           "Void Deck"),
    ("#22 Dragon Playground.png",   "Dragon Playground"),
    ("#23 Kopitiam.png",            "Kopitiam"),
    ("#24 Pasar Malam.png",         "Pasar Malam"),
    ("#25 Ang Bao.png",             "Ang Bao"),
    ("#26 Lion Dance Head.png",     "Lion Dance Head"),
    ("#27 Botanic Gardens.png",     "Botanic Gardens"),
    ("#28 Orchid.png",              "Orchid"),
    ("#29 Otters.png",              "Otters"),
    ("#30 Community Cat.png",       "Community Cat"),
    ("#31 Singapore Flag.png",      "Singapore Flag"),
    ("#32 National Day Fireworks.png", "National Day Fireworks"),
]

STROKE_WIDTH = 8
FILL_COLOR = (255, 255, 255, 255)      # white
STROKE_COLOR = (0, 0, 0, 255)          # black
BASE_FONT_SIZE = 76
MIN_FONT_SIZE = 48


def get_font(size):
    return ImageFont.truetype(FONT_PATH, size)


def measure_text_width(font, text):
    """Total pixel width of the text string."""
    total = 0
    for ch in text:
        bbox = font.getbbox(ch)
        total += bbox[2] - bbox[0]
    return total


def choose_font_size(text, img_width):
    """Pick the largest font size where the text fits within ~90% of img_width."""
    max_text_width = img_width * 0.88
    size = BASE_FONT_SIZE
    while size >= MIN_FONT_SIZE:
        font = get_font(size)
        w = measure_text_width(font, text)
        if w <= max_text_width:
            return size, font
        size -= 4
    return MIN_FONT_SIZE, get_font(MIN_FONT_SIZE)


def choose_arc_radius(text, font, img_width):
    """
    Compute arc radius so the curve is a gentle smile.
    Shorter texts get tighter curves (more visible arc).
    Longer texts need flatter curves so the ends don't fly too high.
    Rule: the longer the name, the FLATTER (higher radius) the curve.
    """
    n = len(text)
    if n <= 5:
        # Short cute names (e.g. "MBS", "Taxi"): subtle arc, nearly flat
        return 1500
    elif n <= 10:
        # Medium names (e.g. "Merlion", "Esplanade"): gentle smile
        return 900
    elif n <= 15:
        # Long names (e.g. "Chicken Rice", "Cable Car"): very gentle curve
        return 1100
    else:
        # Very long names (e.g. "Gardens by the Bay", "National Day Fireworks"): almost flat
        return 1800


def draw_curved_text(img, text, font, center_x, base_y, arc_radius, stroke_width):
    """
    Draw text along a curved arc (smile shape — concave up).
    Each character is rendered individually, rotated to follow the arc tangent,
    and composited onto `img` (RGBA).

    center_x  — horizontal centre of the arc circle
    base_y    — y-coordinate of the LOWEST point of the arc (bottom of smile)
    arc_radius — radius of the circle whose arc we follow
    """
    # Per-character widths
    char_widths = []
    for ch in text:
        bbox = font.getbbox(ch)
        char_widths.append(bbox[2] - bbox[0])
    total_width = sum(char_widths)

    # Angular span the text occupies on the circle
    # arc_length ≈ total_width  →  angle = arc_length / radius
    total_angle = total_width / arc_radius

    # We place characters left-to-right starting at (pi/2 + half_span)
    # (working in standard math coords: 0 = right, pi/2 = top)
    # The lowest point of the smile is at angle = pi/2 (straight down from centre)
    # but our coordinate system has y increasing downward, so we handle that below.
    start_angle = math.pi / 2 + total_angle / 2  # leftmost character angle

    # Circle centre in image coords:
    # The LOWEST point of the arc is at base_y.
    # That point is directly BELOW the circle centre, so:
    #   circle_centre_y = base_y - arc_radius
    circle_cx = center_x
    circle_cy = base_y - arc_radius

    current_angle = start_angle

    for i, ch in enumerate(text):
        char_w = char_widths[i]
        char_angle = char_w / arc_radius
        mid_angle = current_angle - char_angle / 2  # angle at the middle of this char

        # Position on arc (image coords — y increases downward)
        # x = circle_cx + R * cos(mid_angle)
        # y = circle_cy + R * sin(mid_angle)   (note: +sin because y-down)
        # Wait — in standard math y-up, a point at angle θ from centre is:
        #   (cx + R*cos θ,  cy - R*sin θ)
        # But our image has y increasing DOWNWARD, so:
        #   x_img = cx + R*cos θ
        #   y_img = cy + R*sin θ   ← + not -
        # At θ = π/2 (straight up in math = straight DOWN in image):
        #   y_img = cy + R  = (base_y - R) + R = base_y  ✓
        cx = circle_cx + arc_radius * math.cos(mid_angle)
        cy = circle_cy + arc_radius * math.sin(mid_angle)

        # Rotation: the tangent to the circle at angle θ points at angle (θ + π/2).
        # In image-space (y-down), the visual rotation we need is:
        rotation_deg = math.degrees(mid_angle - math.pi / 2)

        # --- Render char onto a small transparent canvas ---
        pad = stroke_width * 3
        ch_h = int(font.size * 1.6)
        # Some fonts report weird bbox origins; normalise
        bbox = font.getbbox(ch)
        ch_render_w = bbox[2] - bbox[0] + pad * 2
        ch_render_h = ch_h + pad * 2

        ch_img = Image.new("RGBA", (ch_render_w, ch_render_h), (0, 0, 0, 0))
        ch_draw = ImageDraw.Draw(ch_img)

        # Stroke: draw char offset in all directions
        text_x = pad - bbox[0]
        text_y = pad
        for ox in range(-stroke_width, stroke_width + 1):
            for oy in range(-stroke_width, stroke_width + 1):
                if ox * ox + oy * oy <= stroke_width * stroke_width:
                    ch_draw.text((text_x + ox, text_y + oy), ch,
                                 font=font, fill=STROKE_COLOR)
        # White fill on top
        ch_draw.text((text_x, text_y), ch, font=font, fill=FILL_COLOR)

        # Rotate character to match arc tangent
        rotated = ch_img.rotate(-rotation_deg, expand=True,
                                resample=Image.BICUBIC)

        # Paste onto main image at computed arc position
        paste_x = int(cx - rotated.width / 2)
        paste_y = int(cy - rotated.height / 2)
        img.alpha_composite(rotated, dest=(paste_x, paste_y))

        current_angle -= char_angle


def process_icon(filename, label, output_dir):
    src_path = os.path.join(ICONS_DIR, filename)
    dst_path = os.path.join(output_dir, filename)

    img = Image.open(src_path).convert("RGBA")
    w, h = img.size

    font_size, font = choose_font_size(label, w)
    arc_radius = choose_arc_radius(label, font, w)

    # Lowest point of the smile arc sits at ~83% of image height
    # This pushes the text up to overlap the sticker artwork more
    base_y = int(h * 0.83)
    center_x = w // 2

    draw_curved_text(img, label, font, center_x, base_y, arc_radius, STROKE_WIDTH)

    img.save(dst_path, "PNG")
    return font_size


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Output dir: {OUTPUT_DIR}\n")
    print(f"{'Icon':<40} {'Label':<30} {'Font size':>9}")
    print("-" * 82)

    for filename, label in ICONS:
        src_path = os.path.join(ICONS_DIR, filename)
        if not os.path.exists(src_path):
            print(f"  MISSING: {src_path}")
            continue
        font_size = process_icon(filename, label, OUTPUT_DIR)
        print(f"  {filename:<40} {label:<30} {font_size:>6}px")

    print("\nAll done.")


if __name__ == "__main__":
    main()
