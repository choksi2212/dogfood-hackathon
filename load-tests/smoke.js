// load-tests/smoke.js
//
// Smoke test for the DOGFOOD hackathon portal. Three public endpoints
// at low load (10 VUs for 30s). Catches catastrophic regressions
// (5xx, deploy broken, DB unreachable) without warming the event
// deadline gate.
//
// Endpoints exercised:
//   GET /healthz
//   GET /api/gallery?event=<slug>
//   GET /api/widget/gallery?event=<slug>
//
// Usage:
//   k6 run load-tests/smoke.js
//
// Thresholds:
//   http_req_failed    rate < 1%   (a smoke failure is a hard regression)
//   http_req_duration  p95  < 500ms (sane on a healthy stack)
//
// ─────────────────────────────────────────────────────────────────────
// Rate limit caveat: the platform's RateLimitMiddleware caps reads at
// 60/min/IP. k6 shares one host IP, so naive runs trip the limiter.
// Each script in this directory spoofs `X-Forwarded-For` per VU×ITER
// to spread load across synthetic 10.x.x.x IPs. Set `K6_NO_IP_SPOOF=1`
// to disable; in that case run with the rate limiter disabled.
// ─────────────────────────────────────────────────────────────────────

import http from 'k6/http';
import { check } from 'k6';
import { open } from 'k6/fs';

import { resolveToml } from './lib/toml.js';
import { withSyntheticIp } from './lib/ip.js';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const EVENT_SLUG = __ENV.EVENT_SLUG || 'sample-hack-2026';

export const options = {
  vus: 10,
  duration: '30s',
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<500'],
  },
};

export default function () {
  const headers = withSyntheticIp({}, __VU, __ITER);

  // /healthz must return 200 — it is the canary the acceptance suite
  // runs before any tier checks. Body should report db ok.
  const healthRes = http.get(`${BASE_URL}/healthz`, { headers });
  check(healthRes, {
    'healthz returns 200': (r) => r.status === 200,
    'healthz reports db ok': (r) => {
      try {
        const body = JSON.parse(r.body);
        return body.status === 'ok';
      } catch (_) {
        return false;
      }
    },
  });

  // /api/gallery is the spec T1 check 1. Public, paginated. The
  // `?event=` query is accepted by the test (matches the URL the
  // acceptance suite constructs) even though the view doesn't read it
  // — keeps parity with widget/gallery and the spec route table.
  const galleryRes = http.get(
    `${BASE_URL}/api/gallery?event=${EVENT_SLUG}`,
    { headers }
  );
  check(galleryRes, {
    'gallery returns 200': (r) => r.status === 200,
    'gallery body has items array': (r) => {
      try {
        const body = JSON.parse(r.body);
        return Array.isArray(body.items);
      } catch (_) {
        return false;
      }
    },
  });

  // /api/widget/gallery is the embeddable widget JSON feed. Same
  // shape but a different code path (decorator-free, no DRF view).
  const widgetRes = http.get(
    `${BASE_URL}/api/widget/gallery?event=${EVENT_SLUG}`,
    { headers }
  );
  check(widgetRes, {
    'widget gallery returns 200': (r) => r.status === 200,
    'widget gallery body has items array': (r) => {
      try {
        const body = JSON.parse(r.body);
        return Array.isArray(body.items);
      } catch (_) {
        return false;
      }
    },
  });
}

// Read .dogfood.toml at init. We don't actually need the cookies for
// the smoke test (all three endpoints are public), but resolving the
// file up-front proves the helper works against the real file and
// fails fast with a useful error if the layout is wrong.
export function setup() {
  return resolveToml(open);
}
