// load-tests/lib/toml.js
//
// Tiny TOML parser used by every load script to read pre-baked session
// cookies from `../.dogfood.toml` at runtime.
//
// Scope: only the shape present in .dogfood.toml — section headers
// (`[auth]`), `key = "value"` pairs, and `#` line comments. No inline
// tables, no multi-line strings, no numbers, no booleans, no arrays.
// That is exactly enough for the auth block; generalising further
// invites correctness bugs we'd never catch in a load harness.
//
// Also exposes `resolveToml()` which finds the file from either
// `k6 run load-tests/<script>.js` (cwd = repo root) or
// `cd load-tests && k6 run <script>.js` (cwd = load-tests/).

/**
 * Parse a small, predictable subset of TOML into a nested object
 * keyed by section name. Each section is an object of key → string.
 */
export function parseToml(text) {
  const result = {};
  let section = result;
  const lines = text.split(/\r?\n/);
  for (const raw of lines) {
    const line = raw.trim();
    if (!line || line.startsWith('#')) continue;
    const sectionMatch = line.match(/^\[([^\]]+)\]$/);
    if (sectionMatch) {
      const name = sectionMatch[1].trim();
      if (!result[name]) result[name] = {};
      section = result[name];
      continue;
    }
    const kvMatch = line.match(/^([A-Za-z0-9_]+)\s*=\s*"(.*)"\s*$/);
    if (kvMatch) {
      section[kvMatch[1]] = kvMatch[2];
    }
  }
  return result;
}

/**
 * Read .dogfood.toml from either of two candidate paths and return
 * both the parsed object and the path that was used.
 *
 * @param {typeof import('k6/fs').open} open - injected so this module
 *   stays testable without k6's filesystem binding.
 */
export function resolveToml(open) {
  const candidates = ['../.dogfood.toml', './.dogfood.toml'];
  const errors = [];
  for (const p of candidates) {
    let text;
    try {
      text = open(p);
    } catch (e) {
      errors.push(`${p}: ${e && e.message ? e.message : e}`);
      continue;
    }
    return { path: p, data: parseToml(text) };
  }
  throw new Error(
    'Could not open .dogfood.toml from either ../.dogfood.toml or ' +
      './.dogfood.toml. Run k6 from the repo root ' +
      "('k6 run load-tests/<script>.js') or from inside load-tests/. " +
      'Errors: ' + errors.join('; ')
  );
}

/**
 * Extract the cookie value (`session=<token>`) from a `Cookie: session=<token>`
 * header value as stored in .dogfood.toml under `*_HEADER` keys.
 */
export function extractSessionCookie(headerValue) {
  // The header in .dogfood.toml looks like: `Cookie: session=...`.
  // k6 wants a Cookie header it can attach; the `Cookie:` prefix is
  // unnecessary — k6 sets the Cookie header from the jar. We strip it.
  const m = String(headerValue).match(/session=([A-Za-z0-9_\-]+)/);
  if (!m) {
    throw new Error(
      `Could not extract session token from header value: ${headerValue}`
    );
  }
  return m[1];
}
