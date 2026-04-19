# Art Direction Page — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the art-direction.html page with 4 sample Chunky Flat icons, a puzzle piece preview, an MRT map preview, and Jackie's feedback system — then activate it on the hub.

**Architecture:** Single self-contained HTML file (`art-direction.html`) with inline CSS + JS, following the same pattern as `brief.html`. Uses the existing D1-backed comment API. Worker routes static assets — no new API endpoints needed.

**Tech Stack:** HTML/CSS/JS (inline), SVG icons, Cloudflare Workers, D1 database (existing)

**Security Note:** This is a private design review portal behind password authentication, accessed only by 4 known users (Jackie, Michele, Gabriel, Nex). The comment rendering uses the same `innerHTML` pattern as `brief.html` for comment bubbles. Since all users are authenticated and trusted, and user input is escaped via `escHtml()` (creates a text node and reads `.innerHTML`), this is acceptable for the use case. The same pattern is already deployed and working in `brief.html`.

---

## File Structure

| Action | File | Purpose |
|--------|------|---------|
| Create | `design-hub/art-direction.html` | Full art direction page with icons, previews, feedback |
| Modify | `design-hub/hub.html:463-473` | Change Card 02 from `card-soon` to active `card` link |
| No change | `design-hub/worker.js` | Already serves any `.html` file from assets — no route change needed |

---

### Task 1: Create art-direction.html — Page Shell + Topbar + Hero

**Files:**
- Create: `design-hub/art-direction.html`

- [ ] **Step 1: Create the HTML file with head, topbar, and hero banner**

Create `design-hub/art-direction.html` with the full page shell. Copy the CSS variable and topbar pattern from `brief.html`. Include the Tropical Pop palette variables (`--coral`, `--teal`, `--yellow`, `--orange`, `--purple`, `--mint`). Hero section shows the style name "Chunky Flat — Tropical Pop" with subtitle and 6 palette-dot color swatches.

- [ ] **Step 2: Verify the page loads locally**

Run: `cd design-hub && npx wrangler dev --local`

Open `http://localhost:8787`, log in with `gabriel2026`, navigate to `/art-direction`. Should see the topbar and hero banner with 6 palette dots.

- [ ] **Step 3: Commit**

```bash
git add design-hub/art-direction.html
git commit -m "feat: add art-direction.html shell with topbar and hero banner"
```

---

### Task 2: Add Sample Icons Grid (4 Chunky Flat SVGs)

**Files:**
- Modify: `design-hub/art-direction.html` — add CSS for icon grid + 4 SVG icon cards after the hero section

- [ ] **Step 1: Add icon grid CSS and HTML with 4 SVG icons**

Add a 2x2 responsive grid (single column below 500px). Each card has: icon image area with category-tinted background, SVG icon drawn in Chunky Flat style (3-4px `#2C3E50` outlines, flat fills from Tropical Pop palette), category dot + name + label below, click-to-open chat panel, and comment count badge.

The 4 icons to draw:

1. **Merlion** — coral accent (`#FF6B6B`). Lion head with round shape, spiky mane (coral strokes), fish body (yellow fill), water spout (teal). Simple dot eyes with white highlights.
2. **MRT Train** — teal accent (`#4ECDC4`). Side view: rounded rect body (teal), yellow windows, purple roof unit, coral wheels with center dots, front headlight.
3. **Chicken Rice** — orange accent (`#FF9F43`). Yellow plate ellipse, orange rice mound, yellow chicken slice, mint and coral garnish dots, chopsticks.
4. **HDB Flat** — purple accent (`#A29BFE`). Purple rectangular building with dark roof line, 3 rows of 4 yellow windows, coral door with yellow doorknob, ground line, faint corridor lines.

Each icon SVG uses `viewBox="0 0 200 200"` and renders at 160x160px display size.

- [ ] **Step 2: Verify icons render in browser**

Reload `/art-direction` — should see 4 icon cards in a 2x2 grid, each with distinct SVG artwork, category dot, name, and label.

- [ ] **Step 3: Commit**

```bash
git add design-hub/art-direction.html
git commit -m "feat: add 4 chunky flat sample icons to art direction page"
```

---

### Task 3: Add Puzzle Piece Preview Section

**Files:**
- Modify: `design-hub/art-direction.html` — add puzzle preview section after the icon grid

- [ ] **Step 1: Add puzzle preview section**

