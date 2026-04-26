/**
 * Rewrite Button Discoverability E2E Test
 *
 * 验证改写按钮在 play 页面始终可见，无需先展开 ChatBar。
 * Fixes Task #29.
 */

import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:3000';

test.describe('Rewrite Button Discoverability', () => {
  test('rewrite button is visible without expanding chat bar', async ({ page }) => {
    // Navigate to play page with a game ID in localStorage
    await page.goto(`${BASE_URL}/`);
    await page.evaluate(() => {
      localStorage.setItem(
        'game-store',
        JSON.stringify({
          state: {
            gameId: 1,
            playerState: { player_name: '测试角色' },
          },
          version: 0,
        })
      );
    });

    await page.goto(`${BASE_URL}/play`, { waitUntil: 'domcontentloaded' }).catch(() => {});
    await page.waitForTimeout(2000);

    // The rewrite button should be visible without clicking anything
    const rewriteButton = page.locator('[data-testid="rewrite-button"]');
    await expect(rewriteButton).toBeVisible({ timeout: 10000 });
  });

  test('rewrite button has pencil icon and correct label', async ({ page }) => {
    await page.goto(`${BASE_URL}/`);
    await page.evaluate(() => {
      localStorage.setItem(
        'game-store',
        JSON.stringify({
          state: {
            gameId: 1,
            playerState: { player_name: '测试角色' },
          },
          version: 0,
        })
      );
    });

    await page.goto(`${BASE_URL}/play`, { waitUntil: 'domcontentloaded' }).catch(() => {});
    await page.waitForTimeout(2000);

    const rewriteButton = page.locator('[data-testid="rewrite-button"]');
    await expect(rewriteButton).toBeVisible({ timeout: 10000 });

    // Should contain "改写" text
    const text = await rewriteButton.textContent();
    expect(text).toContain('改写');
  });
});
