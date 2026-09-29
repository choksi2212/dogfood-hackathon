# Test suite — OpenAPI conformance

> **`openapi.yaml` at repo root + `/api/schema/` accurately describe the live endpoints.** Tests live in `tests/conformance/test_openapi.py` under `@pytest.mark.conformance`. The API First bonus artefact.

## Contents

- [URLconf vs openapi.yaml — diff detector at a glance](#urlconf-vs-openapiyaml--diff-detector-at-a-glance)
- [What it covers](#what-it-covers)
- [Known drift](#known-drift)
- [Run](#run)

## URLconf vs openapi.yaml — diff detector at a glance

```mermaid
flowchart TB
    subgraph SRC["📜 Sources"]
        direction TB
        YAML["📄 openapi.yaml<br/>(repo root)"]
        URL["🐍 config/urls.py<br/>urlpatterns"]
        VIEW["🐍 apps/*/views.py<br/>APIView subclasses"]
        SCHEMA["⚖️ /api/schema/<br/>runtime JSON dump"]
    end

    subgraph PARSE["🧪 Parser"]
        direction TB
        P1["⚖️ yaml.safe_load(openapi.yaml)"]
        P2["⚖️ urlpatterns → set of paths"]
        P3["⚖️ JSON.loads schema endpoint"]
    end

    subgraph DIFF["🔍 Diff detector"]
        direction TB
        D1["🧪 paths_in_yaml ⊆ live_routes?"]
        D2["🧪 live_routes ⊆ paths_in_yaml?"]
        D3["🧪 methods per path match?"]
        D4["🧪 every $ref resolves?"]
        D5["🧪 yaml == json.dumps schema endpoint?"]
    end

    subgraph OUT["📤 Result"]
        direction TB
        OK["✅ all 10 checks pass"]
        FAIL["🔴 which side is wrong?<br/>(URLconf or spec)"]
    end

    YAML --> P1
    URL --> P2
    VIEW --> SCHEMA --> P3
    P1 --> D1
    P2 --> D1
    P2 --> D2
    P1 --> D2
    P1 --> D3
    P3 --> D3
    P1 --> D4
    P1 --> D5
    P3 --> D5

    D1 --> OK
    D2 --> OK
    D3 --> OK
    D4 --> OK
    D5 --> OK
    D1 -.->|mismatch| FAIL
    D2 -.->|mismatch| FAIL
    D3 -.->|mismatch| FAIL
    D4 -.->|broken $ref| FAIL
    D5 -.->|whitespace diff| FAIL

    style SRC fill:#FDF6E3,stroke:#E9C46A,color:#1D3557
    style PARSE fill:#FFE8D6,stroke:#F4A261,color:#1D3557
    style DIFF fill:#EDE7F6,stroke:#6C567B,color:#1D3557
    style OK fill:#A8DADC,stroke:#2A9D8F,color:#1D3557
    style FAIL fill:#F1FAEE,stroke:#E63946,color:#1D3557
```

## What it covers

`openapi.yaml` at repo root + `/api/schema/` accurately describe the live endpoints. The API First bonus artefact.

| Test | Asserts |
|---|---|
| /api/schema/ valid OpenAPI 3 | Has `openapi: 3.0.3`, `info.title`, `info.version`, `paths` |
| openapi.yaml matches /api/schema/ | JSON served by view equals YAML loaded + dumped |
| All paths in spec exist | For each path in `spec['paths']`, GET → 200 or 401/403/404 |
| No undocumented paths | For each path in urlpatterns, must be in `spec['paths']` |
| Spec endpoints have correct methods | GET /api/gallery, POST /api/events/<slug>/submit, etc. |
| Security scheme referenced | `cookie` referenced where required |
| Schemas referenced | Submission, Certificate, Error used by at least one response |
| No broken $ref | Each `$ref` resolves to a defined schema |

## Known drift

- `test_yaml_matches_schema_endpoint`: JSON formatting (key order, whitespace) differs from YAML — compare structurally, not by string.
- `test_all_spec_paths_exist_on_running_service`: 401 with no auth is acceptable. Some spec paths may not be implemented yet (e.g., T3/T4 endpoints).
- `test_no_undocumented_paths_in_urlconf`: All Django urlpatterns must appear in spec. Run before each release.

## Run

```bash
make test-conformance
```

---

[← Back to TESTING.md](TESTING.md)
