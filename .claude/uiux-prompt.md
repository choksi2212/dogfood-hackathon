# HACK HAMSTER Hackathon Portal — Complete UI/UX Overhaul Brief

## Mission

You are redesigning the entire frontend of the HACK HAMSTER hackathon judging portal — a professional, modern, aesthetically distinctive web app used by hackathon organizers, judges, participants, and public visitors during the 2026 hackathon judging cycle.

**The result must look like a paid product, not a template.** Distinctive design language, real typography hierarchy, considered microinteractions, no lorem-ipsum placeholders. Ship something the team would proudly show at the demo.

**Tech stack is locked.** You are NOT choosing libraries. Use exactly what's listed below. The backend, API contracts, and data shapes are frozen — your job is the visual layer only.

**Scope guard — read this three times.**
- ✅ Touch ONLY files inside `web/` (the Next.js app)
- ✅ Add new dependencies to `web/package.json` and run `npm install`
- ❌ Do NOT touch `apps/`, `config/`, `tests/`, `openapi.yaml`, root configs
- ❌ Do NOT modify any API client signature in `web/lib/api/` beyond adding new helpers if absolutely needed
- ❌ Do NOT change any API route path or response shape
- ❌ Do NOT touch `web/app/api/`, `web/middleware.ts`, or auth wiring

---

## Tech Stack (use exactly this)

- **Next.js 16** App Router (`web/app/...`)
- **Tailwind v4** with the `@tailwindcss/postcss` plugin (already wired)
- **shadcn/ui** primitives under `web/components/ui/*` (already wired — Card, Button, Badge, Alert, AlertDialog, Dialog, DropdownMenu, Input, Label, Select, Slider, Tabs, Textarea, Tooltip, Separator, Sheet, Sidebar, etc.)
- **lucide-react** for icons (already in deps)
- **TypeScript** strict mode (already configured)

Add these new dependencies (add to `web/package.json`, then `npm install` from inside `web/`):

```json
{
  "motion": "^11.13.0",
  "gsap": "^3.12.5",
  "@gsap/react": "^2.1.1",
  "lenis": "^1.1.18",
  "react-intersection-observer": "^9.13.1",
  "clsx": "^2.1.1",
  "tailwind-merge": "^2.5.5"
}
```

Why each one:
- `motion` — modern Framer Motion successor for declarative React animations
- `gsap` + `@gsap/react` — scroll-triggered reveals, complex timelines, parallax
- `lenis` — buttery smooth scroll (replaces native scroll for marketing pages)
- `react-intersection-observer` — viewport detection without manual scroll math
- `clsx` + `tailwind-merge` — class composition; create `web/lib/cn.ts` if not already there

---

## Design System Tokens

Define these as Tailwind theme extensions in `web/app/globals.css` (use `@theme` directive for Tailwind v4):

### Color palette — **"After-Hours Indigo"**

A sophisticated dark-first palette with warm electric accents. Think: Vercel meets Linear meets a late-night hackathon.

```css
@theme {
  /* Brand */
  --color-bg: #0a0a0f;            /* near-black, slight cool tint */
  --color-bg-elevated: #13131a;   /* card surface */
  --color-bg-overlay: #1c1c24;    /* hover/active */
  --color-border: #27272f;        /* hairlines */
  --color-border-strong: #3a3a45; /* heavier dividers */

  /* Text */
  --color-text-primary: #fafafa;
  --color-text-secondary: #a1a1aa;
  --color-text-muted: #71717a;
  --color-text-inverse: #0a0a0a; /* for use on accent fills */

  /* Accents — indigo primary, amber energy */
  --color-accent: #8b5cf6;        /* violet-500 */
  --color-accent-hover: #a78bfa;  /* violet-400 */
  --color-accent-dim: rgba(139, 92, 246, 0.12); /* tinted backgrounds */
  --color-accent-2: #f59e0b;      /* amber-500, for CTAs and trophies */
  --color-accent-2-hover: #fbbf24;

  /* Semantic */
  --color-success: #10b981;
  --color-success-dim: rgba(16, 185, 129, 0.12);
  --color-warning: #f59e0b;
  --color-error: #ef4444;
  --color-error-dim: rgba(239, 68, 68, 0.12);
  --color-info: #3b82f6;

  /* Special — gradients */
  --gradient-hero: linear-gradient(135deg, #8b5cf6 0%, #6366f1 50%, #3b82f6 100%);
  --gradient-accent: linear-gradient(135deg, #8b5cf6 0%, #f59e0b 100%);
  --gradient-card: linear-gradient(180deg, rgba(139, 92, 246, 0.04) 0%, transparent 100%);

  /* Glow effects */
  --shadow-glow-accent: 0 0 40px rgba(139, 92, 246, 0.25);
  --shadow-glow-accent-2: 0 0 40px rgba(245, 158, 11, 0.2);
  --shadow-card: 0 1px 3px rgba(0, 0, 0, 0.4), 0 4px 12px rgba(0, 0, 0, 0.2);
  --shadow-elevated: 0 8px 24px rgba(0, 0, 0, 0.4), 0 16px 48px rgba(0, 0, 0, 0.3);
}
```

