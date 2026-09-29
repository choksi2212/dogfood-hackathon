# Test suite — CSV

> **Streaming CSV export from `apps.judging.views.CSVExportView`.** Tests live in `tests/csv/test_csv_export.py` under `@pytest.mark.csv`. Comma-separated, RFC 4180 quoting, unicode-preserving, organizer-only.

## Contents

- [Stream at a glance](#stream-at-a-glance)
- [What it covers](#what-it-covers)
- [Known drift](#known-drift)
- [Run](#run)

## Stream at a glance

```mermaid
flowchart LR
    subgraph REQ["Request"]
        direction TB
        ORG["Organizer<br/>GET /api/csv_export?event_slug/other-slug"]
        ANON["Anonymous"]
        JUDGE["Judge"]
    end

    subgraph GATE["Permission gate"]
        direction TB
        AUTH["IsAuthenticated"]
        ORG2["IsOrganizer"]
    end

    subgraph STREAM["Streaming export"]
        direction TB
        Q["NormalizedScore<br/>select_related all<br/>order_by score"]
        HDR["Header row<br/>event_slug, project_id,<br/>project_name, judge_email,<br/>criterion_name, score, weight"]
        ROW["N by M by K data rows<br/>RFC 4180 quoting"]
        UTF["UTF-8 preserved<br/>(arrow, emoji, CJK)"]
        RESP["StreamingHttpResponse<br/>Content-Type text/csv<br/>Content-Disposition attachment"]
    end

    ORG --> AUTH --> ORG2 --> Q
    Q --> HDR --> ROW --> UTF --> RESP
    ANON --> AUTH
    AUTH -->|no| R401["401"]
    JUDGE --> AUTH
    AUTH -->|yes| ORG2
    ORG2 -->|no| R403["403"]

    style REQ fill:#FDF6E3,stroke:#E9C46A,color:#1D3557
    style GATE fill:#FFE8D6,stroke:#F4A261,color:#1D3557
    style STREAM fill:#A8DADC,stroke:#2A9D8F,color:#1D3557
    style R401 fill:#F1FAEE,stroke:#E63946,color:#1D3557
    style R403 fill:#F1FAEE,stroke:#E63946,color:#1D3557
```

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

- `test_unicode_arrow_in_project_name`: csv writer may quote `→` differently; pass `utf-8` explicitly if needed.
- `test_non_organizer_gets_403`: View returns 422 (validation, missing `?event_slug` for non-organizers) before the organizer check. Reorder: organizer first, then event resolution.

## Run

```bash
make test-csv
```

---

[← Back to TESTING.md](TESTING.md)
