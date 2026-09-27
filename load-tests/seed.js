// load-tests/seed.js
//
// Helper that pre-creates a test user via POST /api/register. Useful
// when you want to add a fresh participant to the demo event without
// running the full Django seed_fixtures management command — e.g. for
// ad-hoc rate-limit probing or for exercising the auth/login path
// end-to-end against the live portal.
//
// Usage:
//   k6 run load-tests/seed.js
//   k6 run load-tests/seed.js --env EMAIL=alice@example.com
//
// What it does:
//   1. Picks an email (EMAIL env var, or one derived from the current
//      Unix timestamp so consecutive runs don't collide on the demo).
//   2. Sends POST /api/register with {email, name, password}.
//   3. Captures the session cookie from the response and reports it.
//   4. Logs `seeded: <email>` on success.
//
// Known limitation (platform bug, not a seed.js issue):
// The shipped UserSerializer does NOT include the inherited
// `username` field. AbstractUser's `username` is NOT NULL + UNIQUE.
// When /api/register is called with only email/name/password, Django
// writes an empty-string username. The first call against a fresh DB
// succeeds; the SECOND call with a different email would fail with
// a 500 IntegrityError on the empty-string duplicate. This is a real
// platform bug — we surface it as a clear failure in the report
// rather than working around it in seed.js.
//
// To run seed.js more than once against the same DB, delete the row
// first (or use a different email AND pre-clear the empty-username
// row via `psql -c "DELETE FROM users_user WHERE username = ''"`).

import http from 'k6/http';
import { check } from 'k6';
import { fail } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

// `EMAIL` overrides the default; default is timestamp-based so
// concurrent invocations don't collide on the unique-email constraint.
const EMAIL =
  __ENV.EMAIL ||
  `seed-${Date.now()}-${Math.floor(Math.random() * 1e6)}@k6.local`;
const NAME = __ENV.NAME || `k6 seeded ${EMAIL.split('@')[0]}`;
const PASSWORD = __ENV.PASSWORD || 'k6-strongpass-2026';

export const options = {
  // Single iteration — this is a one-shot helper, not a load profile.
  vus: 1,
  iterations: 1,
};

export default function () {
  const payload = JSON.stringify({
    email: EMAIL,
    name: NAME,
    password: PASSWORD,
  });
  const res = http.post(`${BASE_URL}/api/register`, payload, {
    headers: { 'Content-Type': 'application/json' },
  });

  const ok = check(res, {
    'register returns 201': (r) => r.status === 201,
  });

  if (!ok) {
    // Pull whatever the server said — it's almost always the empty-
    // username IntegrityError on second runs.
    let body = '';
    try {
      body = typeof res.body === 'string' ? res.body.slice(0, 400) : '';
    } catch (_) {
      // ignore
    }
    fail(
      `seed.js: register failed for ${EMAIL} (status=${res.status}). ` +
        'If status is 500 and the error mentions "users_user_username_key" ' +
        'or "duplicate key value violates unique constraint ... ' +
        'username_key", see the limitation note in the file header. ' +
        `Body: ${body}`
    );
  }

  const sessionCookie =
    res.cookies && res.cookies.session && res.cookies.session.length > 0
      ? res.cookies.session[0].value
      : null;
  if (!sessionCookie) {
    fail(
      `seed.js: register succeeded but no session cookie was returned. ` +
        'Did the server drop the Set-Cookie header?'
    );
  }

  // k6 prints stdout lines verbatim under the "INFO" prefix; we use
  // console.log so it shows up clearly in the run summary.
  console.log(`seeded: email=${EMAIL} session=${sessionCookie}`);
}
