/**
 * Rewrite Button Discoverability E2E Test
 *
 * 验证改写入口在 ChatBar 收起态可直接发现，并打开内联 Sheet。
 */

import { test, expect, Page } from '@playwright/test';

const chatActionViewports = [
  { name: 'narrow mobile', width: 360, height: 640 },
  { name: 'mobile portrait', width: 390, height: 844 },
  { name: 'tablet portrait', width: 768, height: 1024 },
  { name: 'desktop', width: 1280, height: 720 },
  { name: 'wide desktop', width: 1440, height: 900 },
];

async function seedStoryForRewrite(page: Page): Promise<void> {
  await page.goto('/e2e-regression');
  await page.waitForLoadState('domcontentloaded');
  await expect(page.getByLabel('打开聊天')).toBeVisible();
}

async function expectCollapsedActionsVisible(page: Page): Promise<void> {
  const chatLauncher = page.locator('[data-testid="chat-bar-launcher"]');

  await expect(chatLauncher).toBeVisible({ timeout: 10000 });
  await expect(page.getByRole('button', { name: '重新生成' })).toBeVisible({ timeout: 10000 });
  await expect(page.getByRole('button', { name: '改写' })).toBeVisible({ timeout: 10000 });
  await expect(page.getByRole('button', { name: '总结' })).toBeVisible({ timeout: 10000 });
}

test.describe('Rewrite Button Discoverability', () => {
  test('collapsed chat bar exposes rewrite/regenerate/summary actions and opens inline rewrite sheet', async ({ page }) => {
    await seedStoryForRewrite(page);

    await page.setViewportSize({ width: 390, height: 844 });

    await expectCollapsedActionsVisible(page);
    const rewriteButton = page.locator('[data-testid="chat-bar-launcher"] [data-testid="rewrite-button"]');
    await expect(rewriteButton).toBeEnabled({ timeout: 10000 });
    await rewriteButton.click();

    const rewriteSheet = page.locator('[data-testid="inline-rewrite-sheet"]');
    await expect(rewriteSheet).toBeVisible({ timeout: 10000 });
    await expect(rewriteSheet.getByPlaceholder(/描述你想要的修改/)).toBeVisible();
    await expect(rewriteSheet.getByRole('button', { name: '改写故事' })).toBeVisible();
  });

  test('collapsed summary action opens summary panel without story assistant input', async ({ page }) => {
    await seedStoryForRewrite(page);

    await page.setViewportSize({ width: 390, height: 844 });

    await page.getByRole('button', { name: '总结' }).click();

    await expect(page.locator('[data-testid="life-summary-panel"]')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('[data-testid="chat-bar-panel"]')).not.toBeVisible();
    await expect(page.getByPlaceholder(/向剧情助手提问/)).not.toBeVisible();
  });

  for (const viewport of chatActionViewports) {
    test(`${viewport.name} keeps collapsed chat actions visible and uncovered`, async ({ page }) => {
      await seedStoryForRewrite(page);
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await expectCollapsedActionsVisible(page);
    });
  }
});
