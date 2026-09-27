// load-tests/csv_export.js
//
// Streaming CSV export load test. The /api/csv_export endpoint uses
// StreamingHttpResponse — the right metric is time-to-first-byte
// (TTFB) and overall duration, but `http_req_duration` already
// captures both. We keep the VU count low (5) because the endpoint
// holds a connection while iterating scores, and raising the head
// count primarily thrashes the response buffer rather than proving
// throughput.
//
// Endpoints exercised:
//   GET /api/csv_export?event_slug=<slug>   (organizer cookie)
//
// Usage:
//   k6 run load-tests/csv_export.js
//
// Thresholds:
//   http_req_duration  p95 < 2000ms (CSV streaming — first byte counts)
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
  vus: 5,
  duration: '30s',
  thresholds: {
    // No http_req_failed threshold — the seeded demo event may have
    // no assignments for some organizers. 200 with empty CSV body
    // is a legitimate success.
    http_req_duration: ['p(95)<2000'],
  },
};

export default function (data) {
  const headers = withSyntheticIp(
    { Cookie: `session=${data.organizerSession}` },
    __VU,
    __ITER
  );

  const res = http.get(
    `${BASE_URL}/api/csv_export?event_slug=${EVENT_SLUG}`,
    { headers }
  );
  check(res, {
    'csv export returns 200': (r) => r.status === 200,
    'csv export has text/csv content type': (r) =>
      String(r.headers['Content-Type'] || '').includes('text/csv'),
    'csv export body starts with header row': (r) =>
      typeof r.body === 'string' &&
      r.body.startsWith('event_slug,project_id,project_name'),
  });
}

export function setup() {
  const { data } = resolveToml(open);
  const auth = data.auth || {};
  const organizerHeader = auth.organizer_HEADER;
  if (!organizerHeader) {
    throw new Error(
      '.dogfood.toml is missing [auth] organizer_HEADER. Re-run seed_fixtures.'
    );
  }
  return {
    organizerSession: extractSessionCookie(organizerHeader),
    baseUrl: BASE_URL,
    eventSlug: EVENT_SLUG,
  };
}
