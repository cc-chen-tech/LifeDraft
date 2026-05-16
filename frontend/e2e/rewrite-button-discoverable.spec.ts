/**
 * Rewrite Button Discoverability E2E Test
 *
 * 验证改写入口从收起态移入 ChatBar 展开面板，并打开内联 Sheet。
 */

import { test, expect } from '@playwright/test';
import { ensureAuthenticated } from './helpers/auth';

test.describe('Rewrite Button Discoverability', () => {
  test('collapsed chat bar has no standalone rewrite button and expanded chat opens inline rewrite sheet', async ({ page, context }) => {
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

    await page.setViewportSize({ width: 390, height: 844 });

    await expect(page.locator('[data-testid="chat-bar-launcher"] [data-testid="rewrite-button"]')).toHaveCount(0);
    await page.getByLabel('打开聊天').click();

    const rewriteButton = page.locator('[data-testid="chat-bar-panel"] [data-testid="rewrite-button"]');
    await expect(rewriteButton).toBeVisible({ timeout: 10000 });
    await rewriteButton.click();

    const rewriteSheet = page.locator('[data-testid="inline-rewrite-sheet"]');
    await expect(rewriteSheet).toBeVisible({ timeout: 10000 });
    await expect(rewriteSheet.getByPlaceholder(/描述你想要的修改/)).toBeVisible();
    await expect(rewriteSheet.getByRole('button', { name: '改写故事' })).toBeVisible();
  });
});
