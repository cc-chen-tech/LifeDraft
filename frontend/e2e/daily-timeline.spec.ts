import { expect, test } from '@playwright/test';

test('daily choice settles once and automatically opens the next calendar day', async ({ page }) => {
  const gameId = 880001;
  let dayIndex = 0;
  let currentEvent: Record<string, unknown> | null = {
    event_id: 'daily-0',
    revision: 1,
    story_date: '2026-08-13',
    event_description: '第一天，林舟在雨后的书铺里发现了一封没有署名的信。',
    options: [
      { text: '拆开信封', effects: { knowledge: 2 } },
      { text: '先询问掌柜', effects: { mood: 1 } },
    ],
  };
  let choiceCalls = 0;
  let regenerateCalls = 0;
  let rewriteCalls = 0;

  const timeline = () => ({
    version: 2,
    start_date: '2026-08-13',
    current_date: dayIndex === 0 ? '2026-08-13' : '2026-08-14',
    day_index: dayIndex,
    day_number: dayIndex + 1,
    completed_days: dayIndex,
    week_number: 1,
    weekday: dayIndex === 0 ? 4 : 5,
    total_days: 672,
  });
  const gameState = () => ({
    game_id: gameId,
    player_state: {
      player_name: '林舟',
      age: 22,
      energy: 80,
      mood: 70,
      knowledge: 52,
      wealth: 10000,
      timeline_version: 2,
      timeline: timeline(),
      day_history: dayIndex
        ? [{ day_index: 0, story_date: '2026-08-13', event_description: '第一天的故事' }]
        : [],
      character_settings: { era: { year: 2026 }, age: { age: 22 } },
    },
    progress: { timeline: timeline() },
    round_info: { timeline: timeline(), current_round: dayIndex, game_over: false },
    current_event: currentEvent,
    constraint_level: 'expert',
  });

  await page.route('**/api/auth/me', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ user_id: 1, public_id: 'DAILY-E2E', display_name: 'Daily E2E' }),
    }),
  );
  await page.route('**/api/games/active', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(gameState()) }),
  );
  await page.route(`**/api/games/${gameId}/choice`, async (route) => {
    choiceCalls += 1;
    expect(route.request().postDataJSON()).toEqual({
      option_index: 0,
      event_id: 'daily-0',
      revision: 3,
    });
    dayIndex = 1;
    currentEvent = null;
    await route.fulfill({
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
      body:
        `event: complete\ndata: ${JSON.stringify({
          effects_applied: { knowledge: 2 },
          story_continuation: '',
          need_weekly_summary: false,
          next_timeline: timeline(),
          game_over: false,
        })}\n\ndata: [DONE]\n\n`,
    });
  });
  await page.route(`**/api/games/${gameId}/regenerate-stream`, async (route) => {
    regenerateCalls += 1;
    currentEvent = {
      event_id: 'daily-0',
      revision: 2,
      story_date: '2026-08-13',
      event_description: '第一天重新生成后，林舟在信封夹层里发现一枚旧钥匙。',
      options: [{ text: '收好钥匙' }, { text: '交给掌柜' }],
    };
    await route.fulfill({
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
      body: `event: complete\ndata: ${JSON.stringify(currentEvent)}\n\ndata: [DONE]\n\n`,
    });
  });
  await page.route(`**/api/games/${gameId}/rewrite-stream`, async (route) => {
    rewriteCalls += 1;
    currentEvent = {
      event_id: 'daily-0',
      revision: 3,
      story_date: '2026-08-13',
      event_description: '改写后的第一天，旧钥匙上刻着河边仓库的编号。',
      options: [{ text: '记下仓库编号' }, { text: '询问钥匙来历' }],
    };
    await route.fulfill({
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
      body:
        `event: complete\ndata: ${JSON.stringify({
          new_story: currentEvent.event_description,
          rewritten_story: currentEvent.event_description,
          event: currentEvent,
        })}\n\ndata: [DONE]\n\n`,
    });
  });
  await page.route(`**/api/games/${gameId}/event`, async (route) => {
    currentEvent = {
      event_id: 'daily-1',
      revision: 1,
      story_date: '2026-08-14',
      event_description: '第二天，林舟循着信上的线索来到河边仓库。',
      options: [
        { text: '进入仓库', effects: { energy: -2 } },
        { text: '绕到后门观察', effects: { knowledge: 1 } },
      ],
    };
    await route.fulfill({
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
      body: `event: complete\ndata: ${JSON.stringify(currentEvent)}\n\ndata: [DONE]\n\n`,
    });
  });
  await page.route(`**/api/games/${gameId}`, async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(gameState()) });
      return;
    }
    await route.continue();
  });
  await page.route(`**/api/images/scenes/${gameId}`, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ scenes: [] }) }),
  );
  await page.route(`**/api/images/scene/${gameId}/**`, (route) =>
    route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'fixture' }) }),
  );
  await page.route('**/api/voice-reading/settings', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ tts_provider: 'browser' }) }),
  );
  await page.route('**/api/music/recommend', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ songs: [] }) }),
  );
  await page.route(`**/api/music/playlist/${gameId}`, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ songs: [], queue: [] }) }),
  );

  await page.goto(`/play?gameId=${gameId}`);
  await expect(page.getByRole('heading', { name: '公元 2026 年 8 月 13 日' })).toBeVisible();
  await expect(page.getByRole('button', { name: '拆开信封' })).toBeVisible();
  await expect(page.getByPlaceholder('输入你想做的事...')).toHaveCount(0);

  await page.getByRole('button', { name: '打开工具' }).click();
  await page.getByRole('button', { name: '重新生成今天' }).click();
  await expect(page.getByText('第一天重新生成后，林舟在信封夹层里发现一枚旧钥匙。')).toBeVisible();
  await expect(page.getByRole('button', { name: '收好钥匙' })).toBeVisible();

  await page.getByRole('button', { name: '打开工具' }).click();
  await page.getByRole('button', { name: '改写今天' }).click();
  await page.getByPlaceholder(/描述你想要的修改/).fill('让线索指向仓库');
  await page.getByRole('button', { name: '改写故事' }).click();
  await expect(page.getByText('改写后的第一天，旧钥匙上刻着河边仓库的编号。')).toBeVisible();
  await page.getByRole('button', { name: '关闭故事调整' }).click();
  await expect(page.getByRole('button', { name: '记下仓库编号' })).toBeVisible();

  await page.getByRole('button', { name: '记下仓库编号' }).click();

  await expect(page.getByRole('heading', { name: '公元 2026 年 8 月 14 日' })).toBeVisible();
  await expect(page.getByText('第二天，林舟循着信上的线索来到河边仓库。')).toBeVisible();
  await expect(page.getByRole('button', { name: '进入仓库' })).toBeVisible();
  await expect(page.getByRole('button', { name: /进入周中|进入周末|确认并继续/ })).toHaveCount(0);
  expect(choiceCalls).toBe(1);
  expect(regenerateCalls).toBe(1);
  expect(rewriteCalls).toBe(1);
});

