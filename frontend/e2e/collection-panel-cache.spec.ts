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
    const collection = collectionDialog(page);
    const itemsTab = collection.getByTestId('collection-tab-items');
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
    const landmarksTab = collection.getByTestId('collection-tab-landmarks');
    await landmarksTab.click();
    await page.waitForTimeout(300);

    // 切回人物标签
    const charactersTab = collection.getByTestId('collection-tab-characters');
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
    await expect(collectionDialog).not.toBeVisible();

    await collectionButton.click();
    await expect(collectionDialog).toBeVisible({ timeout: 10000 });
    await expect(historyDialog).not.toBeVisible();

    await historyButton.click();
    await expect(historyDialog).toBeVisible({ timeout: 10000 });
    await expect(collectionDialog).not.toBeVisible();
  });

});

test.describe('真实游戏页收集自动识别', () => {
  test('打开收集面板会自动补入当前故事识别出的人物', async ({ page }) => {
    const gameId = 777001;
    let collectionDetailsCalls = 0;
    let recognizeCalled = false;
    let addEntitiesCalled = false;
    const gameState = {
      game_id: gameId,
      player_state: {
        player_name: '自动收集测试角色',
        age: 28,
        week: 1,
        current_round: 1,
        energy: 70,
        mood: 60,
        knowledge: 50,
        wealth: 10000,
        character_settings: {
          era: { name: '现代', period: '2020年代' },
          age: { age: 28, stage: '青年' },
          background: { occupation: '产品经理' },
          personality: { traits: ['谨慎', '敏锐'] },
        },
      },
      progress: { week: 1, current_round: 1, total_rounds: 3 },
      round_info: { week: 1, current_round: 1, total_rounds: 3 },
      current_event: {
        event_description: '赵掌柜递来账册，要求主角立刻核对。',
        options: [{ text: '追问账册来源' }],
      },
      constraint_level: 'expert',
    };

    const initialCollection = {
      game_id: gameId,
      characters: [
        {
          name: '自动收集测试角色',
          role: '主角',
          description: '当前游戏主角。',
          affinity: 100,
          age: null,
          gender: null,
          occupation: '产品经理',
          personality_traits: [],
          image_url: null,
          image_generated: false,
          description_generated: true,
        },
      ],
      items: [],
      landmarks: [],
      total_characters: 1,
      total_items: 0,
      total_landmarks: 0,
    };
    const refreshedCollection = {
      ...initialCollection,
      characters: [
        ...initialCollection.characters,
        {
          name: '赵掌柜',
          role: '故事人物',
          description: '刚刚在当前故事中出现并推动剧情的人物。',
          affinity: 50,
          age: null,
          gender: null,
          occupation: '账房',
          personality_traits: [],
          image_url: null,
          image_generated: false,
          description_generated: true,
        },
      ],
      total_characters: 2,
    };

    await page.route('**/api/auth/me', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          user_id: 1,
          public_id: 'AUTOE2E',
          display_name: 'Auto Collection E2E',
          private_id: 'AUTO-COLLECTION-E2E',
        }),
      });
    });
    await page.route('**/api/games/active', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(gameState) });
    });
    await page.route(`**/api/games/${gameId}`, async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(gameState) });
    });
    await page.route(`**/api/images/scenes/${gameId}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ scenes: [] }),
      });
    });
    await page.route(`**/api/images/scene/${gameId}/1**`, async (route) => {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'No scene image in this fixture' }),
      });
    });
    await page.route('**/api/voice-reading/settings', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          tts_provider: 'browser',
          backend_audio_enabled: false,
          available_voices: [],
        }),
      });
    });
    await page.route('**/api/music/recommend', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ songs: [] }),
      });
    });
    await page.route(`**/api/collection/${gameId}/details`, async (route) => {
      collectionDetailsCalls += 1;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(collectionDetailsCalls === 1 ? initialCollection : refreshedCollection),
      });
    });
    await page.route(`**/api/collection/${gameId}/recognize-entities`, async (route) => {
      recognizeCalled = true;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          characters: [
            {
              name: '赵掌柜',
              description: '刚刚在当前故事中出现并推动剧情的人物。',
              role: '故事人物',
              importance: 'normal',
              appear_count: 1,
              appear_contexts: ['赵掌柜递来账册，要求主角立刻核对。'],
            },
          ],
          items: [],
          landmarks: [],
        }),
      });
    });
    await page.route(`**/api/collection/${gameId}/add-entities`, async (route) => {
      addEntitiesCalled = true;
      const requestBody = route.request().postData() || '';
      expect(requestBody).toContain('赵掌柜');
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          message: '成功添加 0 个物品, 1 个人物, 0 个地点',
          added_items: [],
          added_characters: ['赵掌柜'],
          added_landmarks: [],
        }),
      });
    });

    await page.goto(`/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');

    await openCollectionPanel(page);

    const collection = collectionDialog(page);
    await expect(collection.getByRole('button', { name: /赵掌柜.*故事人物/ })).toBeVisible({
      timeout: 10000,
    });
    await expect(collection.getByText(/人物 \(2\)/)).toBeVisible();
    expect(recognizeCalled).toBe(true);
    expect(addEntitiesCalled).toBe(true);
    expect(collectionDetailsCalls).toBeGreaterThanOrEqual(2);
  });
});