Add a section with heading "Merlion Puzzle — Piece Preview". Contains a card with two elements side by side (flex wrap for mobile):

Left side: A jigsaw piece SVG (`viewBox="0 0 140 140"`) — standard piece shape with 2 tabs and 2 slots, drawn with dashed stroke (`stroke-dasharray="6 4"`), filled with light tint, containing a scaled-down Merlion icon (`transform="translate(25, 15) scale(0.5)"` using the same Merlion SVG paths from Task 2).

Right side: Title "32-Piece Merlion Puzzle", description text, and a mini 4x8 CSS grid (32 cells, 18px each, 2px gap). First cell highlighted in coral, rest in grey. Label "A4 PUZZLE LAYOUT (4 x 8)" above the grid.

- [ ] **Step 2: Verify puzzle preview renders**

Reload — should see the jigsaw piece with Merlion inside (dashed outline), plus the 4x8 mini grid with one highlighted cell.

- [ ] **Step 3: Commit**

```bash
git add design-hub/art-direction.html
git commit -m "feat: add puzzle piece preview section to art direction page"
```

---

### Task 4: Add MRT Map Preview Section

**Files:**
- Modify: `design-hub/art-direction.html` — add MRT map preview section after the puzzle section

- [ ] **Step 1: Add MRT map preview section**

Add a section with heading "MRT Sticker Map — Preview". Contains a card with a wide SVG (`viewBox="0 0 700 200"`, `width="100%"`):

- Horizontal teal line (`stroke-width="6"`) representing the East-West line
- 4 station dots (white circles with dark stroke) at: Raffles Place, Marina Bay, Bayfront, Gardens by the Bay
- Station name labels below each dot (Nunito font, 11px, centered)
- 3 mini icons placed above their stations:
  - **MBS** at Marina Bay: 3 purple rectangles with coral curved roof line
  - **Merlion** at Bayfront: tiny scaled version of the Merlion (body + head + mane + eyes)
  - **Supertree** at Gardens: green trunk + leaf canopy ellipse + small flower dots
- Label at bottom: "Icons shown at approximate sticker size (~50px)"
- Description text below the SVG: "Kids place sticker icons at their MRT stations..."

- [ ] **Step 2: Verify map preview renders**

Reload — horizontal line with 4 stations, 3 mini icons above their stations, labels below.

- [ ] **Step 3: Commit**

```bash
git add design-hub/art-direction.html
git commit -m "feat: add MRT map preview section to art direction page"
```

---

### Task 5: Add Feedback Section + Lobby Chat FAB + JavaScript

**Files:**
- Modify: `design-hub/art-direction.html` — add feedback questions, lobby FAB, and all JavaScript

- [ ] **Step 1: Add feedback section HTML**

Add section heading "Your Feedback" and 3 feedback cards:
- Q1: "Does this illustration style feel right for a Singapore heritage sticker book?"
- Q2: "Are the icons clear and recognizable at small sticker size?"
- Q3: "Any changes you'd like to the color palette or level of detail?"

Each card has: question text as `<h3>`, a `<textarea>` with placeholder "Share your thoughts...", a save row with status text span and "Save" button. Use IDs: `textarea-art-q1`, `status-art-q1`, etc.

- [ ] **Step 2: Add lobby chat FAB HTML**

Add a fixed-position coral FAB button (bottom-right, 56px circle) and a slide-up panel (320px wide, rounded corners, shadow) with header "General Discussion", scrollable messages area, and input row with send button. Same visual pattern as `brief.html` and `hub.html` lobby.

- [ ] **Step 3: Add footer**

```html
<footer>Made by <strong>Gabriel</strong> and <strong>Nex</strong> &mdash; April 2026</footer>
```

- [ ] **Step 4: Add JavaScript**

Add a `<script>` block before `</body>` implementing:

**State & Init:**
- `currentUser` fetched from `GET /api/me`
- `AUTHOR_COLORS` object: Jackie=#3498DB, Michele=#E74C3C, Gabriel=#27AE60, Nex=#FF9F43
- On load: fetch user identity, load comment counts for all 4 icons, load saved responses for Q1-Q3

**Helper functions:**
- `formatTime(iso)` — returns HH:MM string
- `escHtml(str)` — creates a temporary `div` element, sets `textContent` to the input string, reads back the element's `innerHTML` property to get the escaped version. This is the standard DOM-based escaping pattern.
- `renderBubble(comment)` — returns HTML string for a chat bubble with author (colored), escaped message, timestamp, and conditional delete button (visible on hover, only for author/Gabriel/Nex). Uses `escHtml()` to sanitize message content before rendering.

