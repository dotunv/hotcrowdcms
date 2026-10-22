import type { NextConfig } from "next";

const api = process.env.API_URL || "http://127.0.0.1:8000";
const isDev = process.env.NODE_ENV !== "production";

// Next.js needs inline scripts for hydration and the theme bootstrap in layout.tsx, so script-src keeps
// 'unsafe-inline' (a nonce-based policy would need middleware). Everything else is locked down: no framing,
// no plugins, no cross-origin form posts or fetches. Images and video may come from any https origin
// because customers link their own media by URL.
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src 'self' https://fonts.gstatic.com data:",
  "img-src 'self' data: blob: https:",
  "media-src 'self' blob: https:",
  "connect-src 'self'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
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
