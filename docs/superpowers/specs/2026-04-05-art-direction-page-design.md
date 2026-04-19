# Art Direction Page — Design Spec

**Date:** 2026-04-05
**Sprint:** 2 (Art Direction)
**Page:** `art-direction.html`
**Deployed to:** `littledotbook-design` Cloudflare Worker

---

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Illustration style | Chunky Flat | Bold outlines, flat fills, max readability for age 3-6 stickers |
| Color palette | Tropical Pop | Coral, teal, yellow, orange, purple, mint — high energy, sunny Singapore |
| Page scope | Full Showcase | 4 sample icons + puzzle piece preview + MRT map preview |

---

## Style: Chunky Flat

### Rules (apply to all 32 icons)

- **Outlines:** 3-4px black (#2C3E50) stroke, `stroke-linejoin: round`, `stroke-linecap: round`
- **Fills:** Flat solid colors from Tropical Pop palette. No gradients, no textures, no shadows.
- **Detail level:** 2-3 defining features per icon maximum. Simplify aggressively.
- **Eyes/faces:** Only on living things (Merlion, Otters, Community Cat, Lion Dance Head). Simple dot eyes with white highlight. No faces on buildings, food, or objects.
- **ViewBox:** 200x200 SVG. Must read clearly at 40px (sticker thumbnail) and 200px (full display).
- **Corners:** Rounded everywhere — `rx` on rects, rounded path joins.

### Tropical Pop Palette

| Color | Hex | Usage |
|-------|-----|-------|
| Coral | #FF6B6B | Landmarks accent, highlights |
| Teal | #4ECDC4 | Transport accent, water |
| Yellow | #FFE66D | National symbols, warmth |
| Orange | #FF9F43 | Food & Hawker accent |
| Purple | #A29BFE | Culture & Daily Life accent |
| Mint | #55EFC4 | Nature & Animals accent |
| Dark | #2C3E50 | Outlines, text |
| Light | #F7F7F7 | Backgrounds |

### Category Color Coding

Each icon category gets a dominant accent:

- **Landmarks (8):** Coral (#FF6B6B)
- **Transport (5):** Teal (#4ECDC4)
- **Food & Hawker (6):** Orange (#FF9F43)
- **Culture & Daily Life (7):** Purple (#A29BFE)
- **Nature & Animals (4):** Mint (#55EFC4)
- **National Symbols (2):** Yellow (#FFE66D)

---

## Page Structure: art-direction.html

### Layout (top to bottom)

**1. Topbar** (sticky)
- Back button → `/hub`
- Title: "Art Direction"
- Logout button (top-right)
- Matches `brief.html` topbar exactly

**2. Hero Banner**
- Heading: "Chunky Flat — Tropical Pop"
- Subtitle: "Bold outlines, flat bright fills, maximum readability for tiny hands."
- 6 palette swatches displayed as colored circles in a row
- Light background (#F7F7F7)

**3. Sample Icons Grid** (2x2)
- 4 large Chunky Flat SVG icons on white cards:
  - **Merlion** (Landmark — coral accent)
  - **MRT Train** (Transport — teal accent)
  - **Chicken Rice** (Food — orange accent)
  - **HDB Flat** (Culture — purple accent)
- Each card: white background, subtle shadow, icon name + category label below
- Icons rendered at ~180px display size
- Cards are clickable — tap opens per-icon feedback chat (same system as brief.html)

**4. Puzzle Piece Preview**
- Section heading: "Merlion Puzzle — Piece Preview"
- One jigsaw piece shape (standard: 2 tabs out, 2 slots in) containing the Merlion icon
- Thick dashed outline suggesting "cut here"
- Below: a mini 4x8 grid outline (32 cells) with one cell highlighted to show where this piece fits
- Descriptive text: "Each of the 32 icons becomes a puzzle piece. Kids assemble the Merlion silhouette by matching stickers to shapes."

**5. MRT Map Preview**
- Section heading: "MRT Sticker Map — Preview"
- Simplified horizontal East-West line segment with 4-5 station dots
- Station labels: "Marina Bay", "Bayfront", "Gardens by the Bay", plus 1-2 others
- 3 sample sticker icons placed at their stations:
  - MBS → Marina Bay station
  - Merlion → near Marina Bay
  - Gardens by the Bay → Gardens station
- Icons shown at sticker-size (~50px) to demonstrate readability at actual use scale
- Map line: simple colored line + circle station dots. Not a full MRT diagram.

**6. Feedback Section**
- 3 feedback questions with response boxes (same Q&A system as brief.html):
  - Q1: "Does this illustration style feel right for a Singapore heritage sticker book?"
  - Q2: "Are the icons clear and recognizable at small sticker size?"
  - Q3: "Any changes you'd like to the color palette or level of detail?"
- One response per person, editable, Save button

**7. Floating Lobby Chat FAB**
- Bottom-right corner, same as hub.html and brief.html
- General discussion thread (icon_id: lobby)

---

## Technical Details

### File Location
`design-hub/art-direction.html` — single self-contained HTML file (inline CSS + JS), same pattern as `brief.html`.

### API Integration
Uses existing endpoints — no new API routes needed:
- `GET /api/me` — identity
- `GET /api/comments?icon_id=XX` — load feedback
- `POST /api/comments` — submit feedback
- `DELETE /api/comments/:id` — soft-delete

### New icon_id Values
- Per-icon chats: `art-merlion`, `art-mrt`, `art-chickenrice`, `art-hdb`
- Feedback questions: `art-q1`, `art-q2`, `art-q3`
- Lobby: `lobby` (shared across pages)

### Hub Page Update
- The "Art Direction" card on hub.html changes from "Coming Soon" to active (links to `/art-direction`)

### Worker Route
- Add `/art-direction` route to `worker.js` serving `art-direction.html`
- Worker already handles `.html` extension stripping

---

## Sample Icons to Produce

4 icons in Chunky Flat + Tropical Pop style:

1. **Merlion** — lion head with spiky mane (coral), fish body (yellow), water spout (teal). Sitting on water base.
2. **MRT Train** — rounded rectangle body (teal), yellow windows, coral wheels, purple roof unit. Simple side view.
3. **Chicken Rice** — plate/bowl (yellow), rice mound (orange), garnish dots (coral + mint). Top-down or 3/4 view.
4. **HDB Flat** — rectangular building (purple), grid of yellow windows, coral door at bottom. Frontal view.

---

## Out of Scope (Future Sprints)

- Full 32-icon production (Sprint 3)
- Actual puzzle piece layout and cutting guides (Sprint 4)
- Full MRT map with all stations (Sprint 5)
- Cover design (Sprint 5)
- Print-ready CMYK conversion (Sprint 5)
