# Hack Hamster logo assets

An original geometric hamster identity with the lowercase wordmark **hack hamster**. The red first word and neutral second word use outlined Geist Sans Medium, weight 500, with −0.02em tracking and a 0.25em word space. All SVGs render without installed fonts. This package supplies assets only; it does not integrate them into the application.

## Ten variants

Every numbered variant has separate SVG and PNG files. The dimensions below are PNG export sizes; most SVGs scale through their viewBox.

| # | File stem | PNG dimensions | Use |
| --- | --- | --- | --- |
| 1 | `01-horizontal-dark` | 4096 × 1024 | Neutral mascot, red `hack`, offwhite `hamster`, on charcoal. |
| 2 | `02-horizontal-light` | 4096 × 1024 | Neutral mascot, red `hack`, charcoal `hamster`, on offwhite. |
| 3 | `03-stacked-dark` | 2048 × 2048 | Centered stacked lockup on charcoal. |
| 4 | `04-mark-dark` | 2048 × 2048 | Transparent red mascot for dark surfaces. |
| 5 | `05-mark-light` | 2048 × 2048 | Transparent red mascot for light surfaces. |
| 6 | `06-wordmark-dark` | 4096 × 1024 | Split-color wordmark alone, on charcoal. |
| 7 | `07-wordmark-light` | 4096 × 1024 | Split-color wordmark alone, on offwhite. |
| 8 | `08-monochrome-ink` | 4096 × 1024 | Transparent, single-color charcoal horizontal lockup. |
| 9 | `09-monochrome-reversed` | 4096 × 1024 | Transparent, single-color white horizontal lockup. |
| 10 | `10-favicon-16`, `10-favicon-32` | 16 × 16; 32 × 32 | Transparent red favicons at native sizes. |

Variants 4, 5, 8, and 9 have separate `-preview` files with backgrounds for contrast review. Use their transparent source files when placing artwork into a design. Variants 4 and 5 intentionally share the same red outline; their previews demonstrate the two surface contexts. `logo` is a transparent dark-context horizontal lockup; `logo-icon` is the transparent red mascot.

## Palette and spacing

Use these exact flat colors:

| Color | Value | Role |
| --- | --- | --- |
| Red | `#E2454A` | `hack`, red mascot exports, app-icon background. |
| Offwhite | `#F5F5F5` | Light surface and primary reversed artwork. |
| Gray | `#DADADA` | Supporting neutral. |
| Charcoal | `#303030` | Dark surface and primary light-context artwork. |
| White | `#FFFFFF` | Monochrome reversed artwork and app-icon mascot. |

Maintain at least one wordmark x-height of clear space around general-purpose lockups. Measured x-height is 0.532em. Preserve the word space, proportions, and cutouts when scaling; use uniform scaling.

The canonical horizontal symbol canvas is 2.4 × wordmark x-height high. The stacked symbol canvas is 0.62 × wordmark width. The compact widget and fixed-size certificate are purpose-specific exceptions.

## Mascot construction and reference

The mascot uses a 24 × 24 viewBox, rounded short ears, broad cheeks, two rounded eye cutouts, a triangular nose, and paired incisor cutouts. Its visible bounds are x=1–23 and y=2–23. Facial details are transparent holes in an even-odd compound path, so they adopt the placement surface rather than an imposed fill.

The [XHamster logo reference on Wikimedia Commons](https://commons.wikimedia.org/wiki/File:XHamster_logo.svg) informed the front-facing hamster, visible incisors, and red-prefix/neutral-wordmark treatment. The supplied mascot is an original geometric construction with its own outlines and typography.

## Production exports

- **Favicons:** use `10-favicon-16` and `10-favicon-32` at their native sizes. `favicon-reversed-16` and `favicon-reversed-32` supply white equivalents. `favicon.ico` packages the separate 16px and 32px masters.
- **App icon:** `app-icon`, 1024 × 1024, with a white mascot on a rounded red square. The outer corners remain transparent.
- **Widget:** `widget-header-dark` and `widget-header-light`, 152 × 24, use a 24px symbol canvas and Geist Medium at 14px. `widget-header-dark-4x`, 608 × 96, is intended for display at 152 × 24.
- **Certificate:** `certificate-header.svg` has intrinsic dimensions **280pt × 230pt** and viewBox `0 0 280 230`. Preserve that placement size for a **40mm visible mascot width** and **24pt wordmark**. The padded symbol canvas is approximately 43.636mm wide. The 2800 × 2300 PNG carries 720dpi metadata for the same physical size; prefer SVG for print.
- **Social card:** `github-social-card`, 1280 × 640, includes the charcoal background.
- **Proof sheets:** `hack-hamster-family`, 1920 × 2800, and `production-formats`, 1920 × 1600, collect the family and production examples for review.

Review the favicon eyes and teeth at native 16px/32px, inspect transparent edges on charcoal and offwhite, and check certificate placement at its intrinsic print dimensions. `manifest.json` records colors, construction, proportions, and export sizes.

## Typeface license

Geist uses the [SIL Open Font License 1.1](https://raw.githubusercontent.com/vercel/geist-font/main/OFL.txt). No font binaries are bundled here; the wordmarks are outlined paths. Obtain the original font with its license if rebuilding or distributing font files.
