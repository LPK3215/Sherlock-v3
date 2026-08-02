import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      // SmallWebRTC transport: /start → 后端启动 session
      {
        source: "/start",
        destination: "http://localhost:7860/start",
      },
      // SmallWebRTC transport: /sessions/{id}/api/offer → 后端 WebRTC 信令
      {
        source: "/sessions/:sessionId/api/offer",
        destination: "http://localhost:7860/sessions/:sessionId/api/offer",
      },
    ];
  },
};

export default nextConfig;
