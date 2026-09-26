# Test suite — CSV

`tests/csv/test_csv_export.py` — `@pytest.mark.csv`

## What it covers

Streaming CSV export from `apps.judging.views.CSVExportView`.

| Test | Asserts |
|---|---|
| Shape | Header + N×M×K data rows |
| Header columns | event_slug, project_id, project_name, judge_email, criterion_name, score, weight |
| CSV dialect | Comma-separated, RFC 4180 quoting |
| Special characters | Commas/quotes/newlines in names → properly quoted |
| Unicode (→, emoji) | UTF-8 preserved |
| Empty event | Header row only |
| Streaming | StreamingHttpResponse, Content-Type: text/csv |
| Content-Disposition | `attachment; filename="scores-<slug>.csv"` |
| Organizer-only | Non-organizer → 403 |
| Anonymous | 401 |
| Multi-event | `?event_slug=<other>` returns that event |
| Weight column | Reflects criterion.weight |
| ?event_slug missing | Defaults to organizer's only event |

## Known drift

- `test_unicode_arrow_in_project_name`: The csv module's writer
  default may quote the `→` differently. Use `utf-8` encoding
  explicitly in writer if needed.
- `test_non_organizer_gets_403`: Our view returns 422 (validation
  error from missing `?event_slug` for non-organizers) before the
  organizer check. Reorder: organizer first, then event resolution.

## Run

```bash
make test-csv
```
