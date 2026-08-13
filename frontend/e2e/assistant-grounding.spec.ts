import { expect, test, type Page } from '@playwright/test';
import { API_URL, ensureAuthenticated } from './helpers/auth';
import { openPlayTools } from './helpers/play-tools';

async function routeActionableGameState(
  page: Page,
  gameId: number,
  createdState: Record<string, unknown>,
): Promise<void> {
  await page.route(`**/api/games/${gameId}`, async (route) => {
    if (route.request().method() !== 'GET') {
      await route.continue();
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ...createdState,
        current_event: {
          event_description: '建筑档案已经整理完毕，接下来可以继续忠实记录这段生活。',
          options: [
            {
              text: '继续忠实记录已经发生的生活',
              effects: {},
              likely_choice: true,
            },
            {
              text: '先核对档案中的人物关系',
              effects: {},
              likely_choice: false,
            },
          ],
        },
      }),
    });
  });
}

test.describe('Read-only grounded story assistant', () => {
  test('unknown people degrade visibly without changing authoritative state', async ({
    page,
    context,
  }) => {
    await ensureAuthenticated(page, context);

    const playerName = `助手事实约束_${Date.now()}`;
    const createResponse = await page.request.post(`${API_URL}/api/games`, {
      data: {
        player_name: playerName,
        life_vision: '忠实记录已经发生的生活',
        character_settings: {
          era: { name: '现代', period: '2026年' },
          age: { age: 31, stage: '青年' },
          background: { occupation: '建筑师' },
          relationships: {
            key_people: [{ name: '苏敏', role: '摄影师', relationship: '好友' }],
          },
        },
        language: 'zh',
      },
    });
    expect(createResponse.status()).toBe(201);
    const created = await createResponse.json();
    const gameId = created.game_id as number;
    await routeActionableGameState(page, gameId, created as Record<string, unknown>);

    let observeChatMutations = false;
    const chatMutationRequests: string[] = [];
    page.on('request', request => {
      if (
        observeChatMutations &&
        request.method() !== 'GET' &&
        /\/api\/games\/\d+\/(?:event|choice|custom-choice|sync)/.test(request.url())
      ) {
        chatMutationRequests.push(`${request.method()} ${request.url()}`);
      }
    });

    await page.goto(`/play?gameId=${gameId}`);
    await page.waitForLoadState('domcontentloaded');
    await expect(
      page.getByRole('button', { name: '选择 1：继续忠实记录已经发生的生活' }),
    ).toBeVisible({ timeout: 20_000 });
    const toolsDialog = await openPlayTools(page);
    await toolsDialog.getByRole('button', { name: '打开剧情助手' }).click();

    const input = page.getByPlaceholder('向剧情助手提问...');
    await expect(input).toBeVisible();
    await input.fill('李华是谁？');

    const beforeResponse = await page.request.get(`${API_URL}/api/games/${gameId}`);
    expect(beforeResponse.ok()).toBe(true);
    const before = await beforeResponse.json();

    const chatResponsePromise = page.waitForResponse(
      response =>
        response.url().endsWith(`/api/games/${gameId}/chat`) &&
        response.request().method() === 'POST',
    );
    observeChatMutations = true;
    await page.getByRole('button', { name: '发送消息' }).click();
    const chatResponse = await chatResponsePromise;
    expect(chatResponse.status()).toBe(200);
    const chatPayload = await chatResponse.json();
    expect(chatPayload.reply).toContain('没有找到');
    expect(chatPayload.reply).toContain('李华');
    await expect(page.locator('[data-testid="chat-bar-panel"]')).toContainText('没有找到');

    const afterResponse = await page.request.get(`${API_URL}/api/games/${gameId}`);
    expect(afterResponse.ok()).toBe(true);
    const after = await afterResponse.json();
    const authoritativeFields = [
      'player_name',
      'life_vision',
      'age',
      'week',
      'current_round',
      'energy',
      'mood',
      'knowledge',
      'wealth',
      'relationships',
      'character_settings',
      'round_history',
      'weekly_summaries',
      'established_facts',
      'continuity_ledger',
    ];
    for (const field of authoritativeFields) {
      expect(after.player_state[field], field).toEqual(before.player_state[field]);
    }
    expect(chatMutationRequests).toEqual([]);
  });
});
