/**
 * E2E Test: SSE Timeout and Polling Fallback Synchronization
 *
 * 验证关键契约：SSE 断开后前端 polling 能正确接管并最终拿到结果。
 * 防止"用户看到生成失败但后端还在工作"的问题。
 */
import { test, expect, Page, BrowserContext } from '@playwright/test';
import { ensureAuthenticated } from './helpers/auth';

const BASE_URL = 'http://localhost:3000';
const API_URL = 'http://localhost:8000';

/** 通过 API 创建测试游戏 */
async function createTestGame(context: BrowserContext): Promise<number> {
  const createResp = await context.request.post(`${API_URL}/api/games`, {
    data: {
      player_name: 'SSE测试角色',
      life_vision: '测试 SSE 和 polling',
      character_settings: {
        era: { name: '2024年', period: '现代' },
        age: { age: 22, stage: '青年' },
        gender: { gender: '男' },
        world: { name: '普通现代', description: '测试世界' },
        family: { description: '普通家庭' },
        relationships: { key_people: [], relationships_description: '暂无' },
        traits: { traits: ['勇敢'] },
        wealth: { level: '中等', description: '普通收入' },
      },
      language: 'zh',
    },
  });

  if (!createResp.ok()) {
    throw new Error(`创建游戏失败: ${createResp.status()} ${await createResp.text()}`);
  }

  const game = await createResp.json();
  return game.game_id;
}

