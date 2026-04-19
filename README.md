# Little Dot Book — My Singapore Stories: Book 2 (Merlion Puzzle)

**Authors:** Jackie Ang & Michele Ang
**Publisher:** Little Dot Book
**Series:** My Singapore Stories

---

## Project Goal

Design a print-ready A4 pull-out puzzle page for Book 2 of the "My Singapore Stories" series.

The page features a **Merlion silhouette** divided into **32 interlocking puzzle pieces**. Each piece is a distinct Singapore landmark, food, or cultural icon. Kids assemble the puzzle by matching stickers to the corresponding piece shapes inside the Merlion outline.

**Target audience:** Children ages 4–8
**Output:** Print-ready artwork, correct A4 dimensions with bleed, CMYK-ready

---

## Asset Inventory

### Merlion Silhouette
- `design-hub/assets/merlion-silhouette.svg` — primary SVG silhouette used as the puzzle boundary
- `design-hub/assets/merlion-silhouette-preview.png` — raster preview
- `design-hub/assets/merlion-preview.png` — alternate preview
- `design-hub/assets/puzzle-board-preview.png` — full puzzle board preview
- `design-hub/assets/merlion-puzzle-a4-mockup.png` — A4 page mockup

### Sticker Icons (32 Singapore landmarks and icons)
Located in `design-hub/assets/icons/` (originals) and `design-hub/assets/icons/labeled/` (with bubble labels):

**Landmarks**
| # | Icon |
|---|------|
| 1 | Merlion |
| 2 | Marina Bay Sands (MBS) |
| 3 | Esplanade |
| 4 | Gardens by the Bay |
| 5 | Singapore Flyer |
| 6 | Changi Jewel |
| 7 | National Museum |
| 8 | Chinatown Gate |

**Transport**
| # | Icon |
|---|------|
| 9 | MRT Train |
| 10 | SBS Bus |
| 11 | Bumboat |
| 12 | Cable Car |
| 13 | Taxi |

**Food**
| # | Icon |
|---|------|
| 14 | Chicken Rice |
| 15 | Laksa |
| 16 | Ice Kacang |
| 17 | Roti Prata |
| 18 | Satay |
| 19 | Kaya Toast + Kopi |

**Culture / Community**
| # | Icon |
|---|------|
| 20 | HDB Flat |
| 21 | Void Deck |
| 22 | Dragon Playground |
| 23 | Kopitiam |
| 24 | Pasar Malam |
| 25 | Ang Bao |
| 26 | Lion Dance Head |

**Nature**
| # | Icon |
|---|------|
| 27 | Botanic Gardens / Rain Tree |
| 28 | Orchid |
| 29 | Otters |
| 30 | Community Cat |

**National**
| # | Icon |
|---|------|
| 31 | Singapore Flag |
| 32 | National Day Fireworks |

Also in `design-hub/assets/icons/varients/` — alternate style variants for Merlion, MBS, and Esplanade icons.

### Python Mockup Scripts
Located in `design-hub/assets/`:
- `generate_a4_mockup.py` — v1, initial A4 layout
- `generate_a4_mockup_v2.py` — v2, iteration
- `generate_a4_mockup_v3.py` — v3, iteration
- `generate_a4_mockup_v4.py` — v4, latest mockup generator

Additional scripts in `design-hub/`:
- `extract_merlion_silhouette.py` — extracts the Merlion outline from source
- `generate_puzzle_preview.py` — generates puzzle board preview image
- `assets/icons/add_labels.py` — adds text labels to icon PNGs
- `assets/icons/add_bubble_labels.py` — adds bubble-style labels
- `assets/icons/curved_bubble_labels.py` — curved bubble label variant

### Design Hub HTML Files
Located in `design-hub/`:
- `hub.html` — main design hub index
- `brief.html` — project brief
- `art-direction.html` — art direction reference
- `icons.html` — icon gallery
- `puzzle-layout.html` — puzzle layout reference
- `puzzle-mockup.html` — mockup viewer

---

## Status

Design in progress. All 32 sticker icons are complete. Merlion SVG silhouette is finalized. A4 mockup layout is being refined for print-ready output.

Ready for design iteration via claude.ai/design.
