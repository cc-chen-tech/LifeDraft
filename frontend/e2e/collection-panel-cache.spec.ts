/**
 * 收集面板缓存优化 E2E 测试
 *
 * 测试前端缓存和后端异步化优化后的用户交互流程：
 * 1. 打开收集面板 → 正常加载
 * 2. 关闭后重新打开 → 快速显示（缓存生效）
 * 3. 生成图片后 → 收集面板显示最新数据
 */

import { test, expect, type Locator, type Page } from '@playwright/test';
import { ensureActiveGame } from './helpers/auth';
import { openPlayTools } from './helpers/play-tools';

const CACHED_COLLECTION_OPEN_MAX_MS = 1500;

function collectionDialog(page: Page) {
  return page.getByRole('dialog', { name: '收集', exact: true });
}

function historyDialog(page: Page) {
  return page.getByRole('dialog', { name: '历史回顾', exact: true });
}

// 从当前 viewport 的真实工具入口打开收集面板。
async function openCollectionPanel(page: Page): Promise<Locator> {
  const tools = await openPlayTools(page);
  await tools.getByRole('button', { name: '打开收集', exact: true }).click();

  const dialog = collectionDialog(page);
  await expect(dialog).toBeVisible({ timeout: 5000 });
  await expect(
    dialog.getByText('人物、物品和标志物收集记录', { exact: true })
  ).toBeVisible({ timeout: 5000 });
  return dialog;
}

async function closeCollectionPanel(page: Page) {
  const dialog = collectionDialog(page);
  await dialog.getByRole('button', { name: '关闭收集', exact: true }).click();
  await expect(dialog).not.toBeVisible({ timeout: 3000 });
}

async function openHistoryPanel(page: Page): Promise<Locator> {
  const tools = await openPlayTools(page);
  await tools.getByRole('button', { name: '打开历史回顾', exact: true }).click();

  const dialog = historyDialog(page);
  await expect(dialog).toBeVisible({ timeout: 10000 });
  return dialog;
}

async function closeHistoryPanel(page: Page) {
  const dialog = historyDialog(page);
  await dialog.getByRole('button', { name: '关闭历史回顾', exact: true }).click();
  await expect(dialog).not.toBeVisible({ timeout: 3000 });
}

test.describe('收集面板缓存优化', () => {
  test.beforeEach(async ({ page, context }) => {
    await ensureActiveGame(page, context, { player_name: '缓存测试角色' });
  });

  test('收集面板首次打开正常加载', async ({ page }) => {
    await page.goto('/play');
    await page.waitForLoadState('domcontentloaded');

    const collection = await openCollectionPanel(page);

    // 验证面板内容加载完成
    await expect(
      collection.getByText('人物、物品和标志物收集记录', { exact: true })
    ).toBeVisible();
    await expect(collection.getByRole('tab', { name: /人物.*\(/ })).toBeVisible();
  });

  test('收集面板关闭后重新打开应快速显示', async ({ page }) => {
    await page.goto('/play');
    await page.waitForLoadState('domcontentloaded');

    // 第一次打开
    const initialCollection = await openCollectionPanel(page);
    const initialPlayerRow = initialCollection.getByRole('button', {
      name: '查看人物：缓存测试角色',
      exact: true,
    });
    await expect(initialPlayerRow).toBeVisible();
    await expect(initialPlayerRow.getByText('主角', { exact: true })).toBeVisible();

    // 关闭面板
    await closeCollectionPanel(page);

    // 工具面板不是收集缓存的一部分；只计时从收集动作到缓存内容可见。
    const tools = await openPlayTools(page);
    const startTime = Date.now();
    await tools.getByRole('button', { name: '打开收集', exact: true }).click();

    const collection = collectionDialog(page);
    await expect(collection).toBeVisible({ timeout: CACHED_COLLECTION_OPEN_MAX_MS });
    const cachedPlayerRow = collection.getByRole('button', {
      name: '查看人物：缓存测试角色',
      exact: true,
    });
    await expect(cachedPlayerRow).toBeVisible({ timeout: CACHED_COLLECTION_OPEN_MAX_MS });
    await expect(cachedPlayerRow.getByText('主角', { exact: true })).toBeVisible();

    const openTime = Date.now() - startTime;

    // 保留缓存性能预算，同时为 CI 调度抖动预留少量余量。
    expect(openTime).toBeLessThan(CACHED_COLLECTION_OPEN_MAX_MS);

    // 内容应该仍然正确显示
    await expect(
      collection.getByText('人物、物品和标志物收集记录', { exact: true })
    ).toBeVisible({ timeout: 5000 });
  });

  test('收集面板显示分类标签和主角信息', async ({ page }) => {
    await page.goto('/play');
    await page.waitForLoadState('domcontentloaded');

    const collection = await openCollectionPanel(page);

    // 应有人物、物品、标志物三个分类标签
    await expect(collection.getByRole('tab', { name: /人物.*\(/ })).toBeVisible();
    await expect(collection.getByRole('tab', { name: /物品.*\(/ })).toBeVisible();
    await expect(collection.getByRole('tab', { name: /标志物.*\(/ })).toBeVisible();

    // 应显示主角
    const playerRow = collection.getByRole('button', {
      name: '查看人物：缓存测试角色',
      exact: true,
    });
    await expect(playerRow).toBeVisible();
    await expect(playerRow.getByText('主角', { exact: true })).toBeVisible();
  });

  test('切换标签页不触发新的网络请求', async ({ page }) => {
    await page.goto('/play');
    await page.waitForLoadState('domcontentloaded');

    const collection = await openCollectionPanel(page);

    // 获取物品标签
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

  test('历史回顾与收集面板按用户路径保持单一可见层', async ({ page }) => {
    await page.goto('/play');
    await page.waitForLoadState('domcontentloaded');

    const history = historyDialog(page);
    const collection = collectionDialog(page);

    await openHistoryPanel(page);
    await expect(history).toBeVisible();
    await expect(collection).not.toBeVisible();

    await closeHistoryPanel(page);
    await openCollectionPanel(page);
    await expect(collection).toBeVisible();
    await expect(history).not.toBeVisible();

    await closeCollectionPanel(page);
    await openHistoryPanel(page);
    await expect(history).toBeVisible();
    await expect(collection).not.toBeVisible();
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

    const collection = await openCollectionPanel(page);

    const recognizedCharacterRow = collection.getByRole('button', {
      name: '查看人物：赵掌柜',
      exact: true,
    });
    await expect(recognizedCharacterRow).toBeVisible({ timeout: 10000 });
    await expect(
      recognizedCharacterRow.getByText('故事人物', { exact: true })
    ).toBeVisible();
    await expect(collection.getByText(/人物 \(2\)/)).toBeVisible();
    expect(recognizeCalled).toBe(true);
    expect(addEntitiesCalled).toBe(true);
    expect(collectionDetailsCalls).toBeGreaterThanOrEqual(2);
  });
});
