# Hack Hamster — Hackathon Judging Platform Logo Brief

## Brand context

**Hack Hamster** is a hackathon judging platform. It hosts the full judging cycle — submissions, multi-criteria scoring (rubrics + sliders + comments), pairwise comparison (Bradley–Terry), community voting, audit-grade trails, signed certificates. The audience is four-way: organizers running the event, judges scoring projects, participants submitting, and public visitors browsing the gallery.

The product feels professional and modern. The visual language across the existing design system (which the logo must harmonize with) is dark-first, sophisticated, with a violet primary and amber accent. Geist is the type system.

The logo will be the anchor — wordmark, symbol, colors, all visible on a public landing page, an organizer dashboard, an embeddable widget, and a signed certificate. It needs to hold up at 16px favicon and at 200px hero size.

---

## Name

**"Hack Hamster"** — single word, lowercase typesetting preferred for the wordmark (`hack-hamster.` with the trailing period as the brand device — same trick Linear and Notion used). The period is part of the identity, not optional.

Pronounced /ˈlɛdʒər/. Does NOT need to be explained — it lands as "where records are kept," which is exactly what the product does.

---

## Visual direction

**One sentence concept**: A geometric mark that reads as both a folded hack-hamster page and a balanced scale, paired with a precise modern wordmark.

**Mood**: Considered. Precise. Quietly confident. No trophies, no checkmarks, no flame emojis, no AI gradient orbs, no swooshes. The mark should look like it was drawn with a compass, not a mouse.

**References for taste (do not copy)**:
- Linear's mark — geometric, monochromatic, reads at small size
- Vercel's wordmark — lowercase, period as brand device, tight tracking
- Stripe's logo — sophisticated restraint, scales to favicon
- IBM's eight-bar logo — mathematical, constructed on a grid
- Nothing from Dribbble "judge" or "voting" tags — those are full of clichés

---

## Color system — use exactly these

The brand sits in the existing design system, so the logo must look like it belongs.

```
Primary mark color (dark mode):  #8B5CF6   violet-500
Primary mark color (light mode): #6D28D9   violet-700
Accent (use sparingly, never on its own): #F59E0B   amber-500
Deep ink (monochrome variant):  #0A0A0F   near-black
Surface (for reverse-on-color):  #FAFAFA   near-white
```

Rules:
- Default mark color: violet (`#8B5CF6` on dark surfaces, `#6D28D9` on light surfaces)
- Never use amber on the logo itself — amber is for accents in the product UI (CTAs, hover states), not the brand mark
- Never use a gradient on the logo. The brand is monochromatic and confident
- Provide monochrome (all-ink) and reversed (all-surface) variants for one-color print, embroidery, watermarks

---

## Symbol / mark — concept

**Primary concept (recommended)**: An abstracted **"L"** built from two stacked rectangular bars of unequal length, aligned to a 4×6 grid. The longer bar is the base, the shorter bar sits above it flush to the left, suggesting both a folded paper edge AND a scale arm. There's a single 1px notch cut into the inner corner of the top bar — a "tab" or "tick" that hints at hack-hamster rows without being literal.

**Secondary concept (if primary feels too austere)**: A geometric **"balance mark"** — two triangular weights hanging from a horizontal beam, abstracted into a triangle-and-bar composition that reads as both a scale and the letter L if you squint.

