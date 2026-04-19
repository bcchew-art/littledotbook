"""
Generate a PNG preview of the Merlion puzzle board layout.
Renders the 4x8 grid of zones clipped to the real Merlion silhouette path.
Output: assets/puzzle-board-preview.png

Run: python generate_puzzle_preview.py
Requires: Pillow (pip install Pillow)
"""
import sys
import os
import subprocess

# Auto-install Pillow if missing
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "Pillow"], check=True)
    from PIL import Image, ImageDraw, ImageFont

# --- Silhouette path points (from merlion-silhouette.svg, L-command polygon) ---
MERLION_POINTS = [
    (451.06,123.52),(422.68,122.61),(421.76,121.69),(416.27,121.69),(415.35,120.77),
    (402.54,118.94),(360.42,104.3),(357.68,104.3),(351.27,101.55),(348.52,101.55),
    (336.62,97.89),(324.72,96.97),(323.8,96.06),(318.31,96.06),(317.39,95.14),
    (282.61,95.14),(281.69,96.06),(267.04,97.89),(263.38,99.72),(255.14,101.55),
    (236.83,110.7),(230.42,115.28),(219.44,126.27),(212.11,139.08),(208.45,142.75),
    (203.87,142.75),(198.38,144.58),(191.97,144.58),(186.48,146.41),(180.99,146.41),
    (170.92,149.15),(166.34,149.15),(162.68,150.99),(158.1,150.99),(154.44,152.82),
    (151.69,152.82),(139.79,156.48),(133.38,159.23),(130.63,161.97),(130.63,168.38),
    (135.21,178.45),(136.13,183.03),(132.46,186.69),(128.8,188.52),(128.8,198.59),
    (132.46,206.83),(141.62,218.73),(145.28,220.56),(148.94,219.65),(150.77,216.9),
    (150.77,215.07),(153.52,212.32),(161.76,215.99),(164.51,215.99),(183.73,221.48),
    (190.14,225.14),(194.72,231.55),(194.72,236.13),(192.89,239.79),(185.56,247.11),
    (175.49,252.61),(148.03,261.76),(142.54,264.51),(139.79,268.17),(139.79,273.66),
    (141.62,279.15),(146.2,287.39),(155.35,298.38),(162.68,302.96),(169.08,302.96),
    (172.75,301.13),(177.32,296.55),(186.48,290.14),(233.17,274.58),(260.63,261.76),
    (275.28,251.69),(285.35,241.62),(290.85,234.3),(297.25,221.48),(299.08,219.65),
    (300.92,221.48),(298.17,230.63),(289.93,244.37),(276.2,257.18),(257.89,268.17),
    (222.18,286.48),(213.03,291.97),(205.7,298.38),(194.72,302.96),(192.89,304.79),
    (172.75,314.86),(166.34,319.44),(145.28,330.42),(111.41,352.39),(102.25,356.97),
    (102.25,359.72),(104.08,361.55),(107.75,362.46),(117.82,367.96),(122.39,368.87),
    (124.23,370.7),(122.39,372.54),(114.15,373.45),(109.58,376.2),(109.58,378.03),
    (112.32,380.77),(116.9,389.01),(119.65,397.25),(121.48,410.07),(122.39,410.99),
    (122.39,416.48),(123.31,417.39),(123.31,438.45),(122.39,439.37),(122.39,444.86),
    (121.48,445.77),(120.56,452.18),(115.99,465.0),(110.49,473.24),(110.49,475.07),
    (89.44,491.55),(74.79,506.2),(62.89,520.85),(56.48,530.92),(50.07,543.73),
    (44.58,559.3),(42.75,570.28),(41.83,571.2),(41.83,575.77),(40.92,576.69),
    (40.92,587.68),(40.0,588.59),(41.83,612.39),(47.32,631.62),(52.82,642.61),
    (61.97,655.42),(72.04,665.49),(80.28,671.9),(93.1,680.14),(117.82,691.13),
    (137.04,696.62),(162.68,700.28),(163.59,701.2),(173.66,701.2),(174.58,702.11),
    (215.77,702.11),(216.69,701.2),(224.01,701.2),(224.93,700.28),(230.42,700.28),
    (232.25,699.37),(233.17,700.28),(237.75,700.28),(238.66,701.2),(243.24,701.2),
    (249.65,703.03),(273.45,703.94),(274.37,704.86),(304.58,704.86),(305.49,703.94),
    (325.63,703.03),(326.55,702.11),(332.04,702.11),(332.96,701.2),(348.52,699.37),
    (349.44,698.45),(363.17,695.7),(369.58,692.96),(372.32,692.96),(386.97,687.46),
    (401.62,680.14),(419.01,669.15),(432.75,658.17),(443.73,647.18),(455.63,632.54),
    (467.54,612.39),(467.54,610.56),(473.94,597.75),(474.86,592.25),(476.69,589.51),
    (476.69,586.76),(478.52,584.01),(482.18,563.87),(483.1,562.96),(484.01,548.31),
    (484.93,547.39),(484.93,525.42),(484.01,523.59),(486.76,520.85),(491.34,519.01),
    (499.58,513.52),(512.39,499.79),(520.63,486.06),(520.63,484.23),(525.21,475.99),
    (530.7,458.59),(538.03,443.03),(550.85,430.21),(560.0,422.89),(560.0,420.14),
    (546.27,412.82),(534.37,409.15),(524.3,408.24),(523.38,407.32),(504.15,408.24),
    (503.24,409.15),(495.92,410.07),(478.52,416.48),(465.7,425.63),(455.63,435.7),
    (446.48,440.28),(442.82,437.54),(438.24,429.3),(427.25,421.06),(410.77,413.73),
    (399.79,411.9),(398.87,410.99),(393.38,410.99),(392.46,410.07),(367.75,410.07),
    (366.83,410.99),(360.42,410.99),(354.93,413.73),(354.93,416.48),(359.51,423.8),
    (359.51,425.63),(361.34,427.46),(367.75,441.2),(369.58,443.03),(372.32,450.35),
    (374.15,452.18),(380.56,465.92),(382.39,467.75),(385.14,475.07),(387.89,478.73),
    (394.3,492.46),(396.13,494.3),(405.28,513.52),(407.11,515.35),(405.28,525.42),
    (398.87,540.99),(385.14,555.63),(375.07,561.13),(373.24,559.3),(377.82,543.73),
    (378.73,530.0),(379.65,529.08),(379.65,514.44),(378.73,513.52),(378.73,507.11),
    (377.82,506.2),(376.9,497.04),(375.07,492.46),(375.07,486.97),(368.66,473.24),
    (368.66,471.41),(365.0,465.0),(360.42,452.18),(358.59,450.35),(354.01,438.45),
    (348.52,428.38),(348.52,426.55),(346.69,424.72),(346.69,422.89),(338.45,408.24),
    (338.45,406.41),(340.28,404.58),(355.85,401.83),(356.76,400.92),(361.34,400.92),
    (362.25,400.0),(368.66,400.0),(369.58,399.08),(399.79,399.08),(400.7,400.0),
    (406.2,400.0),(407.11,400.92),(415.35,401.83),(426.34,405.49),(440.99,413.73),
    (442.82,412.82),(442.82,408.24),(427.25,350.56),(429.08,348.73),(434.58,348.73),
    (435.49,349.65),(440.99,349.65),(441.9,350.56),(458.38,350.56),(459.3,351.48),
    (465.7,351.48),(468.45,349.65),(467.54,334.08),(466.62,333.17),(463.87,309.37),
    (462.04,304.79),(462.04,300.21),(457.46,282.82),(457.46,279.15),(456.55,278.24),
    (456.55,274.58),(455.63,273.66),(455.63,270.0),(453.8,265.42),(451.06,249.86),
    (452.89,248.03),(486.76,239.79),(486.76,236.13),(451.97,183.94),(441.9,173.87),
    (419.93,157.39),(421.76,155.56),(429.08,153.73),(436.41,150.07),(444.65,143.66),
    (451.06,136.34),(453.8,130.85),(453.8,125.35),
]