**Icon chat functions:**
- `toggleIconChat(card)` — close all open chats, toggle clicked card's chat panel, load comments, focus input
- `loadIconComments(iconId)` — fetch from `/api/comments?icon_id=X`, render bubbles into messages container
- `loadCommentCount(iconId)` — fetch comments, update badge count and visibility
- `sendIconComment(iconId)` — POST to `/api/comments`, reload comments and count
- Enter key handler on `.chat-input-row input` elements

**Delete function:**
- `deleteComment(commentId, iconId)` — DELETE to `/api/comments/:id`, reload appropriate comment list

**Feedback response functions:**
- `loadResponse(questionId)` — fetch comments for the question ID, find current user's response, populate textarea
- `saveResponse(questionId)` — delete existing response if any, POST new response, update status text

**Lobby functions:**
- `toggleLobby()` — toggle panel visibility, load comments on open, focus input
- `loadLobbyComments()` — fetch lobby comments, render bubbles
- `sendLobbyComment()` — POST lobby message, reload
- Enter key handler on lobby input

All functions follow the same patterns used in `brief.html` — the agent should reference `brief.html` for the exact implementation patterns.

- [ ] **Step 5: Verify the complete page works**

Reload `/art-direction`. Test:
1. All 4 icons visible in 2x2 grid
2. Click an icon card — chat panel opens
3. Type a comment, press Enter — bubble appears
4. Puzzle piece and MRT map sections visible
5. Type in Q1 textarea, click Save, refresh — response persists
6. Lobby FAB opens chat panel, can send messages

- [ ] **Step 6: Commit**

```bash
git add design-hub/art-direction.html
git commit -m "feat: add feedback system, lobby chat, and JS to art direction page"
```

---

### Task 6: Activate Art Direction Card on Hub Page

**Files:**
- Modify: `design-hub/hub.html:442-473`

- [ ] **Step 1: Move Card 02 from coming-soon to active**

In `hub.html`, find the "Coming Soon" section and remove the Card 02 block (the `card-soon` div with "Art Direction").

Then in the "Ready for review" grid (the one containing Card 01 Brief), add Card 02 as an active card after Card 01:

```html
      <!-- Card 02 — Active -->
      <a href="/art-direction.html" class="card">
        <div class="card-number" aria-hidden="true">02</div>
        <div class="card-title">Art Direction</div>
        <div class="card-desc">
          Chunky Flat style with Tropical Pop palette &mdash; review the sample icons and previews.
        </div>
        <div class="card-footer">
          <span class="card-badge badge-active">Ready</span>
          <span class="card-arrow" aria-hidden="true">&#8594;</span>
        </div>
      </a>
```

- [ ] **Step 2: Verify hub page**

Navigate to `/hub`:
- "Ready for review" has 2 cards (Brief + Art Direction)
- Art Direction card links to `/art-direction`
- "Coming soon" has 4 remaining cards (03-06)

- [ ] **Step 3: Commit**

```bash
git add design-hub/hub.html
git commit -m "feat: activate art direction card on hub page"
```

---

### Task 7: Deploy to Cloudflare Workers

**Files:**
- No file changes — deployment only

- [ ] **Step 1: Deploy**

```bash
cd design-hub && npx wrangler deploy
```

Expected: `Published littledotbook-design ...`

- [ ] **Step 2: Verify production**

Open `https://littledotbook-design.bc-chew.workers.dev`:
1. Log in with `gabriel2026`
2. Hub shows Art Direction card as active (02)
3. Click through — all sections render
4. Feedback system works (post + persist)
5. Lobby chat works

- [ ] **Step 3: Commit deployment confirmation**

```bash
git commit --allow-empty -m "chore: deploy art direction page to production"
```

---

## Summary

| Task | What | Files |
|------|------|-------|
| 1 | Page shell + topbar + hero | Create `art-direction.html` |
| 2 | 4 Chunky Flat SVG icons grid | Modify `art-direction.html` |
| 3 | Puzzle piece preview section | Modify `art-direction.html` |
| 4 | MRT map preview section | Modify `art-direction.html` |
| 5 | Feedback questions + lobby chat + JS | Modify `art-direction.html` |
| 6 | Activate hub card | Modify `hub.html` |
| 7 | Deploy to Cloudflare | No file changes |
