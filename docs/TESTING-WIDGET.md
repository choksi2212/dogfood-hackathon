# Test suite — widget

`tests/widget/test_widget.py` — `@pytest.mark.widget`

## What it covers

Embeddable widget: `/widget.js` (JS shim) and `/api/widget/gallery`
(JSON feed). CORS, content-type, JSON shape, public access.

| Test | Asserts |
|---|---|
| /widget.js returns JS | 200, application/javascript, contains `HACK HAMSTER_WIDGET` |
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

- `test_widget_gallery_bogus_event_returns_empty_not_404`: Our view
  returns `{items: []}` without the `event` key for unknown events.
  The tests should assert `{items: []}` only.

## Run

```bash
make test-widget
```
