import type { NextConfig } from "next";

const botServerUrl = process.env.BOT_SERVER_URL || "http://localhost:7860";
const yuxiServerUrl = process.env.YUXI_SERVER_URL || "http://localhost:5050";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      // SmallWebRTC transport: /sessions/{id}/api/offer → 后端 WebRTC 信令
      {
        source: "/sessions/:sessionId/api/offer",
        destination: `${botServerUrl}/sessions/:sessionId/api/offer`,
      },
      {
        source: "/api/sessions/:sessionId/api/offer",
        destination: `${botServerUrl}/sessions/:sessionId/api/offer`,
      },
      {
        source: "/yuxi-api/:path*",
        destination: `${yuxiServerUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