# --- Grid definition (SVG coordinates) ---
GRID_X0 = 40
GRID_Y0 = 95
COL_W = 130
ROW_H = 76.25  # (705-95) / 8

# Category fill colors (RGBA)
CATEGORY_COLORS = {
    'Landmarks': (255, 107, 107, 45),
    'Transport': (78, 205, 196, 45),
    'Food':      (255, 159, 67, 45),
    'Culture':   (162, 155, 254, 45),
    'Nature':    (85, 239, 196, 45),
    'National':  (255, 230, 109, 70),
}

# Zone data: (zone_number, name, category)
ZONES = [
    (1,"Merlion","Landmarks"),(2,"MBS","Landmarks"),(3,"Esplanade","Landmarks"),(4,"Gardens by the Bay","Landmarks"),
    (5,"Singapore Flyer","Landmarks"),(6,"Changi Jewel","Landmarks"),(7,"National Museum","Landmarks"),(8,"Chinatown Gate","Landmarks"),
    (9,"MRT Train","Transport"),(10,"SBS Bus","Transport"),(11,"Bumboat","Transport"),(12,"Cable Car","Transport"),
    (13,"Taxi","Transport"),(14,"Chicken Rice","Food"),(15,"Laksa","Food"),(16,"Ice Kacang","Food"),
    (17,"Roti Prata","Food"),(18,"Satay","Food"),(19,"Kaya Toast + Kopi","Food"),(20,"HDB Flat","Culture"),
    (21,"Void Deck","Culture"),(22,"Dragon Playground","Culture"),(23,"Kopitiam","Culture"),(24,"Pasar Malam","Culture"),
    (25,"Ang Bao","Culture"),(26,"Lion Dance Head","Culture"),(27,"Botanic Gardens","Nature"),(28,"Orchid","Nature"),
    (29,"Otters","Nature"),(30,"Community Cat","Nature"),(31,"Singapore Flag","National"),(32,"National Day Fireworks","National"),
]

