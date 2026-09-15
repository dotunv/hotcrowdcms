import type { NextConfig } from "next";

const api = process.env.API_URL || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  transpilePackages: ["@hotcrowd/contracts"],
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${api}/api/:path*` },
      { source: "/media/:path*", destination: `${api}/media/:path*` },
    ];
  },
};

export default nextConfig;
