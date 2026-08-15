import { expect, test, type Page } from '@playwright/test';

async function stubHighQualityNarration(page: Page): Promise<void> {
  await page.route('**/api/voice-reading/settings', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        auto_read_enabled: false,
        selected_voice_color: 'warm_female',
        selected_speed: 1,
        tts_provider: 'minimax',
        tts_provider_available: true,
        backend_audio_enabled: true,
        playback_mode: 'audio',
      }),
    }),
  );
  await page.route('**/api/voice-reading/progress**', (route) =>
    route.fulfill({ status: 404, contentType: 'application/json', body: '{}' }),
  );
  await page.route('**/api/voice-reading/read', async (route) => {
    const request = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        job_id: 901,
        status: 'ready',
        playback_mode: 'audio',
        provider: 'minimax',
        model: 'speech-02-turbo',
        message: '',
        segments: [{
          paragraph_index: 0,
          status: 'ready',
          audio_url: '/api/voice-reading/audio/e2e.mp3',
          duration_ms: Math.max(1_000, String(request.context.text).length * 100),
          media_type: 'audio/mpeg',
        }],
      }),
    });
  });
}

test('daily choice settles once and automatically opens the next calendar day', async ({ page }) => {
  const gameId = 880001;
  let dayIndex = 0;
  let currentEvent: Record<string, unknown> | null = {
    event_id: 'daily-0',
    revision: 1,
    story_date: '2026-08-13',
    event_description: '第一天，林舟在雨后的书铺里发现了一封没有署名的信。\n\n窗外的雨声渐渐停了。',
    options: [
      { text: '拆开信封', effects: { knowledge: 2 } },
      { text: '先询问掌柜', effects: { mood: 1 } },
    ],
  };
  let choiceCalls = 0;
  let narrationCalls = 0;
  let musicCalls = 0;
  page.on('request', (request) => {
    if (new URL(request.url()).pathname.startsWith('/api/music/')) {
      musicCalls += 1;
    }
  });

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
      revision: 1,
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
  await page.route(`**/api/games/${gameId}/event`, async (route) => {
    currentEvent = {
      event_id: 'daily-1',
      revision: 1,
      story_date: '2026-08-14',
      event_description: '第二天，林舟循着信上的线索来到河边仓库。\n\n晨雾里的仓门半掩着。',
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
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        auto_read_enabled: true,
        selected_voice_color: 'warm_female',
        selected_speed: 1,
        tts_provider: 'minimax',
        tts_model: 'speech-02-turbo',
        tts_provider_available: true,
        backend_audio_enabled: true,
        playback_mode: 'audio',
      }),
    }),
  );
  await page.route('**/api/voice-reading/progress**', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({ status: 404, contentType: 'application/json', body: '{}' });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: route.request().postData() || '{}',
    });
  });
  await page.route('**/api/voice-reading/read', async (route) => {
    narrationCalls += 1;
    const request = route.request().postDataJSON();
    const paragraphs = String(request.context.text).split(/\n\s*\n/);
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        job_id: narrationCalls,
        status: 'ready',
        playback_mode: 'audio',
        provider: 'minimax',
        model: 'speech-02-turbo',
        message: '',
        segments: paragraphs.map((_: string, paragraphIndex: number) => ({
          paragraph_index: paragraphIndex,
          status: 'ready',
          audio_url: `/api/voice-reading/audio/day-${dayIndex}-${paragraphIndex}.mp3`,
          duration_ms: 4_000,
          media_type: 'audio/mpeg',
        })),
      }),
    });
  });
  await page.addInitScript(() => {
    const playback = { play: 0, pause: 0 };
    Object.defineProperty(window, '__storyAudioEvents', { value: playback });
    HTMLMediaElement.prototype.play = function play() {
      playback.play += 1;
      return Promise.resolve();
    };
    HTMLMediaElement.prototype.pause = function pause() {
      playback.pause += 1;
    };
  });

  await page.goto(`/play?gameId=${gameId}`);
  await expect(page.getByRole('heading', { name: '听故事' })).toBeVisible();
  await expect(page.getByText('公元 2026 年 8 月 13 日')).toBeVisible();
  await expect(page.getByRole('button', { name: '拆开信封' })).toBeVisible();
  await expect(page.getByPlaceholder('输入你想做的事...')).toHaveCount(0);
  await expect.poll(() => narrationCalls).toBe(1);
  await expect.poll(() => page.evaluate(() => (window as unknown as { __storyAudioEvents: { play: number } }).__storyAudioEvents.play)).toBeGreaterThan(0);

  await page.getByRole('button', { name: '查看正文' }).first().click();
  await page.getByRole('button', { name: '从第 2 段开始朗读' }).click();
  const pausesBeforeChoice = await page.evaluate(() => (window as unknown as { __storyAudioEvents: { pause: number } }).__storyAudioEvents.pause);
  await page.getByRole('button', { name: '拆开信封' }).click();

  await expect(page.getByText('公元 2026 年 8 月 14 日')).toBeVisible();
  await expect(page.getByRole('heading', { name: '听故事' })).toBeVisible();
  await expect(page.getByRole('button', { name: '进入仓库' })).toBeVisible();
  await expect(page.getByRole('button', { name: /进入周中|进入周末|确认并继续/ })).toHaveCount(0);
  await expect.poll(() => narrationCalls).toBe(2);
  await expect.poll(() => page.evaluate(() => (window as unknown as { __storyAudioEvents: { pause: number } }).__storyAudioEvents.pause)).toBeGreaterThan(pausesBeforeChoice);
  expect(choiceCalls).toBe(1);
  expect(musicCalls).toBe(0);
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
  await stubHighQualityNarration(page);
  await page.route(`**/api/images/**/${gameId}**`, (route) =>
    route.fulfill({ status: 404, contentType: 'application/json', body: '{}' }),
  );

  await page.goto(`/play?gameId=${gameId}`);
  await expect(page.getByText('公元 2026 年 1 月 14 日')).toBeVisible();
  await page.getByRole('button', { name: '查看正文' }).first().click();
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
  await stubHighQualityNarration(page);
  await page.route(`**/api/images/**/${gameId}**`, (route) =>
    route.fulfill({ status: 404, contentType: 'application/json', body: '{}' }),
  );

  await page.goto(`/play?gameId=${gameId}`);
  await expect(page.getByText('公元 2026 年 8 月 14 日')).toBeVisible();
  await page.getByRole('button', { name: '查看正文' }).first().click();
  await expect(page.getByText('刷新后，第二天故事在正确日期重新生成。')).toBeVisible();
  await expect(page.getByRole('button', { name: '继续调查' })).toBeVisible();
  expect(generationCalls).toBe(1);
});
