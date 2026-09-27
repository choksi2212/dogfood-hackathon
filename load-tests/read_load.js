// load-tests/read_load.js
//
// Read-heavy load test for the DOGFOOD hackathon portal. Three GETs
// hammered at 50 VUs with a 30s ramp and a 1m hold — close to 10x the
// expected demo traffic so regressions in cache headers, query plans,
// or auth lookup costs show up as latency, not as 5xx.
//
// Endpoints exercised:
//   GET /api/gallery
//   GET /api/widget/gallery?event=<slug>
//   GET /api/judge/scores              (judge_a session cookie)
//
// Usage:
//   k6 run load-tests/read_load.js
//
// Thresholds:
//   http_req_failed    rate < 5%
//   http_req_duration  p95  < 800ms
//
// ─────────────────────────────────────────────────────────────────────
// Rate limit caveat: see smoke.js — `X-Forwarded-For` is spoofed per
// VU×ITER by default. `K6_NO_IP_SPOOF=1` disables it.
// ─────────────────────────────────────────────────────────────────────

import http from 'k6/http';
import { check } from 'k6';
import { open } from 'k6/fs';

import { resolveToml, extractSessionCookie } from './lib/toml.js';
import { withSyntheticIp } from './lib/ip.js';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const EVENT_SLUG = __ENV.EVENT_SLUG || 'sample-hack-2026';

export const options = {
  scenarios: {
    read_load: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: 50 },
        { duration: '1m', target: 50 },
        { duration: '10s', target: 0 },
      ],
      gracefulRampDown: '10s',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.05'],
    http_req_duration: ['p(95)<800'],
  },
};

export default function (data) {
  // k6 attaches Cookie headers from the `headers` map. We pass
  // `session=<token>` directly; k6 sets the Cookie header itself.
  const headers = withSyntheticIp(
    { Cookie: `session=${data.judgeSession}` },
    __VU,
    __ITER
  );
  const params = { headers };

  // Public gallery.
  const galleryRes = http.get(
    `${BASE_URL}/api/gallery?event=${EVENT_SLUG}`,
    params
  );
  check(galleryRes, {
    'gallery returns 200': (r) => r.status === 200,
  });

  // Widget gallery — same data, different code path.
  const widgetRes = http.get(
    `${BASE_URL}/api/widget/gallery?event=${EVENT_SLUG}`,
    params
  );
  check(widgetRes, {
    'widget gallery returns 200': (r) => r.status === 200,
  });

  // Judge's own scores. judge_a has pre-baked scores from
  // seed_fixtures, so this exercises the SELECT path under load.
  const judgeRes = http.get(`${BASE_URL}/api/judge/scores`, params);
  check(judgeRes, {
    'judge scores returns 200': (r) => r.status === 200,
    'judge scores body has scores array': (r) => {
      try {
        const body = JSON.parse(r.body);
        return Array.isArray(body.scores);
      } catch (_) {
        return false;
      }
    },
  });
}

export function setup() {
  const { data } = resolveToml(open);
  const auth = data.auth || {};
  const judgeHeader = auth.judge_a_HEADER;
  if (!judgeHeader) {
    throw new Error(
      '.dogfood.toml is missing [auth] judge_a_HEADER. Re-run seed_fixtures.'
    );
  }
  return {
    judgeSession: extractSessionCookie(judgeHeader),
    baseUrl: BASE_URL,
    eventSlug: EVENT_SLUG,
  };
}
