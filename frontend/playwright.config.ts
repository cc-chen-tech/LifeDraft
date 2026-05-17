import { defineConfig, devices } from '@playwright/test';

/**
 * E2E 测试配置 - 双阶段执行策略
 *
 * 解决两个结构性问题：
 * 1. AI 测试耗尽资源导致 server 崩溃 → 级联 ERR_CONNECTION_REFUSED
 *    方案：将测试分为 core（非 AI）和 ai-heavy 两个项目，core 先跑
 *
 * 2. AI 生成超时
 *    方案：ai-heavy 项目使用 5 分钟超时 + 重试 + 串行执行
 *
 * 执行顺序：
 *   Phase 1: core (非 AI 测试) - 快速、稳定、不消耗服务器资源
 *   Phase 2: ai-heavy (AI 测试) - 慢速、资源密集、串行执行
 *   Phase 3: mobile (非 AI 测试, 仅本地) - 移动端验证
 */

// ============================================================================
// AI 重度依赖的测试文件
// 这些测试会触发真实 LLM 调用，消耗大量服务器资源
// ============================================================================
const AI_HEAVY_TESTS = [
  '**/narrative-systems.spec.ts',         // 三大叙事系统集成, 多个 120s timeout
  '**/character-settings-persistence.spec.ts', // 角色设置持久化, 300s timeout
  '**/music-player.spec.ts',              // 音乐播放器, 180s (需 AI 生成故事 + 音乐推荐)
  '**/music-playlist-persistence.spec.ts', // 播放列表持久化, 180s
  '**/sse-timeout-sync.spec.ts',          // SSE 超时同步, 创建游戏触发 AI 生成
  '**/claude-code-improvements.spec.ts',  // 进度显示验证, 120s (需 AI 生成过程)
  '**/full-game-flow.spec.ts',            // 完整游戏流程, 120s
  '**/stability.spec.ts',                 // 稳定性测试, 90s
  '**/event-generation-race.spec.ts',     // 事件生成竞态, 120s
  '**/story-summary.spec.ts',             // 故事总结, 创建游戏触发 AI
  '**/choice-impact-visible.spec.ts',      // 选择影响可见性, 需要真实 AI 响应
  '**/era-validator-no-false-positive.spec.ts', // 时代验证器, 需要真实 AI 响应
];

// Production-site exploration is intentionally manual: it targets story101.live,
// can run for 30 minutes, and should not block default CI for local code changes.
const MANUAL_EXPLORATION_TESTS = ['**/story101-exploration.spec.ts'];

export default defineConfig({
  testDir: './e2e',

  /* 全局默认超时 (非 AI 测试) */
  timeout: 60_000,

  /* 默认并行执行 */
  fullyParallel: true,

  /* CI 中禁止 test.only */
  forbidOnly: !!process.env.CI,

  /* 重试策略: CI 多重试, 本地也重试 1 次以应对瞬时故障 */
  retries: process.env.CI ? 2 : 1,

  /* 工作线程: 限制并发以减少服务器压力 */
  workers: process.env.CI ? 1 : 2,

  /* Reporter */
  reporter: 'html',

  /* 级联失败保护: 累计 N 个失败后停止整个测试套件 */
  maxFailures: process.env.CI ? 10 : 5,

  /* 全局健康检查 */
  globalSetup: require.resolve('./e2e/global-setup'),
  globalTeardown: require.resolve('./e2e/global-teardown'),

  /* 共享配置 */
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  /* 双阶段项目配置 */
  projects: process.env.CI
    ? [
        // ── CI: 同样分阶段, 但只跑 chromium ──
        {
          name: 'core',
          testIgnore: [...AI_HEAVY_TESTS, ...MANUAL_EXPLORATION_TESTS],
          use: { ...devices['Desktop Chrome'] },
        },
        {
          name: 'ai-heavy',
          testMatch: AI_HEAVY_TESTS,
          dependencies: ['core'],
          use: { ...devices['Desktop Chrome'] },
          timeout: 300_000,     // 5 分钟超时
          retries: 2,           // AI 测试多重试
          fullyParallel: false, // 串行执行, 减少资源竞争
        },
        ...(process.env.STORY101_DEEP_EXPLORATION === '1'
          ? [{
              name: 'story101-exploration',
              testMatch: MANUAL_EXPLORATION_TESTS,
              use: { ...devices['Desktop Chrome'] },
              timeout: 1_800_000,
              retries: 0,
              fullyParallel: false,
            }]
          : []),
      ]
    : [
        // ── 本地开发: 分阶段 + 移动端 ──

        // Phase 1: 核心测试 (非 AI)
        // 快速验证 UI 结构、路由、API 契约等
        {
          name: 'core',
          testIgnore: [...AI_HEAVY_TESTS, ...MANUAL_EXPLORATION_TESTS],
          use: { ...devices['Desktop Chrome'] },
        },

        // Phase 2: AI 重度测试
        // 依赖 core 完成后再运行, 防止 AI 测试崩溃影响核心测试
        {
          name: 'ai-heavy',
          testMatch: AI_HEAVY_TESTS,
          dependencies: ['core'],
          use: { ...devices['Desktop Chrome'] },
          timeout: 300_000,      // 5 分钟超时 (AI 生成可能需要 60-180s)
          retries: 1,            // 重试 1 次, 应对瞬时资源不足
          fullyParallel: false,  // 串行执行, 避免多个 AI 请求并发压垮服务器
        },

        // Phase 3: 移动端测试 (仅非 AI)
        {
          name: 'Mobile Safari',
          testIgnore: [...AI_HEAVY_TESTS, ...MANUAL_EXPLORATION_TESTS],
          use: { ...devices['iPhone 13'] },
          dependencies: ['core'],
        },
        ...(process.env.STORY101_DEEP_EXPLORATION === '1'
          ? [{
              name: 'story101-exploration',
              testMatch: MANUAL_EXPLORATION_TESTS,
              use: { ...devices['Desktop Chrome'] },
              timeout: 1_800_000,
              retries: 0,
              fullyParallel: false,
            }]
          : []),
      ],

  /* Dev server 自动启动 (仅本地) */
  ...(process.env.CI ? {} : {
    webServer: {
      command: 'npm run dev',
      url: 'http://localhost:3000',
      reuseExistingServer: true,
      timeout: 120 * 1000,
      env: Object.fromEntries(
        Object.entries(process.env).filter(([, v]) => v !== undefined)
      ) as Record<string, string>,
    },
  }),
});
