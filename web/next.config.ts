import type { NextConfig } from "next";

// Browser requests hit /api/* on this same origin and get proxied
// server-side to Django. This mirrors the nginx reverse proxy the
// production docker-compose sets up (docs/TRD.md §8.2) — same-origin
// from the browser's point of view, so no CORS config and cookies land
// on the right domain without extra work.
const API_INTERNAL_URL = process.env.API_INTERNAL_URL ?? "http://localhost:8001";

const nextConfig: NextConfig = {
  // Browsers hit the app via nginx on 127.0.0.1:8000 / localhost:8000,
  // not the Next dev server's own origin (frontend:3000) — without this,
  // Next's dev-mode cross-origin guard blocks HMR and RSC requests that
  // arrive proxied from a different apparent origin.
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_INTERNAL_URL}/api/:path*`,
      },
      // Embeddable widget script (issue #13): Django serves /widget.js at
      // the project root (apps/widget/views.py) and nginx already proxies
      // it in the all-in-one build (nginx-all-in-one.conf). But when
      // Next.js is the public surface — the deployed portal fronts this
      // app directly — the embed URL must be rewritten to Django too, or
      // it falls through to Next's 404 HTML page and breaks every
      // third-party <script src=".../widget.js"> with a SyntaxError.
      {
        source: "/widget.js",
        destination: `${API_INTERNAL_URL}/widget.js`,
      },
    ];
  },
};

export default nextConfig;
