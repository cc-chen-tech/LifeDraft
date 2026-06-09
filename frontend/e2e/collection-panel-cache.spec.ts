/**
 * 收集面板缓存优化 E2E 测试
 *
 * 测试前端缓存和后端异步化优化后的用户交互流程：
 * 1. 打开收集面板 → 正常加载
 * 2. 关闭后重新打开 → 快速显示（缓存生效）
 * 3. 生成图片后 → 收集面板显示最新数据
 */

import { test, expect } from '@playwright/test';
import { ensureActiveGame } from './helpers/auth';

// 打开收集面板的辅助函数
async function openCollectionPanel(page: import('@playwright/test').Page) {
  const collectionButton = page.getByRole('button', { name: '收集' });
  await expect(collectionButton).toBeVisible({ timeout: 15000 });
  await collectionButton.click();
  await expect(page.locator('text=人物、物品和标志物收集记录')).toBeVisible({ timeout: 5000 });
}

function collectionDialog(page: import('@playwright/test').Page) {
  return page.getByRole('dialog', { name: '收集' });
}

// 关闭收集面板的辅助函数
async function closeCollectionPanel(page: import('@playwright/test').Page) {
  const closeButton = page.locator('button:has-text("Close"), button[aria-label="关闭"]').first();
  if (await closeButton.isVisible().catch(() => false)) {
    await closeButton.click();
    await page.waitForTimeout(300);
  }
}

test.describe('收集面板缓存优化', () => {
  test.beforeEach(async ({ page, context }) => {
    await ensureActiveGame(page, context, { player_name: '缓存测试角色' });
  });

  test('收集面板首次打开正常加载', async ({ page }) => {
    await page.goto('/play');
    await page.waitForLoadState('domcontentloaded');

    await openCollectionPanel(page);

    // 验证面板内容加载完成
    await expect(page.locator('text=人物、物品和标志物收集记录')).toBeVisible();
    await expect(page.getByText(/人物.*\(/)).toBeVisible();
  });

  test('收集面板关闭后重新打开应快速显示', async ({ page }) => {
    await page.goto('/play');
    await page.waitForLoadState('domcontentloaded');

    // 第一次打开
    await openCollectionPanel(page);
    await expect(
      collectionDialog(page).getByRole('button', { name: /缓存测试角色.*主角/ })
    ).toBeVisible();

    // 关闭面板
    await closeCollectionPanel(page);

    // 记录重新打开的时间
    const startTime = Date.now();

    // 重新打开
    await openCollectionPanel(page);

    const openTime = Date.now() - startTime;

    // 缓存生效时应该几乎瞬间显示（小于 1 秒）
    expect(openTime).toBeLessThan(1000);

    // 内容应该仍然正确显示
    await expect(page.locator('text=人物、物品和标志物收集记录')).toBeVisible();
  });

  test('收集面板显示分类标签和主角信息', async ({ page }) => {
    await page.goto('/play');
    await page.waitForLoadState('domcontentloaded');

    await openCollectionPanel(page);

    // 应有人物、物品、标志物三个分类标签
    await expect(page.getByText(/人物.*\(/)).toBeVisible();
    await expect(page.getByText(/物品.*\(/)).toBeVisible();
    await expect(page.getByText(/标志物.*\(/)).toBeVisible();

    // 应显示主角
    const collection = collectionDialog(page);
    await expect(collection.getByRole('button', { name: /缓存测试角色.*主角/ })).toBeVisible();
    await expect(collection.getByText('主角')).toBeVisible();
  });

  test('切换标签页不触发新的网络请求', async ({ page }) => {
    await page.goto('/play');
    await page.waitForLoadState('domcontentloaded');

    await openCollectionPanel(page);

    // 获取物品标签
    const itemsTab = page.getByText(/物品.*\(/);
    await expect(itemsTab).toBeVisible();

    // 记录网络请求
    let collectionRequestCount = 0;
    const handler = (request: import('@playwright/test').Request) => {
      if (request.url().includes('/api/collection/')) {
        collectionRequestCount++;
      }
    };
    page.on('request', handler);

    // 点击物品标签
    await itemsTab.click();
    await page.waitForTimeout(300);

    // 点击标志物标签
    const landmarksTab = page.getByText(/标志物.*\(/);
    await landmarksTab.click();
    await page.waitForTimeout(300);

    // 切回人物标签
    const charactersTab = page.getByText(/人物.*\(/);
    await charactersTab.click();
    await page.waitForTimeout(300);

    page.off('request', handler);

    // 标签切换不应触发新的 collection API 请求
    // （注意：首次打开已经发过一次请求）
    expect(collectionRequestCount).toBe(0);
  });

  test('历史回顾与收集面板不能同时打开', async ({ page }) => {
    await page.goto('/play');
    await page.waitForLoadState('domcontentloaded');

    const historyButton = page.getByRole('button', { name: '历史回顾' });
    const collectionButton = page.getByRole('button', { name: '收集' });
    const historyDialog = page.getByRole('dialog', { name: '历史回顾' });
    const collectionDialog = page.getByRole('dialog', { name: '收集' });

    await historyButton.click();
    await expect(historyDialog).toBeVisible({ timeout: 10000 });

    await collectionButton.click();
    await expect(collectionDialog).toBeVisible({ timeout: 10000 });
    await expect(historyDialog).not.toBeVisible();
  });
});
