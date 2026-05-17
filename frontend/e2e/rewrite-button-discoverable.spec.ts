/**
 * Rewrite Button Discoverability E2E Test
 *
 * 验证改写入口从收起态移入 ChatBar 展开面板，并打开内联 Sheet。
 */

import { test, expect, Page } from '@playwright/test';

async function seedStoryForRewrite(page: Page): Promise<void> {
  await page.goto('/e2e-regression');
  await page.waitForLoadState('domcontentloaded');
  await expect(page.getByLabel('打开聊天')).toBeVisible();
}

test.describe('Rewrite Button Discoverability', () => {
  test('collapsed chat bar has no standalone rewrite button and expanded chat opens inline rewrite sheet', async ({ page }) => {
    await seedStoryForRewrite(page);

    await page.setViewportSize({ width: 390, height: 844 });

    await expect(page.locator('[data-testid="chat-bar-launcher"] [data-testid="rewrite-button"]')).toHaveCount(0);
    await page.getByLabel('打开聊天').click();

    const rewriteButton = page.locator('[data-testid="chat-bar-panel"] [data-testid="rewrite-button"]');
    await expect(rewriteButton).toBeVisible({ timeout: 10000 });
    await expect(rewriteButton).toBeEnabled({ timeout: 10000 });
    await rewriteButton.click();

    const rewriteSheet = page.locator('[data-testid="inline-rewrite-sheet"]');
    await expect(rewriteSheet).toBeVisible({ timeout: 10000 });
    await expect(rewriteSheet.getByPlaceholder(/描述你想要的修改/)).toBeVisible();
    await expect(rewriteSheet.getByRole('button', { name: '改写故事' })).toBeVisible();
  });
});
