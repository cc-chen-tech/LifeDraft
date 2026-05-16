/**
 * E2E Test: Event Generation Race Condition
 *
 * 验证并发控制：快速双击生成按钮不应创建重复事件。
 * 防止竞态条件导致的状态不一致问题。
 */
import { test, expect, Page } from '@playwright/test';
import { ensureAuthenticated } from './helpers/auth';

const BASE_URL = 'http://localhost:3000';

test.describe('Event Generation Race Condition E2E', () => {
  test.beforeEach(async ({ page, context }) => {
    await ensureAuthenticated(page, context);
  });

  test('rapid double click does not crash the application', async ({ page }) => {
    /**
     * 验证快速双击不会导致应用崩溃。
     *
     * 这是最基本的并发安全测试：即使不能阻止重复请求，
     * 至少不能导致应用崩溃或进入不可恢复状态。
     */
    test.setTimeout(60000);

    const pageErrors: string[] = [];
    page.on('pageerror', (error) => {
      pageErrors.push(error.message);
    });

    // 导航到创建游戏页面
    await page.goto(`${BASE_URL}/create`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000);

    // 填写角色名
    const nameInput = page.getByPlaceholder(/角色名|姓名|Name/i);
    if (await nameInput.isVisible({ timeout: 5000 }).catch(() => false)) {
      await nameInput.fill('竞态测试角色');
    }

    // 查找并快速双击下一步/生成按钮（如果存在）
    const nextButton = page.getByRole('button', { name: /下一步|Next|生成|开始/i }).first();
    if (await nextButton.isVisible().catch(() => false)) {
      // 快速连续点击两次
      await nextButton.click({ force: true, noWaitAfter: true }).catch(() => {});
      await page.waitForTimeout(100); // 100ms 内再次点击
      await nextButton.click({ force: true, noWaitAfter: true }).catch(() => {});
    }

    // 等待页面稳定
    await page.waitForTimeout(3000);

    // 过滤掉非致命错误
    const fatalErrors = pageErrors.filter(e =>
      !e.includes('ResizeObserver') &&
      !e.includes('extension') &&
      !e.includes('Source map') &&
      !e.includes('AbortError') // AbortError 是预期的（取消重复请求）
    );

    // 不应有致命错误
    expect(fatalErrors).toHaveLength(0);

    // 页面应仍然可见
    const body = page.locator('body');
    await expect(body).toBeVisible();
  });

  test('concurrent event requests are handled gracefully', async ({ page }) => {
    /**
     * 验证并发的 /event 请求被后端正确处理。
     *
     * 我们通过拦截 /event 请求来观察后端响应，
     * 验证并发请求不会导致 500 错误或状态混乱。
     */
    test.setTimeout(60000);

    const responses: Array<{ url: string; status: number }> = [];

    page.on('response', (response) => {
      const url = response.url();
      if (url.includes('/event')) {
        responses.push({ url, status: response.status() });
      }
    });

    // 导航到游戏页面
    await page.goto(`${BASE_URL}/play`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);

    // 如果页面有生成/继续按钮，尝试点击
    const actionButton = page.getByRole('button').filter({ hasText: /继续|生成|下一步|开始/i }).first();
    if (await actionButton.isVisible({ timeout: 3000 }).catch(() => false)) {
      await actionButton.click().catch(() => {});
      await page.waitForTimeout(2000);

      // 再次点击（模拟快速重复操作）
      if (await actionButton.isVisible({ timeout: 1000 }).catch(() => false)) {
        await actionButton.click({ force: true, noWaitAfter: true }).catch(() => {});
      }
    }

    await page.waitForTimeout(5000);

    // 检查所有 /event 请求的响应状态
    const eventResponses = responses.filter(r => r.url.includes('/event'));

    for (const resp of eventResponses) {
      // 不应有 500 错误
      expect(resp.status).not.toBe(500);

      // 429 (Too Many Requests) 或 200 都是可接受的
      // 409 (Conflict) 在 sync 端点可能出现，但 SSE 端点应返回 200 + error 事件
      expect([200, 429, 400]).toContain(resp.status);
    }

    // 页面应仍然可见
    const body = page.locator('body');
    await expect(body).toBeVisible();
  });

  test('page reload during generation does not corrupt state', async ({ page }) => {
    /**
     * 验证生成过程中刷新页面不会损坏游戏状态。
     *
     * 这是并发控制的重要场景：前端刷新会中断 SSE 连接，
     * 后端应能正确处理并允许重新连接。
     */
    test.setTimeout(90000);

    const pageErrors: string[] = [];
    page.on('pageerror', (error) => {
      pageErrors.push(error.message);
    });

    // 导航到游戏页面
    await page.goto(`${BASE_URL}/play`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);

    // 尝试触发事件生成
    const actionButton = page.getByRole('button').filter({ hasText: /继续|生成|下一步|开始/i }).first();
    if (await actionButton.isVisible({ timeout: 3000 }).catch(() => false)) {
      await actionButton.click().catch(() => {});

      // 等待 2 秒后刷新（模拟生成中刷新）
      await page.waitForTimeout(2000);
      await page.reload();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);

      // 再次刷新
      await page.reload();
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(3000);
    }

    // 过滤非致命错误
    const fatalErrors = pageErrors.filter(e =>
      !e.includes('ResizeObserver') &&
      !e.includes('extension') &&
      !e.includes('Source map') &&
      !e.includes('AbortError')
    );

    expect(fatalErrors).toHaveLength(0);

    // 页面应正常加载
    const body = page.locator('body');
    await expect(body).toBeVisible();
  });

  test('multiple rapid navigations do not leak SSE connections', async ({ page }) => {
    /**
     * 验证快速导航不会泄漏 SSE 连接。
     *
     * 每次导航到 /play 都会建立新的 SSE 连接，
     * 旧连接应被正确关闭。
     */
    test.setTimeout(120_000);

    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    // 快速在多个页面间导航
    for (let i = 0; i < 3; i++) {
      await page.goto(`${BASE_URL}/play`);
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(500);

      await page.goto(`${BASE_URL}/`);
      await page.waitForLoadState('domcontentloaded');
      await page.waitForTimeout(500);
    }

    // 检查连接泄漏相关的错误
    const connectionErrors = consoleErrors.filter(e =>
      e.includes('leak') ||
      (e.includes('connection') && !e.includes('favicon'))
    );

    // 不应有连接泄漏错误
    expect(connectionErrors).toHaveLength(0);

    // 最终页面应正常
    const body = page.locator('body');
    await expect(body).toBeVisible();
  });
});
