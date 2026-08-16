import { withSentryConfig } from "@sentry/nextjs";
import type { NextConfig } from "next";
import { resolveTurbopackRoot } from "./scripts/resolve-turbopack-root.mjs";

const nextConfig: NextConfig = {
  // Disable Strict Mode to prevent double SSE connections in development
  reactStrictMode: false,
  // 禁用 Next.js Dev Overlay，避免 E2E 测试中拦截点击事件
  devIndicators: false,
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
  // Standalone 输出模式用于生产部署；E2E 使用 next start，需要临时关闭。
  output: process.env.NEXT_DISABLE_STANDALONE === '1' ? undefined : 'standalone',
  // 显式设置 Turbopack root 以避免多 lockfile 导致的模块解析错误
  turbopack: {
    // Linked worktrees share node_modules with the main checkout. Turbopack
    // requires both the project and the resolved dependency target under root.
    root: resolveTurbopackRoot(__dirname),
  },
  // ★ API 代理已迁移到 src/app/api/[...path]/route.ts
  // 使用 API Route 可以正确转发 Set-Cookie 头
};

// 仅在有 SENTRY_DSN 时启用 Sentry 构建插件
const sentryEnabled = !!process.env.NEXT_PUBLIC_SENTRY_DSN;

export default sentryEnabled
  ? withSentryConfig(nextConfig, {
      // 静默模式，不在构建时输出 Sentry 日志
      silent: true,
      // 不自动上传 source maps（需要 Sentry auth token）
      // @ts-ignore - Sentry 类型定义可能不完整
      disableServerWebpackPlugin: true,
      // @ts-ignore - Sentry 类型定义可能不完整
      disableClientWebpackPlugin: true,
    })
  : nextConfig;
