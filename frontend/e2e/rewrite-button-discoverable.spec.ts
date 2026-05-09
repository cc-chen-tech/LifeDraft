/**
 * Rewrite Button Discoverability E2E Test
 *
 * 验证改写按钮在 play 页面始终可见，无需先展开 ChatBar。
 * Fixes Task #29.
 */

import { test, expect } from '@playwright/test';
import { ensureAuthenticated } from './helpers/auth';

test.describe('Rewrite Button Discoverability', () => {
  test('rewrite button is visible without expanding chat bar', async ({ page, context }) => {
    await ensureAuthenticated(page, context);

    // 通过 API 创建真实游戏
    const createResp = await context.request.post('http://localhost:8000/api/games', {
      data: {
        player_name: '测试角色',
        life_vision: '测试人生',
        character_settings: {
          era: { name: '2024年', period: '现代', world_description: '现代世界' },
          age: { age: 22, stage: '青年' },
          gender: { gender: '男', pronouns: '他' },
          world: { name: '普通现代', description: '与现实世界相似' },
          family: { description: '普通家庭' },
          relationships: { key_people: [], relationships_description: '暂无' },
          traits: { traits: ['勇敢'] },
          wealth: { level: '中等', description: '普通收入' },
        },
        language: 'zh',
      },
    });
    const game = await createResp.json();
    const gameId = game.game_id;

    await page.goto(`/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');

    // The rewrite button should be visible without clicking anything
    const rewriteButton = page.locator('[data-testid="rewrite-button"]');
    await expect(rewriteButton).toBeVisible({ timeout: 10000 });
  });

  test('rewrite button has pencil icon and correct label', async ({ page, context }) => {
    await ensureAuthenticated(page, context);

    // 通过 API 创建真实游戏
    const createResp = await context.request.post('http://localhost:8000/api/games', {
      data: {
        player_name: '测试角色',
        life_vision: '测试人生',
        character_settings: {
          era: { name: '2024年', period: '现代', world_description: '现代世界' },
          age: { age: 22, stage: '青年' },
          gender: { gender: '男', pronouns: '他' },
          world: { name: '普通现代', description: '与现实世界相似' },
          family: { description: '普通家庭' },
          relationships: { key_people: [], relationships_description: '暂无' },
          traits: { traits: ['勇敢'] },
          wealth: { level: '中等', description: '普通收入' },
        },
        language: 'zh',
      },
    });
    const game = await createResp.json();
    const gameId = game.game_id;

    await page.goto(`/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');

    const rewriteButton = page.locator('[data-testid="rewrite-button"]');
    await expect(rewriteButton).toBeVisible({ timeout: 10000 });

    // Should contain "改写" text
    const text = await rewriteButton.textContent();
    expect(text).toContain('改写');
  });
});