### Light mode override (add inside `@layer base` or `@media (prefers-color-scheme: light)`)

```css
@media (prefers-color-scheme: light) {
  :root {
    --color-bg: #fafafa;
    --color-bg-elevated: #ffffff;
    --color-bg-overlay: #f4f4f5;
    --color-border: #e4e4e7;
    --color-border-strong: #d4d4d8;
    --color-text-primary: #0a0a0a;
    --color-text-secondary: #52525b;
    --color-text-muted: #71717a;
    --color-text-inverse: #ffffff;
  }
}
```

**But the default aesthetic is dark** — most surfaces ship dark; the marketing/landing page can use a hero that transitions dark→light or stays dark with luminous accents.

### Typography

Already loaded in the project: **Geist** (sans + mono) + **Geist Mono**.

Use these weight/size tokens:

```css
@theme {
  --font-display: "Geist", system-ui, sans-serif;
  --font-body: "Geist", system-ui, sans-serif;
  --font-mono: "Geist Mono", ui-monospace, monospace;

  --text-display-2xl: 4.5rem;    /* hero h1 */
  --text-display-xl: 3.75rem;    /* page h1 */
  --text-display-lg: 3rem;       /* section h1 */
  --text-display-md: 2.25rem;    /* card h1 */
  --text-display-sm: 1.875rem;
  --text-display-xs: 1.5rem;

  --text-body-lg: 1.125rem;
  --text-body-md: 1rem;
  --text-body-sm: 0.875rem;
  --text-body-xs: 0.75rem;

  --leading-display: 1.05;
  --leading-tight: 1.25;
  --leading-body: 1.6;

  --tracking-display: -0.03em;  /* tight, for hero h1 */
  --tracking-tight: -0.015em;
  --tracking-body: 0;
  --tracking-caps: 0.08em;      /* for labels/eyebrows */
}
```

**Hero h1** must use `font-display tracking-display leading-display font-medium` — distinctive, not "Inter Bold 48px".
**Eyebrow labels** (above section titles) use `text-body-xs uppercase tracking-caps text-accent font-mono`.
**Numerics** (counts, scores, deadlines) use `font-mono tabular-nums`.

### Spacing & layout

- Container: `max-w-7xl mx-auto px-6 lg:px-10`
- Section padding: `py-24 lg:py-32` for marketing, `py-8` for dashboard
- Grid gaps: `gap-6` for cards, `gap-12` for sections
- Border radius: `rounded-xl` for cards, `rounded-2xl` for hero, `rounded-full` for pills/badges

### Animation system — three layers, use each in its place

1. **`motion` (declarative, per-component)**:
   - Hover microinteractions (`whileHover={{ y: -2 }}`)
   - Page enter animations (`initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}`)
   - Staggered list reveals (`staggerChildren: 0.05`)
   - Modal/dropdown enter/exit
   - Button press feedback
   - **Use for**: 90% of interactions

2. **`gsap` + ScrollTrigger (scroll-bound)**:
   - Parallax hero background
   - "Scroll-triggered reveal" of section content (fade up + slight scale)
   - Number count-up animations on stats
   - Horizontal scroll-pinned sections (none planned, but keep available)
   - **Use for**: marketing-page scroll choreography
   - Register in `useEffect` from `"use client"` components only

3. **`lenis` (smooth scroll wrapper)**:
   - Wrap marketing route group (`web/app/(marketing)/layout.tsx`)
   - NOT the dashboard route group (those need native scroll for sticky elements)
   - Initialize once at layout mount, destroy on unmount