**Avoid**:
- Anything that looks like a "✓" or a flame or a trophy or a graduation cap
- Rounded organic shapes — the mark must feel constructed, not drawn
- Three or more colors
- Any letter other than "L" being readable in the mark (we don't want a "D" hidden inside)
- Drop shadows, bevels, gradients

---

## Geometry constraints (for the primary concept)

The mark is built on a **6×8 unit grid** (the units are arbitrary — just pick one):

```
████████████████████  ←  long bar (5 units tall × 6 wide)
████                  ←  short bar (3 units tall × 4 wide)
```

Specific proportions:
- Long bar: **5 units tall × 6 units wide**, top-left corner aligned to grid
- Short bar: **3 units tall × 4 units wide**, sitting directly above the long bar with **0 unit gap** (touching, forming an "L" silhouette)
- Inner corner notch on the short bar: **1 unit × 1 unit** cut out of the bottom-right corner, creating a small step that reads as a "tab"
- All corners: **0.5 unit radius** (subtle, not pill-shaped) — keeps the mark modern, not brutalist
- Both bars: **solid fill**, no outline, no gradient, no inner stroke
- Optical balance: the short bar is left-aligned with the long bar (so the "L" reads clearly)

The mark fits in a **6×8 bounding box** with **1 unit padding** on all sides (so the SVG viewBox is `0 0 8 10` if you want to bake in the padding).

---

## Wordmark

**Typeface**: Geist Sans (the product's existing typeface — do NOT use a different font).

**Typesetting**:
- Lowercase `hack-hamster` followed by a period `.`
- The period is **enlarged** to match the x-height of the lowercase letters (it's a brand device, not a punctuation mark). Cap it at 1.4× the lowercase x-height so it doesn't look like a typo
- Weight: **Medium (500)** — not Light, not Regular, not Bold. Medium is the sweet spot for "considered"
- Tracking: **-0.02em** (slightly tight — gives it a precise, custom-feel)
- Color: deep ink `#0A0A0F` on light surfaces, surface `#FAFAFA` on dark surfaces
- Always set in **Geist Medium** — never Geist Regular, never Geist Bold, never Geist Mono

**Sizing relationship to the mark**:
- When the mark sits to the LEFT of the wordmark (horizontal lockup): mark height = wordmark x-height × 2.4 (so the mark feels substantial, not equal-sized)
- When the mark sits ABOVE the wordmark (stacked lockup): mark width = wordmark width × 0.9 (slightly narrower than the text so it looks centered)

**Clearspace**:
- Minimum clearspace around the lockup = 1× the cap height of the wordmark
- No other element, text, or graphic may enter this space

---

## Required variants (deliverables)

Generate each as a separate render, on the right background:

1. **Primary horizontal lockup** — mark left, wordmark right, on dark (`#0A0A0F`) background
2. **Primary horizontal lockup** — same, on light (`#FAFAFA`) background
3. **Stacked lockup** — mark above, wordmark below, centered, on dark
4. **Mark only** — just the symbol, on dark (for favicon, app icon, social avatar)
5. **Mark only** — just the symbol, on light
6. **Wordmark only** — just `hack-hamster.` on dark
7. **Wordmark only** — just `hack-hamster.` on light
8. **Monochrome all-ink** — entire lockup in single color (`#0A0A0F`), for use on light backgrounds where violet doesn't print
9. **Monochrome reversed** — entire lockup in single color (`#FAFAFA`), for use on dark photographic backgrounds
10. **Favicon-size mark** — at 16×16 and 32×32 to verify the mark reads at favicon scale (no tiny details that disappear)

---

## Specific use cases to optimize for

- **Favicon (16×16, 32×32)**: mark must be readable — no thin lines that vanish, no internal detail that disappears. The "tab notch" should still be visible at 32px
- **App icon (1024×1024)**: mark centered in a rounded-square with `bg = #8B5CF6` and the mark in surface `#FAFAFA` (reversed). 22% corner radius (iOS-style "squircle" feel)
- **Embeddable widget header (24px tall)**: horizontal lockup, mark height = 24px, wordmark set in 14px Geist Medium
- **Certificate header (printed at A4)**: stacked lockup, mark = 40mm wide, wordmark below in 24pt Geist Medium
- **GitHub social card (1280×640)**: dark background, horizontal lockup centered, mark + wordmark, no other text

---

## What to AVOID

- ❌ Any gradient on the logo itself (no "AI slop" gradient text, no gradient mark)
- ❌ More than two colors anywhere in the logo
- ❌ Drop shadows, glows, bevels, embossed effects
- ❌ Stock-photo imagery (trophies, ribbons, flames, books, scales drawn literally)
- ❌ Cursive, script, or handwritten typefaces
- ❌ Mixing two typefaces (the wordmark is Geist Medium — period)
- ❌ A period that looks like a typo (it must be enlarged to feel intentional)
- ❌ Round, organic, or hand-drawn shapes — the mark is constructed
- ❌ Reading as a "D", "C", "G", or any letter besides L
- ❌ A checkmark, vote box, ballot, or any literal judging metaphor
- ❌ Light or thin weights (the mark feels underconfident if it's too delicate)
- ❌ Centered period with a regular-size dot

---

## Deliverables

Generate **all 10 variants** in this generation pass. After the primary horizontal lockup (variant 1) is approved, derive the rest from the same construction — same mark, same wordmark proportions, just different background + color treatment.

Render each at:
- **Vector-style** (geometric, sharp edges, no raster noise) — even though the output will be raster, the construction should feel vector
- **High resolution** — at least 2048×2048 for the mark-only variants, 4096×1024 for horizontal lockups
- **Transparent background** for the mark-only and monochrome variants; the dark/light lockups can have their background as a solid color

---

## Final composition check (before declaring done)

The approved logo should pass these five tests:

1. **At 16px favicon**: the mark reads as "an L" — not as a blob, not as a D
2. **At 24px embed header**: `hack-hamster.` is legible without zooming
3. **On a dark hero (`#0A0A0F`)**: the violet mark has presence without screaming; the wordmark in surface white is calm
4. **On a white certificate**: the ink-black monochrome variant prints cleanly at any size
5. **Next to the existing product UI**: it looks like it belongs in the same product family as the After-Hours Indigo design system — same temperature, same level of restraint, same lack of decoration

If any variant fails one of these tests, regenerate the underlying mark before locking the family.

---

## Style keywords for GPT-6 generation prompt

Use these in your generation prompt to steer the output:

> "minimal geometric logo, single letterform mark, constructed on a strict grid, modern sans-serif wordmark, monochrome with optional accent, professional and restrained, suitable for a software platform, dark-mode first, no decoration, no gradients, no metaphors, mathematical, precise, considered"

**Negative keywords** (avoid these in the generation prompt):

> "no trophy, no flame, no gradient, no AI glow, no script font, no cursive, no drop shadow, no organic shapes, no emoji, no three colors, no checkmark"

---

**Generate all 10 variants now. Show them in this order so the construction is visible: variant 1 first (so the primary lockup is the reference), then 2, 3, 4, 5, 6, 7, 8, 9, 10. After delivery, walk through the 5 final-composition checks.**
