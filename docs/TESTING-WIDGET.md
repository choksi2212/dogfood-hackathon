# Test suite — widget

> **Embeddable widget: `/widget.js` (JS shim) and `/api/widget/gallery` (JSON feed).** Tests live in `tests/widget/test_widget.py` under `@pytest.mark.widget`. CORS, content-type, JSON shape, public access.

## Contents

- [Embed at a glance](#embed-at-a-glance)
- [What it covers](#what-it-covers)
- [Known drift](#known-drift)
- [Run](#run)

## Embed at a glance

```mermaid
sequenceDiagram
    autonumber
    participant T as 🌐 Third-party site<br/>(example.com)
    participant J as widget_js
    participant H as ⚖️ Hack-Hamster portal<br/>/api/widget/gallery
    participant DB as 🗄️ Postgres

    T->>J: GET https://hack-hamster/widget.js
    J-->>T: 200 application/javascript<br/>Access-Control-Allow-Origin: *

    Note over T: 🔧 <script> initialises:<br/>HH_WIDGET.init({event: "..."})

    T->>H: GET /api/widget/gallery?event=...
    H->>H: ⚖️ IsAuthenticated: AllowAny
    H->>DB: ⚖️ Event.objects.filter(slug=...).first()
    alt event unknown
        DB-->>H: None
        H-->>T: 200 {"items": [], "event": "..."}
    else event exists
        DB-->>H: Event
        H->>DB: ⚖️ Submission.objects.filter(<br/>status='submitted',<br/>track__event=event).order_by(...)[:24]
        DB-->>H: rows (max 24)
        H->>H: ⚖️ WidgetSerializer<br/>(id, name, tagline, track_slug)
        H-->>T: 200 {items: [...], event: "..."}<br/>Access-Control-Allow-Origin: *
    end

    Note over T: 🔧 DOM render:<br/>append <ul> with item HTML
```

## What it covers

Embeddable widget: `/widget.js` (JS shim) and `/api/widget/gallery` (JSON feed). CORS, content-type, JSON shape, public access.

| Test | Asserts |
|---|---|
| /widget.js returns JS | 200, application/javascript, contains `HH_WIDGET` |
| /widget.js valid JS (issue #13) | Body is a parseable IIFE (`node --check` when node available), `HACK HAMSTER_WIDGET` token absent |
| next.config.ts widget rewrite (issue #13) | `/widget.js` proxied to Django on the Next.js public surface |
| /widget.js CORS | `Access-Control-Allow-Origin: *` |
| /widget.js no auth required | Anonymous GET → 200 |
| /api/widget/gallery returns JSON | 200, application/json |
| /api/widget/gallery CORS | `Access-Control-Allow-Origin: *` |
| /api/widget/gallery JSON shape | `{items: [{id, name, tagline, track_slug}, ...], event}` |
| /api/widget/gallery empty event | `{items: [], event}` |
| /api/widget/gallery bogus event | 200 with empty items (no 404) |
| /api/widget/gallery only submitted | Drafts and withdrawn excluded |
| /api/widget/gallery 24-item cap | 30 projects → 24 items |
| /api/widget/gallery trailing slash | Both `/api/widget/gallery` and `/api/widget/gallery/` work |

## Known drift

- `test_widget_gallery_bogus_event_returns_empty_not_404`: View returns `{items: []}` without the `event` key for unknown events. Tests should assert `{items: []}` only.

## Run

```bash
make test-widget
```

---

[← Back to TESTING.md](TESTING.md)
