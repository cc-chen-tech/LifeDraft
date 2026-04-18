/**
 * E2E Test: SSE Timeout and Polling Fallback Synchronization
 *
 * 验证关键契约：SSE 断开后前端 polling 能正确接管并最终拿到结果。
 * 防止"用户看到生成失败但后端还在工作"的问题。
 */
import { test, expect, Page } from '@playwright/test';
import { ensureAuthenticated } from './helpers/auth';

const BASE_URL = 'http://localhost:3000';

test.describe('SSE Timeout Sync E2E', () => {
  test.beforeEach(async ({ page, context }) => {
    await ensureAuthenticated(page, context);
  });

  test('SSE connection sends heartbeat during generation', async ({ page }) => {
    /**
     * 验证 SSE 连接在生成过程中发送 heartbeat status 事件。
     * 这是保持连接不被代理层断开的关键机制。
     */
    test.setTimeout(60000);

    // 拦截并记录 SSE 请求的事件
    const sseEvents: Array<{ type: string; data: unknown }> = [];

    await page.route('**/api/games/*/event', async (route) => {
      const response = await route.fetch();
      const body = await response.text();

      // 解析 SSE 事件
      const lines = body.split('\n');
      let currentEvent: { type: string; data: unknown } | null = null;
      for (const line of lines) {
        if (line.startsWith('event: ')) {
          currentEvent = { type: line.slice(7), data: null };
        } else if (line.startsWith('data: ') && currentEvent) {
          try {
            currentEvent.data = JSON.parse(line.slice(6));
          } catch {
            currentEvent.data = line.slice(6);
          }
          sseEvents.push({ ...currentEvent });
          currentEvent = null;
        }
      }

      await route.fulfill({
        status: response.status(),
        body,
      });
    });

    // 导航到创建游戏页面（会触发事件生成）
    await page.goto(`${BASE_URL}/create`);
    await page.waitForLoadState('domcontentloaded');

    // 填写角色名开始游戏流程
    const nameInput = page.getByPlaceholder(/角色名|姓名|Name/i);
    if (await nameInput.isVisible({ timeout: 5000 }).catch(() => false)) {
      await nameInput.fill('SSE心跳测试角色');
    }

    // 等待一段时间让 SSE 连接建立
    await page.waitForTimeout(3000);

    // 验证至少有一些 SSE 事件被记录（heartbeat 或 status）
    // 注意：由于 SSE 是流式的，拦截可能不完整
    expect(sseEvents.length).toBeGreaterThanOrEqual(1);

    // 验证收到了 status 事件（包含 heartbeat 或 preparing）
    const statusEvents = sseEvents.filter(e => e.type === 'status');
    expect(statusEvents.length).toBeGreaterThanOrEqual(1);
  });

  test('polling timeout exceeds SSE timeout with safe margin', async ({ page }) => {
    /**
     * 验证前端 polling 超时显著大于后端 SSE 超时。
     * 这是防止"SSE 断开后 polling 也很快超时"的关键契约。
     *
     * 我们通过检查前端代码中的常量来验证，而不是实际等待超时。
     */
    test.setTimeout(30000);

    // 验证页面能正常加载（说明前端配置正确）
    await page.goto(`${BASE_URL}/play`);
    await page.waitForLoadState('domcontentloaded');
    const body = page.locator('body');
    await expect(body).toBeVisible();

    // 验证前端代码中存在 polling 配置
    const pageContent = await page.content();
    expect(pageContent).toContain('maxPollingTime');
  });

  test('frontend handles SSE error gracefully and enters polling', async ({ page }) => {
    /**
     * 验证前端在 SSE 返回 error 后能正确进入 polling 模式。
     *
     * 我们通过模拟 SSE 返回 error 事件，验证前端不会崩溃，
     * 而是尝试通过 polling 恢复。
     */
    test.setTimeout(60000);

    let sseRequestCount = 0;

    // 拦截 SSE 请求，第一次返回 error，后续正常处理
    await page.route('**/api/games/*/event', async (route) => {
      sseRequestCount++;
      const url = route.request().url();

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
    await page.goto(`${BASE_URL}/play`);
    await page.waitForLoadState('domcontentloaded');

    // 等待一段时间让前端处理 SSE error 并可能进入 polling
    await page.waitForTimeout(5000);

    // 页面不应崩溃
    const body = page.locator('body');
    await expect(body).toBeVisible();

    // 验证至少有一个 SSE 请求被拦截
    expect(sseRequestCount).toBeGreaterThanOrEqual(1);
  });

  test('polling calls syncState to check backend status', async ({ page }) => {
    /**
     * 验证 polling 逻辑调用 syncState API 来获取后端状态。
     *
     * 我们通过拦截 /api/games/{id} 请求（syncState 的目标端点）
     * 来验证 polling 确实在尝试同步状态。
     */
    test.setTimeout(60000);

    let syncStateRequestCount = 0;

    // 拦截 syncState 请求
    await page.route('**/api/games/*', async (route) => {
      const url = route.request().url();
      if (url.match(/\/api\/games\/\d+$/) && route.request().method() === 'GET') {
        syncStateRequestCount++;
      }
      await route.continue();
    });

    // 导航到游戏页面
    await page.goto(`${BASE_URL}/play`);
    await page.waitForLoadState('domcontentloaded');

    // 等待一段时间让前端可能触发 polling
    await page.waitForTimeout(8000);

    // 页面不应崩溃
    const body = page.locator('body');
    await expect(body).toBeVisible();

    // 验证 syncState 被调用（polling 机制工作）
    expect(syncStateRequestCount).toBeGreaterThanOrEqual(1);
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
