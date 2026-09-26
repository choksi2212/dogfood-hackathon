import type { NextConfig } from "next";

// Browser requests hit /api/* on this same origin and get proxied
// server-side to Django. This mirrors the nginx reverse proxy the
// production docker-compose sets up (docs/TRD.md §8.2) — same-origin
// from the browser's point of view, so no CORS config and cookies land
// on the right domain without extra work.
const API_INTERNAL_URL = process.env.API_INTERNAL_URL ?? "http://localhost:8001";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${API_INTERNAL_URL}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
