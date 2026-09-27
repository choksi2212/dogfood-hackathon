// load-tests/lib/ip.js
//
// Per-VU synthetic IP helper. The platform's RateLimitMiddleware caps
// reads at 60/min/IP and writes at 10/min/IP — without spoofing
// X-Forwarded-For, every k6 VU shares the host's IP and the limiter
// trips the failure threshold within seconds. The middleware honours
// X-Forwarded-For (no trusted-proxy check), so unique values per
// VU×ITER effectively give each request its own bucket.
//
// Set the env var `K6_NO_IP_SPOOF=1` to disable spoofing (e.g. when
// testing against a deployment where you DO trust the remote IP).

/**
 * Build an `X-Forwarded-For` value that is unique per VU×ITER, of the
 * form `10.<vu>.<iter>.1` — inside the reserved 10.0.0.0/8 range, so
 * it can never collide with a real public IP.
 *
 * @param {number} vu  k6 __VU (1-indexed VU id)
 * @param {number} iter k6 __ITER (0-indexed iteration)
 */
export function syntheticForwardedFor(vu, iter) {
  // Keep within 1..254 so we stay inside an octet and never write a
  // zero or broadcast address. k6 VUs are 1-indexed so __VU % 254 + 1
  // already covers 1..254; same for __ITER.
  const vu8 = (vu % 254) + 1;
  const iter8 = (iter % 254) + 1;
  return `10.${vu8}.${iter8}.1`;
}

/**
 * Merge X-Forwarded-For into an existing headers object unless
 * spoofing is disabled via env. Returns a NEW object — the input is
 * not mutated, which makes it safe to reuse a default template.
 *
 * @param {Record<string, string>} headers
 * @param {number} vu
 * @param {number} iter
 */
export function withSyntheticIp(headers, vu, iter) {
  const out = Object.assign({}, headers);
  if (__ENV.K6_NO_IP_SPOOF && __ENV.K6_NO_IP_SPOOF !== '0') {
    return out;
  }
  out['X-Forwarded-For'] = syntheticForwardedFor(vu, iter);
  return out;
}
