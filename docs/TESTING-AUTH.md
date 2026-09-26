# Test suite — auth

`tests/auth/test_auth.py` — `@pytest.mark.auth`

## What it covers

Session lifecycle + cookie behaviour + register/login/logout.

| Test | Asserts |
|---|---|
| Session lookup | Valid cookie → request.user resolves, is_authenticated=True |
| No cookie | request.user is AnonymousUser, is_authenticated=False |
| Tampered cookie | Random string as cookie → no session found, AnonymousUser |
| Expired session | Session with `expires_at` in the past → purged, subsequent request is anonymous |
| Sliding renewal | Valid session extends `expires_at` by 14 days on each request |
| Register | POST `/api/auth/register` with email+password → 201, session cookie set |
| Login | POST `/api/auth/login` with valid creds → session cookie; wrong password → 401 |
| Logout | POST `/api/auth/logout` (authed) → clears cookie, subsequent request is anonymous |
| Cookie HttpOnly | Login response sets HttpOnly on the cookie |
| Cookie SameSite | Login response sets SameSite=Lax |
| Cookie Secure (DEBUG=False) | When DEBUG is false, the cookie has `Secure` |
| Cookie Secure (DEBUG=True) | When DEBUG is true, the cookie does NOT have `Secure` |

## Known drift

- `test_login_cookie_is_not_secure_when_debug_true`: Our settings default DEBUG=false. The cookie is always Secure unless the test environment explicitly sets DEBUG=true. Either the test should set DEBUG, or our default DEBUG in tests should be true. Decision pending.

## Run

```bash
make test-auth
```

## Run individually

```bash
docker compose exec web pytest tests/auth/ -v
```
