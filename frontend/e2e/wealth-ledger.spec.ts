import { expect, test } from '@playwright/test';
import { API_URL, ensureAuthenticated } from './helpers/auth';

test.describe('Authoritative wealth ledger', () => {
  test('create, late setup, and reload expose one matching balance authority', async ({
    page,
    context,
  }) => {
    await ensureAuthenticated(page, context);

    const createResponse = await context.request.post(`${API_URL}/api/games`, {
      data: {
        player_name: `财富账本_${Date.now()}`,
        life_vision: '让每一笔收支都可核对',
        character_settings: {
          era: { name: '北宋', period: '古代' },
          age: { age: 28, stage: '青年' },
          wealth: {
            wealth_level: '普通',
            starting_wealth: 900,
            currency: '贯',
            currency_name: '贯',
          },
        },
        language: 'zh',
      },
    });
    expect(createResponse.status()).toBe(201);
    const created = await createResponse.json();
    const gameId = created.game_id as number;

    expect(created.player_state.wealth).toBe(900);
    expect(created.player_state.wealth_ledger).toMatchObject({
      version: 1,
      opening_balance: 900,
      balance_snapshot: 900,
      currency_name: '贯',
      transactions: [],
      conflicts: [],
    });

    const patchResponse = await context.request.patch(
      `${API_URL}/api/games/${gameId}/character-settings`,
      {
        data: {
          character_settings: {
            ...created.player_state.character_settings,
            wealth: {
              wealth_level: '小康',
              initial_wealth: '1,200贯',
              currency: '贯',
              currency_name: '贯',
            },
          },
        },
      },
    );
    expect(patchResponse.status()).toBe(200);

    const reloadResponse = await context.request.get(`${API_URL}/api/games/${gameId}`);
    expect(reloadResponse.ok()).toBe(true);
    const reloaded = await reloadResponse.json();
    expect(reloaded.player_state.wealth).toBe(1200);
    expect(reloaded.player_state.wealth_ledger).toMatchObject({
      opening_balance: 1200,
      balance_snapshot: 1200,
      currency_name: '贯',
      transactions: [],
      conflicts: [],
    });
  });
});
