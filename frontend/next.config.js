/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // In docker, the API lives behind nginx on the same host. Both
  // /api routes and the widget/embeddable JS proxy through nginx so
  // this works in dev too.
  async rewrites() {
    return [
      { source: "/api/:path*", destination: "http://nginx/api/:path*" },
    ];
  },
};

module.exports = nextConfig;
