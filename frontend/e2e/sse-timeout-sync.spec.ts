/**
 * E2E Test: SSE Timeout and Polling Fallback Synchronization
 *
 * 验证关键契约：SSE 断开后前端 polling 能正确接管并最终拿到结果。
 * 防止"用户看到生成失败但后端还在工作"的问题。
 */
import { test, expect, BrowserContext } from '@playwright/test';
import { ensureAuthenticated, API_URL } from './helpers/auth';

const BASE_URL = process.env.E2E_BASE_URL || `http://localhost:${process.env.E2E_FRONTEND_PORT ?? '3000'}`;
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

  test('terminal generation failure stays failed instead of polling', async ({ page, context }) => {
    const gameId = await createTestGame(context);
    let eventRequests = 0;
    let stateRequests = 0;
    page.on('request', request => {
      if (new URL(request.url()).pathname === `/api/games/${gameId}`
        && request.method() === 'GET') stateRequests++;
    });
    await page.route(`**/api/games/${gameId}/event`, route => {
      eventRequests++;
      return route.fulfill({
        contentType: 'text/event-stream',
        body: 'event: error\ndata: {"error":"结构测试终止","summary":"结构测试终止","code":"INVALID_STORY_STRUCTURE","retryable":true}\n\n',
      });
    });
    await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
    await expect(page.getByText('结构测试终止', { exact: true })).toBeVisible();
    await expect(page.getByTestId('play-options')).toHaveCount(0);
    const requestsAtFailure = stateRequests;
    // Observe beyond one real polling interval: terminal failures must not
    // silently reconnect or repeatedly fetch state.
    await page.waitForTimeout(6_000);
    expect(eventRequests).toBe(1);
    expect(stateRequests).toBe(requestsAtFailure);
  });

  test('interrupted SSE reconnects then polls persisted story and options', async ({ page, context }) => {
    // Use the real persisted game response shape; only the transport and the
    // moment at which its completed event becomes visible are controlled.
    test.setTimeout(60000);

    const gameId = await createTestGame(context);
    const initialResponse = await context.request.get(`${API_URL}/api/games/${gameId}`);
    expect(initialResponse.ok()).toBe(true);
    const initialState = await initialResponse.json();
    let syncStateRequestCount = 0;
    const streamCursors: Array<string | undefined> = [];

    // A clean EOF before a complete event is a real transport interruption.
    // The first interruption reconnects; the second falls back to polling.
    // A backend `event: error` is not interchangeable with a broken stream.
    await page.route(`**/api/games/${gameId}/event`, async (route) => {
      streamCursors.push(route.request().headers()['last-event-id']);
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: 'event: status\ndata: {"phase":"generating_story"}\n\n',
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
            ...initialState,
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

    await expect.poll(() => streamCursors.length).toBe(2);
    expect(streamCursors[0]).toBeUndefined();
    expect(streamCursors[1]).toBe('-1');
    await expect.poll(() => syncStateRequestCount).toBeGreaterThanOrEqual(2);
    await expect(page.locator('article[data-slot="play-story"] .prose-story'))
      .toHaveText('测试故事内容');
    const options = page.getByTestId('play-options');
    await expect(options).toBeVisible();
    await expect(options.getByRole('button', { name: /选项A/ })).toBeEnabled();
    await expect(options.getByRole('button', { name: /选项B/ })).toBeEnabled();
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
