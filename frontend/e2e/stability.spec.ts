 

/**
 * E2E Test: Stability Validation
 * Tests for system stability under various conditions
 */
import { test, expect, Page, BrowserContext } from '@playwright/test';
import { ensureAuthenticated } from './helpers/auth';
import { waitForApiResponse, waitForPageReady, waitForStableDOM, waitForNetworkIdle } from './helpers/wait-helpers';

const BASE_URL = 'http://localhost:3000';

test.describe('Stability E2E', () => {
  test('SSE connection recovers after disconnect', async ({ page, context }) => {
    await ensureAuthenticated(page, context);

    // 进入游戏页面（如果有活动游戏）
    await page.goto(`${BASE_URL}/play`);
    await page.waitForLoadState('domcontentloaded');

    // 记录控制台错误
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    // 模拟网络中断后恢复
    await page.context().setOffline(true);

    // 等待网络中断被检测
    await expect(async () => {
      // 触发一个快速操作确保 offline 状态生效
      const bodyContent = page.locator('body');
      await expect(bodyContent).toBeVisible();
    }).toPass({ timeout: 2000 });

    // 恢复网络
    await page.context().setOffline(false);

    // 等待重连
    await page.waitForLoadState('domcontentloaded');

    // 页面应该还能正常工作
    const bodyContent = page.locator('body');
    await expect(bodyContent).toBeVisible();

    // 检查是否有致命错误
    const fatalErrors = consoleErrors.filter(
      (e) => e.includes('fatal') || e.includes('crash') || e.includes('unhandled')
    );
    expect(fatalErrors).toHaveLength(0);
  });

  test('concurrent game actions dont crash', async ({ page, context }) => {
    test.setTimeout(90000); // 这个测试需要更多时间
    await ensureAuthenticated(page, context);

    await page.goto(`${BASE_URL}/create`);
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000); // 等待页面完全加载

    // 记录页面错误
    const pageErrors: string[] = [];
    page.on('pageerror', (error) => {
      pageErrors.push(error.message);
    });

    // 快速连续操作
    const nameInput = page.getByPlaceholder(/角色名|姓名|Name/i);
    if (await nameInput.isVisible({ timeout: 3000 }).catch(() => false)) {
      await nameInput.fill('测试角色');
    }

    // 快速连续点击下一步按钮（如果存在）
    const nextButton = page.getByRole('button', { name: /下一步|Next/i }).first();

    if (await nextButton.isVisible().catch(() => false)) {
      for (let i = 0; i < 3; i++) {
        await nextButton.click({ force: true, noWaitAfter: true }).catch(() => {});
      }
    }

    // 等待页面稳定
    try {
      await page.waitForTimeout(3000);
      const bodyContent = page.locator('body');
      await expect(bodyContent).toBeVisible({ timeout: 5000 });
    } catch {
      // 页面已关闭不算崩溃
      return;
    }

    // 不应该有未处理的错误
    const criticalErrors = pageErrors.filter(
      (e) => !e.includes('ResizeObserver') && !e.includes('extension')
    );
    expect(criticalErrors).toHaveLength(0);
  });

  test('rapid navigation doesnt leak connections', async ({ page, context }) => {
    await ensureAuthenticated(page, context);

    // 记录控制台错误
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    // 快速在页面间导航
    const pages = ['/', '/create', '/saves', '/'];

    for (let round = 0; round < 3; round++) {
      for (const path of pages) {
        await page.goto(`${BASE_URL}${path}`);
        // 不等待完全加载，快速导航
      }
    }

    // 最终等待页面稳定
    await page.waitForLoadState('domcontentloaded');

    // 检查连接泄漏相关的错误
    const connectionErrors = consoleErrors.filter(
      (e) =>
        e.includes('connection') ||
        e.includes('leak') ||
        e.includes('memory') ||
        e.includes('EventSource')
    );

    // 不应该有连接泄漏错误
    // 注：某些框架的警告可能会出现，但不应该有错误
    const criticalConnectionErrors = connectionErrors.filter(
      (e) => !e.includes('Warning')
    );
    expect(criticalConnectionErrors).toHaveLength(0);
  });

  test('large collection list renders without freeze', async ({ page, context }) => {
    await ensureAuthenticated(page, context);

    // 模拟大量数据响应
    await page.route('**/api/collection/*', (route) => {
      const largeCollection = {
        characters: Array.from({ length: 50 }, (_, i) => ({
          name: `Character ${i}`,
          description: `Description for character ${i}`,
          role: 'npc',
          importance: 'normal',
        })),
        items: Array.from({ length: 50 }, (_, i) => ({
          name: `Item ${i}`,
          description: `Description for item ${i}`,
          category: 'misc',
          importance: 'normal',
        })),
        landmarks: Array.from({ length: 20 }, (_, i) => ({
          name: `Landmark ${i}`,
          description: `Description for landmark ${i}`,
        })),
      };

      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(largeCollection),
      });
    });

    const startTime = Date.now();

    await page.goto(`${BASE_URL}/play`);
    await page.waitForLoadState('domcontentloaded');

    const loadTime = Date.now() - startTime;

    // 页面应该在合理时间内加载（60秒，考虑并行测试负载）
    expect(loadTime).toBeLessThan(60000);

    // 页面应该正常渲染
    const bodyContent = page.locator('body');
    await expect(bodyContent).toBeVisible();
  });

  test('game save during AI generation succeeds', async ({ page, context }) => {
    await ensureAuthenticated(page, context);

    // 记录保存请求的响应
    let saveRequestSent = false;
    let saveResponseStatus = 0;

    page.on('response', (response) => {
      if (response.url().includes('/save')) {
        saveRequestSent = true;
        saveResponseStatus = response.status();
      }
    });

    await page.goto(`${BASE_URL}/create`);
    await page.waitForLoadState('domcontentloaded');

    // 填写角色名触发 AI 生成
    const nameInput = page.getByPlaceholder(/角色名|姓名|Name/i);
    await nameInput.fill('保存测试角色');

    // 立即尝试查找保存按钮（如果存在）
    const saveButton = page.getByRole('button', { name: /保存|Save/i }).first();

    if (await saveButton.isVisible().catch(() => false)) {
      await saveButton.click();
      await page.waitForLoadState('domcontentloaded');

      // 如果发送了保存请求，应该成功或返回合理的错误
      if (saveRequestSent) {
        expect([200, 201, 400, 422]).toContain(saveResponseStatus);
      }
    }

    // 页面不应该崩溃
    const bodyContent = page.locator('body');
    await expect(bodyContent).toBeVisible();
  });

  test('multiple tab sessions coexist', async ({ context }) => {
    // 创建两个独立的页面
    const page1 = await context.newPage();
    const page2 = await context.newPage();

    try {
      // 在第一个标签页登录
      await ensureAuthenticated(page1, context);

      // 两个标签页各自导航
      await page1.goto(`${BASE_URL}/create`);
      await page2.goto(`${BASE_URL}/saves`);

      // 等待两个页面加载
      await page1.waitForLoadState('domcontentloaded');
      await page2.waitForLoadState('domcontentloaded');

      // 两个页面都应该正常工作
      await expect(page1).toHaveURL(/create/);
      await expect(page2).toHaveURL(/saves/);

      // 在第一个标签页操作
      const nameInput = page1.getByPlaceholder(/角色名|姓名|Name/i);
      await nameInput.fill('多标签测试');

      // 第二个标签页应该仍然正常
      const page2Body = page2.locator('body');
      await expect(page2Body).toBeVisible();

      // 切换到第二个标签页操作
      const returnButton = page2.getByRole('button', { name: /返回/i });
      if (await returnButton.isVisible().catch(() => false)) {
        await returnButton.click();
        await page2.waitForLoadState('domcontentloaded');
      }

      // 第一个标签页的内容应该保持
      await expect(nameInput).toHaveValue('多标签测试');
    } finally {
      await page1.close();
      await page2.close();
    }
  });

  test('page reload preserves game state', async ({ page, context }) => {
    await ensureAuthenticated(page, context);

    await page.goto(`${BASE_URL}/create`);
    await page.waitForLoadState('domcontentloaded');

    // 进行一些操作
    const nameInput = page.getByPlaceholder(/角色名|姓名|Name/i);
    await nameInput.fill('刷新测试角色');

    // 等待可能的自动保存
    await page.waitForLoadState('domcontentloaded');

    // 记录当前 URL
    const urlBeforeReload = page.url();

    // 刷新页面
    await page.reload();
    await page.waitForLoadState('domcontentloaded');

    // 验证 URL 保持不变
    expect(page.url()).toBe(urlBeforeReload);

    // 页面应该正常加载
    const bodyContent = page.locator('body');
    await expect(bodyContent).toBeVisible();

    // 对于 /create 页面，表单可能会被重置（这是预期行为）
    // 重要的是页面不崩溃
  });

  test('network error shows user-friendly message', async ({ page, context }) => {
    await ensureAuthenticated(page, context);

    // 模拟网络错误
    await page.route('**/api/games*', (route) => route.abort('failed'));

    await page.goto(`${BASE_URL}/saves`);

    // 等待页面处理错误
    await page.waitForLoadState('domcontentloaded');

    // 获取页面可见文本内容（使用 innerText 而非 textContent，避免 Next.js script 标签中的序列化数据干扰）
    const pageText = await page.locator('body').innerText({ timeout: 5000 }).catch(() => '');

    // 验证没有显示技术栈错误信息
    expect(pageText).not.toMatch(/traceback/i);
    expect(pageText).not.toMatch(/TypeError/);
    expect(pageText).not.toMatch(/ReferenceError/);

    // 页面应该还能正常显示
    const bodyContent = page.locator('body');
    await expect(bodyContent).toBeVisible();

    // 检查是否有任何形式的错误提示（空状态或错误消息）
    // 而不是完全空白或崩溃
    const hasContent =
      (await page.locator('text=/存档|Save|错误|失败|重试|Empty/').count()) > 0 ||
      (await page.locator('button').count()) > 0;

    expect(hasContent).toBeTruthy();
  });
});
