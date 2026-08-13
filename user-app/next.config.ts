import type { NextConfig } from "next";

const sherlockServerUrl = process.env.SHERLOCK_SERVER_URL || "http://localhost:5050";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/sherlock-api/:path*",
        destination: `${sherlockServerUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
