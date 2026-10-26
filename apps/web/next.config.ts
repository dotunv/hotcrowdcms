import type { NextConfig } from "next";

const api = process.env.API_URL || "http://127.0.0.1:8000";
const isDev = process.env.NODE_ENV !== "production";

// The Content-Security-Policy is built per request in src/middleware.ts (it needs a nonce).
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
  ...(isDev ? [] : [{ key: "Strict-Transport-Security", value: "max-age=31536000" }]),
];

const nextConfig: NextConfig = {
  transpilePackages: ["@hotcrowd/contracts"],
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${api}/api/:path*` },
      { source: "/media/:path*", destination: `${api}/media/:path*` },
    ];
  },
  async headers() {
    // Pages only: /api and /media are proxied from the API, which sets its own headers
    // (uploads get a sandboxing CSP there).
    return [{ source: "/((?!api|media).*)", headers: securityHeaders }];
  },
};

export default nextConfig;