**Animation principles:**
- Duration: 200-400ms for microinteractions, 600-900ms for page-level
- Easing: `cubic-bezier(0.16, 1, 0.3, 1)` for enter (out-expo-ish), `cubic-bezier(0.7, 0, 0.84, 0)` for exit
- Stagger children by 50-80ms max — never longer
- Respect `prefers-reduced-motion`: gate all animations behind `useReducedMotion()` from motion
- NEVER animate `width`/`height` — use `scale` or transform instead

---

## Route Inventory — what to design

The repo has three Next.js route groups. **Don't touch the route structure** — design within the existing layout per group.

### Route group 1: `(marketing)` — public landing + auth

**`web/app/(marketing)/layout.tsx`** — full-bleed dark marketing layout:
- **Top nav**: fixed, semi-transparent backdrop blur (`backdrop-blur-md bg-bg/80`), 64px tall. Logo (left, "Hack Hamster" wordmark + small paw glyph), center nav (Gallery, Certificates, Widget, How it works), right side (Log in button + theme toggle). On scroll past 50px, add `border-b border-border/50`.
- **Footer**: 4-column layout — Product (Gallery, Submit, Judge), Resources (Certificates, Widget, Docs), Company (About, Contact, Privacy), bottom bar (logo + © 2026 Hack Hamster Hackathon + GitHub link). Subtle top border. Background: `--color-bg-elevated`.
- **Lenis smooth scroll** initialized here.

**`web/app/(marketing)/page.tsx`** — landing page. Sections, in order:

1. **Hero** (full viewport height, full bleed):
   - Background: animated gradient mesh using 3 large blurred orbs (one violet, one indigo, one amber), GSAP-driven parallax on scroll. Add subtle SVG grid overlay at 4% opacity for texture.
   - Eyebrow: "HACK HAMSTER 2026 · HACKATHON JUDGING PLATFORM"
   - H1: "Ship the next big thing.\nGet it judged fairly." — display-2xl, with the second line in a gradient text fill (`bg-gradient-hero bg-clip-text text-transparent`).
   - Subhead: "A complete judging platform: submissions, multi-criteria scoring, community voting, audit-grade trails. Built for organizers who won't compromise."
   - Two CTAs side-by-side: primary "Browse gallery" (accent fill, arrow icon), secondary "Sign in" (ghost outline).
   - Below CTAs: tiny trust strip — "Trusted by 36 judges · 105 participants · Sep 25-28, 2026".
   - On the right or behind: an animated floating "rubric preview" card showing 3 criteria with sliders at varying positions (decorative — not interactive).

2. **Stats bar** (sticky-ish, immediately under hero):
   - 4 large numbers: `120+` submissions, `36` judges, `8` tracks, `2,400+` votes.
   - Use `font-mono tabular-nums` for the numbers.
   - Animate count-up on scroll-into-view with GSAP.
   - Horizontal divider line top + bottom.

3. **How it works** (3-column):
   - Three cards with numbered steps: 01 Submit, 02 Judge, 03 Vote/Results.
   - Each card: number (large mono, accent color), title, 2-line description, small illustration (use lucide icons styled with gradient backgrounds).
   - Stagger reveal on scroll.

4. **Features grid** (6 cards, 2x3 on desktop):
   - Multi-criteria scoring (sliders + comments)
   - Pairwise comparison (Bradley-Terry MM)
   - Community voting (simple or quadratic)
   - Audit-grade trails
   - Signatures + certificates
   - Widget embeds for third-party sites
   - Each card: icon in a tinted square, title, 2-line description, "Learn more →" link.
   - Hover: card lifts 4px, accent border on top edge slides in from left.

5. **Gallery preview** (carousel or 6-up grid):
   - "What shipped" — fetch 6 real submissions from `/api/gallery` (public, no auth).
   - Show project name, tagline, track badge, hover reveals submitted date.
   - Cards have a subtle accent-border shimmer on hover.
   - CTA: "Browse all submissions →" links to `/gallery`.

6. **How judging works** (deeper section):
   - Step-by-step with a mockup of the judge scoring UI on the right.
   - Mockup = styled div, not a screenshot. Floating card with sliders at varying values.

7. **CTA banner** (full bleed, gradient bg):
   - "Ready to ship?" with two CTAs.
   - Subtle moving grid pattern overlay.

8. **Footer**: as defined in layout.

