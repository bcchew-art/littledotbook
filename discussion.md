# Discussion: Merlion Puzzle A4 — 32 Stickers, Fresh Eyes Needed

**To:** Codex (GPT-5)
**From:** Nex (Claude Opus, orchestrator) on Gabriel's behalf
**Status:** 13 iterations in, stuck. Need a different brain.
**Date:** 2026-04-21

---

## Project

**Little Dot Book — Book 2: "My Singapore Stories Vol.2"**, a children's sticker book by Jackie Ang (author) for the Singapore market, publisher Little Dot Book. Target age 4–8.

The book ships with an **A4 pull-out puzzle page**. Kids get a sheet of 32 pre-printed Singapore landmark stickers and paste each one inside the Merlion silhouette on the A4 page.

Repo: https://github.com/bcchew-art/littledotbook (public)

---

## What we have

### 1. Merlion silhouette
- `assets/merlion-silhouette.svg` — 318-point polygon, viewBox `0 0 600 800`
- This is the A4 cut-out shape. Everything must fit inside.

### 2. 32 labeled stickers (the "Phase 3" art)
- `design-hub/assets/icons/labeled/` — 32 PNGs
- Filenames: `#1 Merlion.png`, `#2 MBS.png`, ... `#32 National Day Fireworks.png`
- Full-canvas 1024×1024 (except #14 Chicken Rice at 1254×1254)
- **Background is white (not transparent).** Each sticker has curvy white-outlined text with the landmark name baked in below the icon, with a proper die-cut sticker border.
- Categories:
  - **Landmarks** (1–8): Merlion, MBS, Esplanade, Gardens by the Bay, Singapore Flyer, Changi Jewel, National Museum, Chinatown Gate
  - **Transport** (9–14): MRT Train, SBS Bus, Bumboat, Cable Car, Taxi, (14 is Chicken Rice — mis-categorized; treat as Food)
  - **Food** (14–19): Chicken Rice, Laksa, Ice Kacang, Roti Prata, Satay, Kaya Toast + Kopi
  - **Culture / Local Life** (20–25): HDB Flat, Void Deck, Dragon Playground, Kopitiam, Pasar Malam, Ang Bao
  - **Nature** (26–29): Lion Dance Head, Botanic Gardens, Orchid, Otters
  - **National** (30–32): Community Cat, Singapore Flag, National Day Fireworks

### 3. Thirteen prior attempts
- `design-hub/assets/generate_a4_mockup_v1.py` ... `_v13.py`
- Progression: puzzle-piece tessellation → shape-sorter → jigsaw → equal-area organic cuts → region split → Voronoi Lloyd's relaxation → sticker packing
- Latest output: `design-hub/assets/merlion-puzzle-a4-v13.png`

---

## Why we're stuck

Every iteration has traded one problem for another:
- Equal-area tessellation → pieces span body/tail weirdly
- Voronoi packing → stickers end up very different sizes because cell sizes vary
- Forced equal sizing → some stickers get stretched/squashed and lose their natural proportions

Gabriel's latest feedback on v13:
> "why is the mrt train text so much bigger than the taxi one. some sticker just look way bigger for some reason. sheesh.. how about this.. make me a react page.. i move the sticker on my own?"

The core insight: **we've been scaling the stickers to fit cells, when we should preserve their natural sizes and arrange them to fit the Merlion.**

---

## The brief — what we actually want

Place all 32 labeled stickers inside the Merlion silhouette so that:

1. **Keep original sticker sizes.** Do NOT scale to equal size. Each sticker's natural drawn size (at its source PNG) stays the same. The Merlion (sticker #1) is naturally big; the Taxi (sticker #13) is naturally small. Respect that.

2. **Remove the white backgrounds.** Auto-crop to content bbox + make the white background transparent. Script already exists for a bare-icon version in `design-hub/assets/icons/cropped/` — but for this task Gabriel wants the **labeled** versions (names baked in) with transparent backgrounds. Folder to create: `design-hub/assets/icons/labeled-cropped/`.

3. **All 32 fit inside the Merlion silhouette.** No sticker escapes the silhouette boundary. The silhouette outline is the print cut line.

4. **Equal spacing between stickers.** Consistent breathing room between every pair of neighbours. Not Voronoi (which gives per-cell variable space) — a uniform visual gap.

5. **Smart placement, not mechanical.** You may rearrange sticker order. Gabriel's example:
   > "he can use the taxi for the merlion below jaw because its the only one that would fit there nicely"
   
   So small stickers naturally fit in the Merlion's narrow regions (jaw, paws, tail fin). Big stickers go in the wide regions (main body, mane).

6. **No cut lines on the output.** Gabriel will draw the puzzle cut lines himself in Illustrator after placement.

---

## What "done" looks like

- `merlion-puzzle-a4-v14.png` at 1240×1754 (A4 @ 150 DPI)
- All 32 labeled stickers placed, natural sizes preserved, transparent backgrounds
- All inside silhouette, no overlaps, even spacing
- Silhouette outline drawn subtly for reference

Page chrome (copy from v13 / phase 3):
- Title: "My Singapore Stories Vol.2" (Arial Bold 52pt, dark blue `#193773`)
- Subtitle: "The Merlion Puzzle" (34pt, reddish orange `#D74B37`)
- Instruction: "Match each sticker to its place on the Merlion!" (25pt, dark grey `#4B4B5F`)
- Footer: "Little Dot Book  ·  My Singapore Stories Vol.2"

---

## Idea Gabriel wants to try: GPT Image 2.0

Instead of fighting geometry in Python, could we just generate the composition with GPT Image 2.0 / a vision-capable image model?

Rough prompt idea:
> "A cream-background A4 page titled 'My Singapore Stories Vol.2'. Inside a Merlion silhouette outline, evenly arrange these 32 labeled sticker illustrations [attach each]. Preserve each sticker's original size and its white die-cut border. Even spacing between stickers. Small stickers fit into narrow regions (jaw, paws, tail fin), large stickers into wide regions (body, mane)."

Unknown: does GPT Image 2.0 respect input sticker sizes and compositing precisely enough for print? Or will it re-render the stickers (losing Jackie's art)?

**Your call on approach:**
- **Path A (image gen):** Try GPT Image 2.0 or similar. If it can preserve the 32 sticker images exactly while composing the layout, ship it.
- **Path B (algorithm):** Pack stickers using a physics-based approach (start with random scattered positions at natural size → iteratively repel overlaps + attract to silhouette centre → stop when stable with even gaps). No scaling.
- **Path C (hybrid):** Use image gen for a layout *suggestion* (positions only), then render the actual sticker PNGs into those positions in Python so art fidelity is perfect.
- **Path D (interactive):** Build a React page where Gabriel drags the 32 stickers into the silhouette manually, exports PNG. This was his fallback suggestion if AI can't deliver.

Gabriel will judge on output quality. Don't spend weeks — one solid attempt at your best approach, report back with the PNG.

---

## Constraints

- Print-ready A4 @ 150 DPI (1240×1754 px), RGB output (CMYK conversion later)
- Do NOT modify the 32 source PNGs — only the cropped copies
- Work in `C:/Users/Admin/Projects/oinio/littledotbook/` (the standalone repo)
- Commit to `bcchew-art/littledotbook` on GitHub
- The silhouette has concavities (mouth opening, tongue, space between tail and body) — respect them

---

## Questions for you

1. Can GPT Image 2.0 actually preserve 32 specific input images at specific sizes in a composed output? Or does it always re-render from prompt?
2. If A is unreliable, path B or C? Gabriel's latest nudge leans toward path D (interactive React).
3. Any fundamentally different approach we haven't tried?

**Pick a path, justify it briefly, execute it.** Gabriel trusts your judgment — 13 iterations of mine haven't nailed it.

---

## Pointers

- Latest failed attempt: `design-hub/assets/generate_a4_mockup_v13.py` + `merlion-puzzle-a4-v13.png`
- Phase 3 styling reference: `design-hub/assets/generate_a4_mockup_v3.py` (lines 364–524 for fonts/text)
- Original sticker source: `design-hub/assets/icons/labeled/`
- Bare icons (no name): `design-hub/assets/icons/cropped/` (already transparent)
- Silhouette: `assets/merlion-silhouette.svg`

Good luck, Codex. Ping back with your pick and the output.

— Nex
