/* eslint-disable @typescript-eslint/no-unused-vars */

/**
 * Full Game Flow E2E Test - 完整游戏流程测试
 *
 * 测试从角色创建到游戏循环的完整流程
 * 捕获所有API调用错误
 */

import { test, expect, Page, BrowserContext } from '@playwright/test';
import { ensureAuthenticated } from './helpers/auth';
import { startNetworkMonitoring, waitForNetworkIdle, formatNetworkErrors } from './helpers/network-monitor';

const BASE_URL = 'http://localhost:3000';

test.describe('Full Game Flow - Complete Journey', () => {
  let context: BrowserContext;
  let page: Page;

  test.beforeAll(async ({ browser }) => {
    context = await browser.newContext();
    page = await context.newPage();

    // 先登录
    await ensureAuthenticated(page, context);
  });

  test.afterAll(async () => {
    await context.close();
  });

  test('1. Create character and start game', async () => {
    const monitor = startNetworkMonitoring(page);

    // 进入创建页面
    await page.goto(`${BASE_URL}/create`);
    await waitForNetworkIdle(page);

    // 填写角色名
    const nameInput = page.getByPlaceholder(/角色名|姓名|Name/i);
    await nameInput.fill('E2E测试角色');
    await page.waitForTimeout(500);

    // 填写人生愿景
    const visionInput = page.getByPlaceholder(/人生愿景|人生方向|Life Vision/i);
    await visionInput.fill('探索世界，寻找真理');

    // 等待AI生成完成
    await page.waitForTimeout(3000);
    await waitForNetworkIdle(page);

    // 检查是否有网络错误
    const errors = monitor.get4xxErrors();
    if (errors.length > 0) {
      console.log(formatNetworkErrors(errors));
    }

    // 404错误会导致测试失败
    expect(monitor.get404Errors()).toHaveLength(0);
  });

  test('2. Navigate through all character creation steps', async () => {
    const monitor = startNetworkMonitoring(page);

    await page.goto(`${BASE_URL}/create`);
    await waitForNetworkIdle(page);

    // 填写角色名
    const nameInput = page.getByPlaceholder(/角色名|姓名|Name/i);
    await nameInput.fill('E2E测试角色');
    await page.waitForTimeout(1000);

    // 点击下一步遍历所有步骤
    const maxSteps = 5;
    for (let i = 0; i < maxSteps; i++) {
      const nextButton = page.getByRole('button', { name: /下一步|Next/i }).first();

      if (await nextButton.isVisible().catch(() => false)) {
        const isEnabled = await nextButton.isEnabled().catch(() => false);

        if (isEnabled) {
          monitor.clear();
          await nextButton.click();
          await page.waitForTimeout(1000);
          await waitForNetworkIdle(page);

          // 检查每一步是否有API错误
          const errors = monitor.get4xxErrors();
          if (errors.length > 0) {
            console.error(`Step ${i + 1} errors:`, formatNetworkErrors(errors));
          }
          expect(monitor.get404Errors()).toHaveLength(0);
        }
      }
    }
  });

  test('3. Complete character creation and start game', async () => {
    const monitor = startNetworkMonitoring(page);

    await page.goto(`${BASE_URL}/create`);
    await waitForNetworkIdle(page);

    // 填写必要信息
    await page.getByPlaceholder(/角色名|姓名|Name/i).fill('E2E测试角色');
    await page.waitForTimeout(2000);

    // 点击开始游戏按钮（如果在最后一步）
    const startButton = page.getByRole('button', { name: /开始游戏|Start Game|生成角色/i });

    if (await startButton.isVisible().catch(() => false)) {
      monitor.clear();
      await startButton.click();
      await page.waitForTimeout(2000);
      await waitForNetworkIdle(page);

      // 检查是否有API错误
      const errors = monitor.get4xxErrors();
      if (errors.length > 0) {
        console.error('Start game errors:', formatNetworkErrors(errors));
      }
      expect(monitor.get404Errors()).toHaveLength(0);

      // 应该跳转到游戏页面
      await expect(page).toHaveURL(/\/play/);
    }
  });
});

test.describe('Full Game Flow - Game Loop', () => {
  test.beforeEach(async ({ page, context }) => {
    await ensureAuthenticated(page, context);
  });

  test('4. Load play page and verify game state', async ({ page }) => {
    const monitor = startNetworkMonitoring(page);

    await page.goto(`${BASE_URL}/play`);
    await waitForNetworkIdle(page);
    await page.waitForTimeout(2000);

    // 检查是否有404错误
    const notFoundErrors = monitor.get404Errors();

    // 过滤掉预期的404：
    // 1. 游戏不存在的404是正常的（用户还没有创建游戏）
    // 2. 路由不存在的404才是问题
    const unexpected404 = notFoundErrors.filter(e => {
      // 如果URL包含/games/且返回404，这是资源不存在（正常）
      // 如果URL不包含/games/，可能是路由问题
      const isResourceNotFound = e.url.includes('/games/') &&
        (e.body?.includes('Game not found') || e.body?.includes('not found'));
      return !isResourceNotFound;
    });

    if (unexpected404.length > 0) {
      console.error('Unexpected 404 errors:', formatNetworkErrors(unexpected404));
    }

    // 只检查路由级别的404（前端/后端路径不匹配）
    const route404 = unexpected404.filter(e =>
      !e.url.includes('/games/') // 游戏API的404是资源问题，不是路由问题
    );

    expect(route404).toHaveLength(0);
  });

  test('5. Verify all game page API endpoints', async ({ page }) => {
    const monitor = startNetworkMonitoring(page);

    // 访问游戏页面
    await page.goto(`${BASE_URL}/play`);
    await waitForNetworkIdle(page);

    // 如果有游戏，尝试打开历史面板
    const historyButton = page.locator('header button').first();
    if (await historyButton.isVisible().catch(() => false)) {
      monitor.clear();
      await historyButton.click();
      await page.waitForTimeout(1000);

      const errors = monitor.get4xxErrors();
      if (errors.length > 0) {
        console.error('History panel errors:', formatNetworkErrors(errors));
      }
      expect(monitor.get404Errors()).toHaveLength(0);
    }
  });
});

