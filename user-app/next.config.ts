import type { NextConfig } from "next";

const yuxiServerUrl = process.env.YUXI_SERVER_URL || "http://localhost:5050";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/yuxi-api/:path*",
        destination: `${yuxiServerUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
