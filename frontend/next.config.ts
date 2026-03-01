import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Disable Strict Mode to prevent double SSE connections in development
  reactStrictMode: false,
  // Allow LAN/mobile dev access without cross-origin warnings
  allowedDevOrigins: ["http://192.168.0.107:3000"],
  // Only forward NEXT_PUBLIC_API_BASE if explicitly set in environment.
  // Otherwise sse.ts auto-detects using window.location.hostname + port 8000,
  // which works for both localhost and LAN/mobile access.
  env: {
    ...(process.env.NEXT_PUBLIC_API_BASE
      ? { NEXT_PUBLIC_API_BASE: process.env.NEXT_PUBLIC_API_BASE }
      : {}),
  },
  // ★ 增加代理超时时间，图片生成可能需要60秒以上
  experimental: {
    proxyTimeout: 120000,  // 2分钟
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://127.0.0.1:8000/api/:path*",
      },
    ];
  },
  // ★ 禁用图片 API 的缓存，确保重新生成后能立即看到新图片
  async headers() {
    return [
      {
        source: "/api/images/file/:path*",
        headers: [
          { key: "Cache-Control", value: "no-cache, no-store, must-revalidate" },
          { key: "Pragma", value: "no-cache" },
          { key: "Expires", value: "0" },
        ],
      },
    ];
  },
};

export default nextConfig;