test.describe('Full Game Flow - Save and Load', () => {
  test.beforeEach(async ({ page, context }) => {
    await ensureAuthenticated(page, context);
  });

  test('6. Save game flow', async ({ page }) => {
    const monitor = startNetworkMonitoring(page);

    // 进入游戏页面
    await page.goto(`${BASE_URL}/play`);
    await waitForNetworkIdle(page);

    // 查找保存按钮
    const saveButton = page.getByRole('button', { name: /保存|Save/i }).first();

    if (await saveButton.isVisible().catch(() => false)) {
      monitor.clear();
      await saveButton.click();
      await page.waitForTimeout(2000);
      await waitForNetworkIdle(page);

      const errors = monitor.get4xxErrors();
      if (errors.length > 0) {
        console.error('Save game errors:', formatNetworkErrors(errors));
      }
      expect(monitor.get404Errors()).toHaveLength(0);
    }
  });

  test('7. Load game from saves page', async ({ page }) => {
    const monitor = startNetworkMonitoring(page);

    // 进入存档页面
    await page.goto(`${BASE_URL}/saves`);
    await waitForNetworkIdle(page);
    await page.waitForTimeout(2000);

    const errors = monitor.get4xxErrors();
    if (errors.length > 0) {
      console.error('Saves page errors:', formatNetworkErrors(errors));
    }

    // 存档列表API不应该返回404
    const saveList404 = errors.filter(e =>
      e.url.includes('/games') && e.status === 404
    );
    expect(saveList404).toHaveLength(0);
  });
});

test.describe('Full Game Flow - Image Generation', () => {
  test.beforeEach(async ({ page, context }) => {
    await ensureAuthenticated(page, context);
  });

  test('8. Character image generation endpoints', async ({ page }) => {
    const monitor = startNetworkMonitoring(page);

    // 进入创建页面（有图片生成）
    await page.goto(`${BASE_URL}/create`);
    await waitForNetworkIdle(page);

    // 填写角色名触发图片生成
    await page.getByPlaceholder(/角色名|姓名|Name/i).fill('ImageTest角色');
    await page.waitForTimeout(3000);
    await waitForNetworkIdle(page);

    const errors = monitor.get4xxErrors();

    // 检查图片相关API
    const imageErrors = errors.filter(e =>
      e.url.includes('/images/') || e.url.includes('/image')
    );

    if (imageErrors.length > 0) {
      console.error('Image API errors:', formatNetworkErrors(imageErrors));
    }

    expect(imageErrors).toHaveLength(0);
  });

  test('9. Round scene image endpoints', async ({ page }) => {
    const monitor = startNetworkMonitoring(page);

    // 进入游戏页面
    await page.goto(`${BASE_URL}/play`);
    await waitForNetworkIdle(page);
    await page.waitForTimeout(2000);

    const errors = monitor.get4xxErrors();

    // 检查场景图片API（已修复的端点）
    const sceneErrors = errors.filter(e =>
      e.url.includes('/images/scene/') || e.url.includes('/round-scenes/')
    );

    if (sceneErrors.length > 0) {
      console.error('Scene image errors:', formatNetworkErrors(sceneErrors));
    }

    expect(sceneErrors).toHaveLength(0);
  });
});

test.describe('Full Game Flow - Console Error Monitoring', () => {
  test.beforeEach(async ({ page, context }) => {
    await ensureAuthenticated(page, context);
  });

  test('10. Monitor console errors during gameplay', async ({ page }) => {
    const consoleErrors: string[] = [];
    const consoleWarnings: string[] = [];

    page.on('console', msg => {
      const text = msg.text();
      if (msg.type() === 'error') {
        consoleErrors.push(text);
        console.error('[Console Error]', text);
      } else if (msg.type() === 'warning') {
        consoleWarnings.push(text);
      }
    });

    page.on('pageerror', error => {
      consoleErrors.push(error.message);
      console.error('[Page Error]', error.message);
    });

    // 执行一系列操作
    await page.goto(`${BASE_URL}/`);
    await page.waitForTimeout(1000);

    await page.goto(`${BASE_URL}/create`);
    await page.waitForTimeout(1000);

    await page.goto(`${BASE_URL}/saves`);
    await page.waitForTimeout(1000);

    // 过滤掉已知的非关键错误
    const criticalErrors = consoleErrors.filter(e =>
      !e.includes('favicon') &&
      !e.includes('extension') &&
      !e.includes('SourceMap') &&
      !e.includes('ResizeObserver')
    );

    if (criticalErrors.length > 0) {
      console.error('Critical console errors:', criticalErrors);
    }

    // 控制台不应该有API相关的错误
    const apiErrors = criticalErrors.filter(e =>
      e.includes('404') ||
      e.includes('500') ||
      e.includes('API') ||
      e.includes('api')
    );

    expect(apiErrors).toHaveLength(0);
  });
});
