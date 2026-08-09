import type { Page } from '@playwright/test';

export const CANONICAL_ENDING_RESPONSE = {
  ending_type: 'balanced',
  ending_name: '平衡人生',
  summary: '她把每一次选择都写进自己的生活，最终带着清醒与温柔抵达终章。',
  achievements: {
    list: [
      {
        id: 'balanced_life',
        name: '平衡人生',
        description: '在变化中守住生活的重心',
        rarity: 'rare',
        dimension: 'trajectory',
        unlocked_at_week: 12,
        icon: '',
      },
    ],
    count: 1,
  },
  life_review: {
    personality_labels: ['沉着的记录者', '关系守护者'],
    key_turning_points: [
      {
        week: 4,
        description: '在一次艰难取舍中决定忠于已经发生的生活。',
        impact_score: 0.82,
      },
    ],
    resource_curves: {
      energy: [100, 92, 86],
      mood: [100, 88, 91],
      knowledge: [50, 62, 76],
      wealth: [10000, 11200, 12400],
    },
    achievement_badge_wall: [
      {
        id: 'balanced_life',
        name: '平衡人生',
        rarity: 'rare',
        unlocked_at_week: 12,
      },
    ],
    relationship_network: {
      nodes: [{ name: '苏敏', affinity: 82 }],
      edges: [],
    },
    life_motto: '把真实的日子，过成自己的答案。',
    play_duration_minutes: 42,
    total_decisions: 12,
    favorite_choice_type: '平衡',
  },
  final_stats: {
    energy: 86,
    mood: 91,
    knowledge: 76,
    wealth: 12400,
    relationships: { 苏敏: 82 },
  },
};

interface ReadyEndingFixtureOptions {
  gameId?: number;
  playerName?: string;
  response?: typeof CANONICAL_ENDING_RESPONSE;
}

/**
 * Install a deterministic, canonical ready response for frontend rendering tests.
 * Backend endpoint/error contracts remain covered separately with real requests.
 */
export async function installReadyEndingFixture(
  page: Page,
  {
    gameId = 91001,
    playerName = '测试角色',
    response = CANONICAL_ENDING_RESPONSE,
  }: ReadyEndingFixtureOptions = {},
): Promise<number> {
  await page.route(`**/api/games/${gameId}/ending`, async (route) => {
    if (route.request().method() !== 'GET') {
      await route.continue();
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(response),
    });
  });

  await page.goto('/');
  await page.evaluate(
    ({ fixtureGameId, fixturePlayerName }) => {
      localStorage.setItem(
        'game-store',
        JSON.stringify({
          state: {
            gameId: fixtureGameId,
            playerState: { player_name: fixturePlayerName },
          },
          version: 0,
        }),
      );
    },
    { fixtureGameId: gameId, fixturePlayerName: playerName },
  );

  return gameId;
}
