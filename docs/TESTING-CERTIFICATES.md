# Test suite — certificates

`tests/certificates/test_certificates.py` — `@pytest.mark.certificates`

## What it covers

HMAC-SHA256-signed per-submission certificates. Sign, verify, tamper
detection, canonical-JSON stability, view-level roundtrip.

| Test | Asserts |
|---|---|
| Sign + verify | Signed certificate verifies with correct key |
| Wrong key | Different SECRET_KEY fails verification |
| Tampered payload | Mutate one byte of signed_payload → verify() returns False |
| Canonical-JSON stability | Two equivalent dicts (different key order / whitespace) → identical signatures |
| public_id uniqueness | Two issue() calls on different submissions → different public_ids |
| Issue → fetch via view | GET /api/certificates/<public_id> → 200 with signed payload + signature |
| Issue → fetch with tampered public_id | 404 |
| Tampered fetch | GET real cert, mutate DB payload, GET again → 400 `signature_invalid` |
| Public access | Anonymous GET allowed |
| Re-issuing | Two issue() calls on same submission → two distinct Certificate rows |
| Payload schema | submission_id, team_name, event_slug at minimum |
| Signature length | Constant (hex sha256 = 64 chars) |
| Real hmac module matches | Independent computation of HMAC matches our sign_payload |

## HMAC scheme

```
key      = settings.SECRET_KEY (UTF-8)
payload  = canonical-JSON(payload) — sort_keys, no whitespace
sig      = hmac.new(key, payload, hashlib.sha256).hexdigest()
verify   = constant-time hmac.compare_digest(sig, sign_payload(payload))
```

## Known drift

- `apps/certificates/urls.py` mounts `/api/certificates/<public_id>` via
  `path("<str:public_id>", ...)` inside `include()`. The intent
  per the spec is `/api/certificates/<public_id>`. The view tests
  run against the actual URL the server responds to.
- For `test_view_does_not_accept_post`: `@require_GET` is used. POST
  should be 405. The current view returns 405 only if the URL routes
  correctly; verify in browser before changing.

## Run

```bash
make test-certificates
```