IMG_W = 600
IMG_H = 800


def main():
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "puzzle-board-preview.png")

    # Base image: light background
    img = Image.new("RGBA", (IMG_W, IMG_H), (247, 247, 247, 255))

    # --- Step 1: Create silhouette mask ---
    mask = Image.new("L", (IMG_W, IMG_H), 0)
    mask_draw = ImageDraw.Draw(mask)
    flat_pts = [(int(round(x)), int(round(y))) for x, y in MERLION_POINTS]
    mask_draw.polygon(flat_pts, fill=255)

    # --- Step 2: Draw zone rectangles into a separate layer ---
    zones_layer = Image.new("RGBA", (IMG_W, IMG_H), (0, 0, 0, 0))
    z_draw = ImageDraw.Draw(zones_layer, "RGBA")

    for i, (zone_num, name, cat) in enumerate(ZONES):
        row = i // 4
        col = i % 4
        x0 = int(GRID_X0 + col * COL_W)
        y0 = int(GRID_Y0 + row * ROW_H)
        x1 = int(x0 + COL_W) - 1
        y1 = int(y0 + ROW_H) - 1
        fill = CATEGORY_COLORS[cat]
        z_draw.rectangle([(x0, y0), (x1, y1)], fill=fill, outline=(200, 200, 200, 150), width=1)

        # Zone number centered in cell
        try:
            font = ImageFont.truetype("arial.ttf", 15)
        except Exception:
            font = ImageFont.load_default()

        label = str(zone_num)
        bbox = z_draw.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        cx = x0 + (COL_W / 2) - tw / 2
        cy = y0 + (ROW_H / 2) - th / 2
        z_draw.text((cx, cy), label, fill=(90, 106, 122, 220), font=font)

    # --- Step 3: Apply silhouette clip (blank out areas outside Merlion) ---
    white_bg = Image.new("RGBA", (IMG_W, IMG_H), (250, 250, 250, 255))
    clipped = Image.composite(zones_layer, white_bg, mask)

    # --- Step 4: Draw Merlion outline on top ---
    outline_layer = Image.new("RGBA", (IMG_W, IMG_H), (0, 0, 0, 0))
    o_draw = ImageDraw.Draw(outline_layer, "RGBA")
    # Draw outline multiple times for thickness
    for dx, dy in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(1,-1),(-1,1),(1,1),(0,0)]:
        shifted = [(x+dx, y+dy) for x, y in flat_pts]
        o_draw.polygon(shifted, fill=None, outline=(44, 62, 80, 200))

    # Merge everything
    result = Image.alpha_composite(clipped, outline_layer)

    # --- Step 5: Add title and legend ---
    final_draw = ImageDraw.Draw(result, "RGBA")
    try:
        title_font = ImageFont.truetype("arial.ttf", 13)
        leg_font   = ImageFont.truetype("arial.ttf", 10)
    except Exception:
        title_font = ImageFont.load_default()
        leg_font   = title_font

    final_draw.text((8, 8), "Merlion Puzzle Board — 32 zones, real silhouette, 4x8 grid", fill=(44, 62, 80, 200), font=title_font)

    legend = [
        ("Landmarks 1-8",   (255, 107, 107)),
        ("Transport 9-13",  (78,  205, 196)),
        ("Food 14-19",      (255, 159, 67)),
        ("Culture 20-26",   (162, 155, 254)),
        ("Nature 27-30",    (85,  239, 196)),
        ("National 31-32",  (255, 210, 50)),
    ]
    lx, ly = 8, IMG_H - 22
    for label, color in legend:
        final_draw.rectangle([(lx, ly), (lx+10, ly+10)], fill=color+(220,))
        final_draw.text((lx+13, ly), label, fill=(44, 62, 80, 200), font=leg_font)
        bbox = final_draw.textbbox((0,0), label, font=leg_font)
        lx += bbox[2] - bbox[0] + 26

    # Save
    result_rgb = result.convert("RGB")
    result_rgb.save(output_path, "PNG")
    print(f"Preview saved: {output_path}  ({IMG_W}x{IMG_H}px)")


if __name__ == "__main__":
    main()
