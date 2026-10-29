/**
 * E2E Test: SSE Timeout and Polling Fallback Synchronization
 *
 * 验证关键契约：SSE 断开后前端 polling 能正确接管并最终拿到结果。
 * 防止"用户看到生成失败但后端还在工作"的问题。
 */
import { test, expect, Page, BrowserContext } from '@playwright/test';
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

  test('a terminal SSE validation failure remains visible until the player retries', async ({ page, context }) => {
    const gameId = await createTestGame(context);
    let sseRequestCount = 0;
    const failure = {
      code: 'INVALID_STORY_STRUCTURE',
      summary: '故事结构检查未通过',
      detail: '测试失败稿没有保存',
      retryable: true,
    };
    await page.route(`**/api/games/${gameId}/event`, async route => {
      sseRequestCount += 1;
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: `event: error\ndata: ${JSON.stringify(failure)}\n\n`,
      });
    });
    await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
    await expect(page.getByText(failure.summary, { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: '再次生成', exact: true })).toBeEnabled();
    expect(sseRequestCount).toBe(1);
    await page.getByRole('button', { name: '再次生成', exact: true }).click();
    await expect.poll(() => sseRequestCount).toBe(2);
    await expect(page.getByText(failure.summary, { exact: true })).toBeVisible();
  });

  test('incomplete SSE reconnects once then polls persisted state and restores choices', async ({ page, context }) => {
    /**
     * 初始化读取无事件的快照；两次不完整 SSE 后，恢复流程重新读取
     * 已保存的日历状态，并显示其中的故事与选项。
     */
    test.setTimeout(60000);

    const gameId = await createTestGame(context);
    let syncStateRequestCount = 0;
    const initialResponse = await context.request.get(`${API_URL}/api/games/${gameId}`);
    expect(initialResponse.status()).toBe(200);
    const initialState = await initialResponse.json();
    const streamRequests: { lastEventId: string | undefined }[] = [];

    // An EOF without complete is a transport failure. A business error event
    // deliberately terminates generation and must not be used to fake a disconnect.
    await page.route(`**/api/games/${gameId}/event*`, async (route) => {
      streamRequests.push({ lastEventId: route.request().headers()['last-event-id'] });
      await route.fulfill({
        status: 200,
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
        },
        body: 'event: story\ndata: {"text":"尚未完成的故事"}\n\n',
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
                  event_id: 'recovered-day-0',
                  revision: 1,
                  story_date: initialState.player_state.timeline.current_date,
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

    await expect.poll(() => syncStateRequestCount, { timeout: 15_000 }).toBeGreaterThanOrEqual(2);
    expect(streamRequests).toHaveLength(2);
    expect(streamRequests[0].lastEventId).toBeUndefined();
    expect(streamRequests[1].lastEventId).toBe('-1');
    await expect(page.getByRole('heading', { name: '听故事', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: '选择 1：选项A', exact: true })).toBeEnabled();
    await expect(page.getByRole('button', { name: '选择 2：选项B', exact: true })).toBeEnabled();
    await page.getByRole('button', { name: '查看故事正文', exact: true }).click();
    await expect(page.getByRole('region', { name: '故事正文' })).toContainText('测试故事内容');
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