**`web/app/(marketing)/login/page.tsx`**:
- Split layout: left = brand panel (gradient bg, big logo, "Welcome back" + tagline + decorative trophy/star illustration); right = form card.
- Card: max-w-md, `bg-bg-elevated border border-border rounded-2xl shadow-elevated`.
- Inputs: shadcn Input with `bg-bg-overlay border-border` style.
- Primary button: full width, accent fill.
- Below button: "Don't have an account? Register →".
- Error state: inline Alert with destructive variant, no toast.

**`web/app/(marketing)/register/page.tsx`**:
- Similar split layout. Password field with strength indicator (4 dots that fill based on length/complexity).
- Email field with mail icon prefix.
- Submit creates the user + auto-logs-in.

### Route group 2: `(dashboard)` — app

**`web/app/(dashboard)/layout.tsx`** — keep current structure but polish:
- Sidebar: keep current component but elevate the visual treatment — backdrop-blur, subtle border-right, hover states on nav items with accent-color left bar that slides in.
- Top bar: page title (h1) on left, theme toggle on right, no breadcrumbs (the sidebar nav is the orientation).
- Main content: `max-w-6xl mx-auto p-6 lg:p-10`.

**`web/app/(dashboard)/page.tsx` (the dashboard home, if it exists — currently goes to organizer?)** — check structure; if there's no index page, skip.

**`web/app/(dashboard)/gallery/page.tsx`** (or wherever the dashboard-side gallery lives — check the actual structure):
- Header: page title "Gallery" + subtitle.
- Filter bar: track filter (dropdown), sort (Alpha/Newest).
- Grid: 3 cols on desktop, 2 on tablet, 1 on mobile.
- Each card: track badge (top-right), name (display-md), tagline (text-secondary), "View →" hover action.
- Hover: lift 4px, accent border-top shimmer, image/placeholder fade in.
- Pagination: cursor-based (already implemented) — show "Load more" button at bottom with a loading state.

**`web/app/(dashboard)/submit/page.tsx`**:
- If not participant: clean "Participants only" gate card with icon, "Switch accounts" copy.
- If participant: a single elegant form, NOT multi-step. Two-column on desktop (project details left, track + links right). Save Draft + Submit buttons.

**`web/app/(dashboard)/vote/page.tsx`**:
- Header: page title + how-voting-works tooltip (question icon → popover).
- Grid of project cards, each with a Vote button.
- Clicking Vote: optimistic state change (button morphs to "Voted ✓" with accent fill), then real API call.

**`web/app/(dashboard)/judge/page.tsx`**:
- Header: "Your batch" + progress ring (large circular progress showing X/Y scored).
- Project list: each row = project name + tagline + status pill (Pending / Reviewed with timestamp).
- "Continue judging" CTA on each pending row.

**`web/app/(dashboard)/judge/[projectId]/page.tsx`** + **`ScoreForm.tsx`**:
- Two-column on desktop: left = project details (name, tagline, description, links), right = scoring card.
- Each criterion: card with criterion name, description, weight badge (mono), slider with min/max labels, live value display (mono), comment textarea below.
- "Save draft" + "Submit review" buttons. Submitted state: replaced with success card + "Edit review" button.
- Use motion for slider value display (subtle scale on change).

**`web/app/(dashboard)/organizer/page.tsx`**:
- Top stats grid: 4 cards (judges, organizers, participants, submissions count).
- Membership table with proper spacing, role badges, search/filter.
- Actions panel: 3 cards (Bulk invite, Run assignment, Run normalization) with description + button + loading states.
- **Loading states matter here**: each action button shows a spinner inside the button while in flight, and on success shows a toast + reveals result inline (no separate results page jump).

**`web/app/(dashboard)/organizer/results/page.tsx`**:
- Two sections: Voting results (table) + Audit log (table with timestamp, actor, action, target, result).
- Tables: zebra striping, sticky headers, monospace timestamps + IDs.
- Audit log entries: result badge (success = green, denied = red, error = red bold).

**`web/app/(dashboard)/pairwise/page.tsx`**:
- Two large cards side-by-side with "Tie" between them.
- Project card: name + tagline + accent hover effect on hover (when user hovers one, it scales up slightly).
- Keyboard shortcuts banner: "← left wins · → right wins · T tie".
- Counter: "X compared this session".

**`web/app/(dashboard)/pairwise/ranking/page.tsx`**:
- Table: rank, project name, W/L/T, θ (theta, monospace), with a sparkline or bar visualization for θ.
- Top 3 have a small trophy/star icon.
- Export CSV button.

