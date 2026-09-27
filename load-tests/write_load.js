// load-tests/write_load.js
//
// Write-heavy load test for the DOGFOOD hackathon portal. Two POSTs
// hammered at 20 VUs with a 30s ramp and a 1m hold — state-changing
// paths are more expensive than reads, so we keep the headcount lower
// but still 4x the demo traffic.
//
// Endpoints exercised:
//   POST /api/events/<slug>/submit                (participant cookie, ~1 KB body)
//   POST /api/events/<slug>/submissions/<id>/vote (participant cookie, valid id)
//
// Usage:
//   k6 run load-tests/write_load.js
//
// Thresholds:
//   http_req_failed    rate < 10%   (writes touch more rows; some contention is normal)
//   http_req_duration  p95  < 1500ms
//
// ─────────────────────────────────────────────────────────────────────
// Deadline caveat: the demo event seeded by `manage.py seed_fixtures`
// has `submissions_close_at` one hour in the PAST — that is intentional
// for the T1 acceptance check 3 ("post-deadline submit returns 422").
// While that past deadline stands, BOTH submit and vote return 422
// with `code: deadline_passed` immediately after auth+event lookup,
// before any actual write occurs.
//
// In that case:
//   - The platform is still being load-tested: auth lookup, session
//     validation, event lookup, and the decorator stack all execute
//     per request. 422 is a normal response, not a 5xx.
//   - The strict `http_req_failed rate<0.10` threshold WILL trip,
//     because k6 counts 4xx as failures. To exercise the real write
//     paths and pass thresholds, push `submissions_close_at` into the
//     future (Django shell — `python manage.py shell -c "from
//     apps.events.models import Event; e = Event.objects.get(
//     slug='sample-hack-2026'); from django.utils import timezone; from
//     datetime import timedelta; e.submissions_close_at = timezone.now()
//     + timedelta(hours=2); e.save()"`).
//
// ─────────────────────────────────────────────────────────────────────
// Rate limit caveat: see smoke.js — `X-Forwarded-For` is spoofed per
// VU×ITER by default. The write bucket is 10/min/IP, so spoofing is
// essential. `K6_NO_IP_SPOOF=1` disables it.
// ─────────────────────────────────────────────────────────────────────

import http from 'k6/http';
import { check } from 'k6';
import { open } from 'k6/fs';

import { resolveToml, extractSessionCookie } from './lib/toml.js';
import { withSyntheticIp } from './lib/ip.js';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const EVENT_SLUG = __ENV.EVENT_SLUG || 'sample-hack-2026';

// 1 KB JSON body. The seed participant submits for their team (team 0
// in the fixture). The body is a payload large enough to exercise
// JSON parsing, body validation, and (when the deadline is open) the
// get_or_create + save path.
function buildSubmitBody(i) {
  // Pad `description` with ~900 chars of unique data so the body is
  // genuinely ~1 KB; the rest (~120) is name + tagline + track_slug.
  const padding = 'x'.repeat(900) + i;
  return JSON.stringify({
    name: `load-test submission ${i}`,
    tagline: 'hammered by k6 write_load.js',
    description: padding,
    track_slug: 'main',
  });
}

export const options = {
  scenarios: {
    write_load: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: 20 },
        { duration: '1m', target: 20 },
        { duration: '10s', target: 0 },
      ],
      gracefulRampDown: '10s',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.10'],
    http_req_duration: ['p(95)<1500'],
  },
};

export default function (data) {
  const headers = withSyntheticIp(
    {
      'Content-Type': 'application/json',
      Cookie: `session=${data.participantSession}`,
    },
    __VU,
    __ITER
  );
  const params = { headers };

  // 1. Submit (idempotent on the participant's team — get_or_create).
  const submitRes = http.post(
    `${BASE_URL}/api/events/${EVENT_SLUG}/submit`,
    buildSubmitBody(__VU * 10000 + __ITER),
    params
  );
  check(submitRes, {
    'submit returns 201 (or 422 if deadline is closed)': (r) =>
      r.status === 201 ||
      (r.status === 422 &&
        (() => {
          try {
            return JSON.parse(r.body).error.code === 'deadline_passed';
          } catch (_) {
            return false;
          }
        })()),
  });

  // 2. Vote — exercise the per-voter upsert path. data.voteTargetId
  // comes from setup() (a non-self-team submission id fetched from
  // the public gallery, so we never trip the self-vote guard).
  const voteRes = http.post(
    `${BASE_URL}/api/events/${EVENT_SLUG}/submissions/${data.voteTargetId}/vote`,
    JSON.stringify({ votes: 1 }),
    params
  );
  check(voteRes, {
    'vote returns 201 (or 422 if deadline is closed)': (r) =>
      r.status === 201 ||
      (r.status === 422 &&
        (() => {
          try {
            return JSON.parse(r.body).error.code === 'deadline_passed';
          } catch (_) {
            return false;
          }
        })()),
  });
}

export function setup() {
  const { data } = resolveToml(open);
  const auth = data.auth || {};
  const participantHeader = auth.participant_HEADER;
  if (!participantHeader) {
    throw new Error(
      '.dogfood.toml is missing [auth] participant_HEADER. Re-run seed_fixtures.'
    );
  }

  // Find a non-self-team submission id to vote on. The seeded
  // participant is on team 0 ("Quokka Collective"). Any submission
  // whose name does NOT start with "Quokka" is fair game.
  //
  // The gallery endpoint is public — we don't need a cookie here.
  const galleryRes = http.get(
    `${BASE_URL}/api/gallery?event=${EVENT_SLUG}`
  );
  if (galleryRes.status !== 200) {
    throw new Error(
      `Gallery lookup failed during setup (status=${galleryRes.status}). ` +
        'Is the portal up?'
    );
  }
  let items;
  try {
    items = JSON.parse(galleryRes.body).items;
  } catch (e) {
    throw new Error(
      'Gallery response was not JSON. Body: ' +
        String(galleryRes.body).slice(0, 200)
    );
  }
  if (!Array.isArray(items) || items.length === 0) {
    throw new Error(
      'Gallery returned no items. Run seed_fixtures to populate the demo event.'
    );
  }
  // Prefer a non-Quokka submission. Fall back to items[0] only if
  // every submission happens to be a Quokka (impossible in the
  // shipped fixtures, but cheap to defend against).
  const target =
    items.find((it) => !/^Quokka/.test(it.name || '')) || items[0];
  if (!target.id) {
    throw new Error(
      'Gallery item missing id field. Got: ' + JSON.stringify(target)
    );
  }

  return {
    participantSession: extractSessionCookie(participantHeader),
    voteTargetId: target.id,
    baseUrl: BASE_URL,
    eventSlug: EVENT_SLUG,
  };
}