test('migrated save resumes on its mapped calendar date without legacy controls', async ({ page }) => {
  const gameId = 880002;
  const timeline = {
    version: 2,
    start_date: '2026-01-05',
    current_date: '2026-01-14',
    day_index: 9,
    day_number: 10,
    completed_days: 9,
    week_number: 2,
    weekday: 3,
    total_days: 672,
  };
  const state = {
    game_id: gameId,
    player_state: {
      player_name: '旧存档角色',
      age: 30,
      timeline_version: 2,
      timeline,
      day_history: [{ day_index: 6, story_date: '2026-01-11', event_description: '旧周末正文' }],
      character_settings: { era: { year: 2026 } },
    },
    progress: { timeline },
    round_info: { timeline, current_round: 9, game_over: false },
    current_event: {
      event_id: 'day:9',
      revision: 1,
      story_date: '2026-01-14',
      event_description: '迁移后的未选择事件仍停留在原周中映射日期。',
      options: [{ text: '查看旧信' }, { text: '暂时收起' }],
    },
    constraint_level: 'expert',
  };

  await page.route(`**/api/games/${gameId}`, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(state) }),
  );
  await page.route('**/api/games/active', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(state) }),
  );
  await page.route('**/api/auth/me', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }),
  );
  await page.route('**/api/voice-reading/settings', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }),
  );
  await page.route('**/api/music/**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ songs: [], queue: [] }) }),
  );
  await page.route(`**/api/images/**/${gameId}**`, (route) =>
    route.fulfill({ status: 404, contentType: 'application/json', body: '{}' }),
  );

  await page.goto(`/play?gameId=${gameId}`);
  await expect(page.getByRole('heading', { name: '公元 2026 年 1 月 14 日' })).toBeVisible();
  await expect(page.getByText('迁移后的未选择事件仍停留在原周中映射日期。')).toBeVisible();
  await expect(page.getByRole('button', { name: '查看旧信' })).toBeVisible();
  await expect(page.getByRole('button', { name: /进入周中|进入周末|确认并继续/ })).toHaveCount(0);
});

test('refresh after a saved choice safely retries generation on the advanced day', async ({ page }) => {
  const gameId = 880003;
  const timeline = {
    version: 2,
    start_date: '2026-08-13',
    current_date: '2026-08-14',
    day_index: 1,
    day_number: 2,
    completed_days: 1,
    week_number: 1,
    weekday: 5,
    total_days: 672,
  };
  const state = {
    game_id: gameId,
    player_state: {
      player_name: '断线恢复角色',
      age: 22,
      timeline_version: 2,
      timeline,
      day_history: [{
        event_id: 'daily-0',
        day_index: 0,
        story_date: '2026-08-13',
        event_description: '第一天已结算',
        choice: '继续',
        postprocessing_status: 'pending',
      }],
      character_settings: { era: { year: 2026 } },
    },
    progress: { timeline },
    round_info: { timeline, current_round: 1, game_over: false },
    current_event: null,
    constraint_level: 'expert',
  };
  let generationCalls = 0;

  await page.route(`**/api/games/${gameId}`, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(state) }),
  );
  await page.route('**/api/games/active', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(state) }),
  );
  await page.route(`**/api/games/${gameId}/event`, async (route) => {
    generationCalls += 1;
    await route.fulfill({
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' },
      body: `event: complete\ndata: ${JSON.stringify({
        event_id: 'daily-1',
        revision: 1,
        story_date: '2026-08-14',
        event_description: '刷新后，第二天故事在正确日期重新生成。',
        options: [{ text: '继续调查' }, { text: '先休息' }],
      })}\n\ndata: [DONE]\n\n`,
    });
  });
  await page.route('**/api/auth/me', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }),
  );
  await page.route('**/api/voice-reading/settings', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }),
  );
  await page.route('**/api/music/**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ songs: [], queue: [] }) }),
  );
  await page.route(`**/api/images/**/${gameId}**`, (route) =>
    route.fulfill({ status: 404, contentType: 'application/json', body: '{}' }),
  );

  await page.goto(`/play?gameId=${gameId}`);
  await expect(page.getByRole('heading', { name: '公元 2026 年 8 月 14 日' })).toBeVisible();
  await expect(page.getByText('刷新后，第二天故事在正确日期重新生成。')).toBeVisible();
  await expect(page.getByRole('button', { name: '继续调查' })).toBeVisible();
  expect(generationCalls).toBe(1);
});