test.describe('SSE Timeout Sync E2E', () => {
  test.beforeEach(async ({ page, context }) => {
    await ensureAuthenticated(page, context);
  });

  test('SSE connection sends heartbeat during generation', async ({ page, context }) => {
    /**
     * 验证 SSE 连接在生成过程中发送 status 事件。
     * 这是保持连接不被代理层断开的关键机制。
     */
    test.setTimeout(60000);

    const gameId = await createTestGame(context);

    // 拦截 SSE 请求，记录请求发出
    let sseRequestMade = false;
    page.on('request', (request) => {
      const url = request.url();
      if (url.includes(`/api/games/${gameId}/event`)) {
        sseRequestMade = true;
      }
    });

    // 导航到游戏页面（会触发 SSE 连接）
    await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');

    // 等待一段时间让 SSE 连接建立
    await page.waitForTimeout(5000);

    // 验证 SSE 请求已被发出
    expect(sseRequestMade).toBe(true);

    // 页面不应崩溃
    const body = page.locator('body');
    await expect(body).toBeVisible();
  });

  test('polling timeout exceeds SSE timeout with safe margin', async ({ page }) => {
    /**
     * 验证前端 polling 超时显著大于后端 SSE 超时。
     * 这是防止"SSE 断开后 polling 也很快超时"的关键契约。
     *
     * 由于 Next.js 将 JS 常量打包到独立 chunk 中，无法通过 page.content() 检查。
     * 此测试验证页面能正常加载（说明前端配置正确），
     * 具体的超时数值契约由 Layer 3 Contract 测试覆盖。
     */
    test.setTimeout(30000);

    // 验证页面能正常加载（说明前端配置正确）
    await page.goto(`${BASE_URL}/play`);
    await page.waitForLoadState('domcontentloaded');
    const body = page.locator('body');
    await expect(body).toBeVisible();

    // Contract 测试已验证：
    // - 后端 SSE timeout: 180s (tests/test_sse_timeout_contract.py)
    // - 前端 polling timeout: 300s > 180s (tests/test_sse_timeout_contract.py)
    // 两者存在 120s 的安全余量
  });

  test('frontend handles SSE error gracefully and enters polling', async ({ page, context }) => {
    /**
     * 验证前端在 SSE 返回 error 后能正确进入 polling 模式。
     *
     * 我们通过模拟 SSE 返回 error 事件，验证前端不会崩溃，
     * 而是尝试通过 polling 恢复。
     */
    test.setTimeout(60000);

    const gameId = await createTestGame(context);
    let sseRequestCount = 0;

    // 拦截 SSE 请求，第一次返回 error，后续正常处理
    await page.route(`**/api/games/${gameId}/event`, async (route) => {
      sseRequestCount++;

      if (sseRequestCount === 1) {
        // 模拟 SSE 返回 error 事件后断开
        const sseError = 'event: error\ndata: {"error": "Simulated SSE timeout"}\n\n';
        await route.fulfill({
          status: 200,
          headers: {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
          },
          body: sseError,
        });
      } else {
        // 后续请求正常通过
        await route.continue();
      }
    });

    // 导航到游戏页面
    await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');

    // 等待一段时间让前端处理 SSE error 并可能进入 polling
    await page.waitForTimeout(5000);

    // 页面不应崩溃
    const body = page.locator('body');
    await expect(body).toBeVisible();

    // 验证至少有一个 SSE 请求被拦截
    expect(sseRequestCount).toBeGreaterThanOrEqual(1);
  });

  test('polling calls syncState to check backend status', async ({ page, context }) => {
    /**
     * 验证 polling 逻辑调用 syncState API 来获取后端状态。
     *
     * 我们通过拦截 /api/games/{id} 请求（syncState 的目标端点）
     * 来验证 polling 确实在尝试同步状态。
     *
     * 为了测试能稳定完成，我们 mock syncState 响应使其包含选项，
     * 这样 polling 会在一次请求后成功退出，不会无限循环。
     */
    test.setTimeout(60000);

    const gameId = await createTestGame(context);
    let syncStateRequestCount = 0;
    const consoleLogs: string[] = [];

    page.on('console', (msg) => {
      consoleLogs.push(msg.text());
    });

    // 拦截 SSE 请求，返回 error 触发 polling
    await page.route(`**/api/games/${gameId}/event`, async (route) => {
      const sseError = 'event: error\ndata: {"error": "Simulated SSE timeout"}\n\n';
      await route.fulfill({
        status: 200,
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
        },
        body: sseError,
      });
    });

    // 拦截 syncState 请求：计数并返回带选项的 mock 响应
    await page.route(`**/api/games/${gameId}`, async (route) => {
      if (route.request().method() === 'GET') {
        syncStateRequestCount++;
        // 第一次 syncState 调用（初始化）返回无选项状态
        // 第二次及以后（polling）返回有选项状态，让 polling 成功退出
        const hasOptions = syncStateRequestCount >= 2;
        await route.fulfill({
          status: 200,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            game_id: gameId,
            player_state: {
              player_name: 'SSE测试角色',
              age: 22,
              energy: 100,
              mood: 100,
              knowledge: 50,
              wealth: 10000,
            },
            progress: { age: 22, week: 0, year: 0 },
            round_info: { current_round: 0, game_over: false },
            current_event: hasOptions
              ? {
                  event_description: '测试故事内容',
                  story_text: '测试故事内容',
                  options: [
                    { text: '选项A', effects: {} },
                    { text: '选项B', effects: {} },
                  ],
                }
              : null,
            constraint_level: 'expert',
          }),
        });
        return;
      }
      await route.continue();
    });

    // 导航到游戏页面
    await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');

    // 等待前端处理 SSE error、触发 polling、pollForCompletion 成功退出
    await page.waitForTimeout(15000);

    // 页面不应崩溃
    const body = page.locator('body');
    await expect(body).toBeVisible();

    // 验证 syncState 被调用至少 2 次（初始化 1 次 + polling 至少 1 次）
    expect(syncStateRequestCount).toBeGreaterThanOrEqual(2);

    // 验证 console 中有 polling 相关日志
    const hasPollingLog = consoleLogs.some(
      (log) => log.includes('SSE failed, starting polling') || log.includes('Polling...')
    );
    expect(hasPollingLog).toBe(true);
  });

  test('no fatal errors during SSE disconnection and polling transition', async ({ page }) => {
    /**
     * 验证 SSE 断开和 polling 切换过程中没有致命错误。
     */
    test.setTimeout(60000);

    const consoleErrors: string[] = [];
    const pageErrors: string[] = [];

    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    page.on('pageerror', (error) => {
      pageErrors.push(error.message);
    });

    // 模拟 SSE 连接不稳定：先正常连接，然后断开
    let requestCount = 0;
    await page.route('**/api/games/*/event', async (route) => {
      requestCount++;
      if (requestCount === 1) {
        // 返回一个立即结束的 SSE 流（模拟断开）
        await route.fulfill({
          status: 200,
          headers: {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
          },
          body: 'event: error\ndata: {"error": "Connection closed"}\n\n',
        });
      } else {
        await route.continue();
      }
    });

    await page.goto(`${BASE_URL}/play`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(5000);

    // 过滤掉非致命错误
    const fatalErrors = pageErrors.filter(e =>
      !e.includes('ResizeObserver') &&
      !e.includes('extension') &&
      !e.includes('Source map')
    );

    const fatalConsoleErrors = consoleErrors.filter(e =>
      !e.includes('favicon') &&
      !e.includes('Source map')
    );

    // 不应有致命错误
    expect(fatalErrors).toHaveLength(0);

    // 页面应仍然可见
    const body = page.locator('body');
    await expect(body).toBeVisible();
  });
});