### Route group 3: `(public)` — public-facing

**`web/app/(public)/layout.tsx`** — minimal nav (logo + Log in button on right).

**`web/app/(public)/gallery/page.tsx`** + **`[id]/page.tsx`**:
- Public gallery: same component style as dashboard gallery but read-only.
- Detail page: hero with project name + track badge, two-column (description left, links + meta right).

**`web/app/(public)/certificates/[publicId]/page.tsx`**:
- Verify form: large centered card with input + verify button.
- Result: badge with "Signature valid" or "tampered" / "not found" with appropriate icons.

**`web/app/(public)/widget/page.tsx`**:
- Two-column: left = live preview of the embed widget, right = embed code (copyable).
- Widget preview: shows a mini gallery from `/api/widget/gallery`.

### Loading, empty, error states

For every list view (gallery, batch, audit log, voting results), define:

- **Loading**: skeleton screens (NOT spinners). Pulse animation, `bg-bg-overlay` rectangles sized to match the real content layout.
- **Empty**: centered illustration (lucide icon in tinted square) + title + 1-line description + optional CTA.
- **Error**: Alert variant="destructive" with retry button. No raw stack traces shown to user.

---

## Microinteractions & Polish

These are the small details that distinguish a professional app from a template:

- **Buttons**: hover scales 1.02 + accent shadow, active scales 0.98, focus ring is accent color, disabled has 50% opacity + cursor-not-allowed.
- **Cards**: hover lifts -2px, top accent border slides in from left (200ms), shadow deepens.
- **Links**: underline slides in from left on hover (don't show always).
- **Inputs**: focus border becomes accent, focus ring is accent at 30% opacity, label slides up.
- **Nav items**: active state has accent left bar + bg-accent-dim.
- **Tables**: row hover = `bg-bg-overlay`, alternating rows `bg-bg` / `bg-bg-elevated`.
- **Number changes**: count-up animation 600ms ease-out.
- **Page transitions**: fade + slight slide-up (motion AnimatePresence).

---

## Accessibility

- All interactive elements keyboard-accessible (visible focus rings).
- Color contrast: text on `--color-bg` is `--color-text-primary` (#fafafa on #0a0a0f = 19.5:1, AAA).
- ARIA labels on icon-only buttons.
- `prefers-reduced-motion` respected everywhere (gate animations).
- Form inputs always have `<Label>` association.

---

## Commit & Push Workflow

At the END, do exactly this:

```bash
# Sanity check — verify no files outside web/ were touched
cd /path/to/hack-hamster-hackathon
git status --short
# Should ONLY show web/ files. If apps/, config/, tests/, etc. show up, revert them.

# Commit on mihir branch (must already be on it)
git add web/
git commit -m "<descriptive summary>

<2-3 line detail of major changes>

- Theme tokens in web/app/globals.css (After-Hours Indigo palette)
- Reusable motion + scroll + class utilities
- All route groups redesigned end-to-end
- Loading/empty/error states everywhere"

# Push to mihir's branch
git push origin mihir
```

**Do NOT force-push. Do NOT push to main. Do NOT push to manas. ONLY `git push origin mihir`.**

If the build fails after your changes (`npm run build` in `web/`), fix it before committing. The user will be testing in the browser afterward.

---

## Verification Before You Push

Run these in order before committing:

```bash
cd web
npm run build 2>&1 | tail -30    # must exit 0
npx tsc --noEmit 2>&1 | tail -10  # must exit 0 (or only show pre-existing warnings)
```

If build fails: fix. If type errors are introduced: fix. Don't push broken code.

---

## Final notes

- **Be opinionated**. Don't ask "should I use X or Y" — the design system above already decided.
- **Be thorough**. Every page gets the full treatment: hero, empty, loading, error states. No "TODO" comments.
- **Be consistent**. Reuse the same patterns. If a Button is rounded-full with accent bg on the landing page, the same Button is rounded-full with accent bg in the dashboard.
- **Don't import from `frontend/`** — that folder is untracked on the manas branch only. The web/ folder is what you're designing.
- **Real data**: use the seeded test data from the live backend. Don't make up fake project names. The gallery API at `/api/gallery` returns 24 real submissions.
- **Theme toggle**: ship dark + light, default dark. Use `next-themes` if not already installed; otherwise hand-roll a theme provider with localStorage + class on `<html>`.

**Ship it.**
