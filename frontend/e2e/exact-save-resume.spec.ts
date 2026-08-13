import { test, expect } from '@playwright/test';

import { API_URL, ensureAuthenticated } from './helpers/auth';

test('loading a result save preserves the result until explicit continuation', async ({
  page,
  context,
}) => {
  // This legacy-v1 compatibility path intentionally exercises the real story
  // and continuation providers. Provider retries can exceed the normal five
  // minute E2E budget without indicating a product deadlock.
  test.setTimeout(600_000);
  await ensureAuthenticated(page, context);

  const playerName = `精确恢复_${Date.now()}`;
  const createResponse = await page.request.post(`${API_URL}/api/games`, {
    data: {
      player_name: playerName,
      life_vision: '验证结果页存档不会自动推进',
      character_settings: {
        era: { name: '现代', period: '2026' },
        age: { age: 29, stage: '青年' },
        personality: { traits: ['谨慎'] },
        background: { occupation: '产品经理' },
      },
      language: 'zh',
      constraint_level: 'fast',
    },
  });
  expect(createResponse.ok()).toBeTruthy();
  const created = await createResponse.json();
  const gameId = created.game_id as number;

  const eventResponse = await page.request.post(
    `${API_URL}/api/games/${gameId}/event-sync`,
    { data: {} },
  );
  expect(eventResponse.ok()).toBeTruthy();
  const event = await eventResponse.json();
  expect(event.options.length).toBeGreaterThan(0);

  const choiceResponse = await page.request.post(
    `${API_URL}/api/games/${gameId}/choice-sync`,
    { data: { option_index: 0 } },
  );
  expect(choiceResponse.ok()).toBeTruthy();
  const choice = await choiceResponse.json();

  const savedResponse = await page.request.post(`${API_URL}/api/games/${gameId}/save`);
  expect(savedResponse.ok()).toBeTruthy();
  const playlistResponse = await page.request.put(
    `${API_URL}/api/music/playlist/${gameId}`,
    {
      data: {
        songs: [
          {
            id: 42,
            name: '存档恢复测试曲目',
            artists: ['测试音乐人'],
            album: '测试专辑',
            duration: 180,
          },
        ],
        mood: '平静',
        keywords: ['存档恢复'],
      },
    },
  );
  expect(playlistResponse.ok()).toBeTruthy();
  const stateBeforeLoad = await (
    await page.request.get(`${API_URL}/api/games/${gameId}`)
  ).json();
  expect(stateBeforeLoad.player_state.resume_view.phase).toBe('result');
  expect(stateBeforeLoad.player_state.current_round).toBe(1);

  const eventRequests: string[] = [];
  page.on('request', (request) => {
    const pathname = new URL(request.url()).pathname;
    if (pathname.endsWith(`/games/${gameId}/event`)) {
      eventRequests.push(request.url());
    }
  });

  // Restore the persisted playlist before opening saves. The global sound panel
  // must not intercept the save card's primary action when it is expanded.
  await page.evaluate((id) => localStorage.setItem('gameId', String(id)), gameId);
  await page.reload();
  await page.waitForLoadState('domcontentloaded');
  await page.getByTestId('global-music-mini-bar').waitFor({
    state: 'visible',
    timeout: 15_000,
  });

  // Follow the real authenticated entry point. A hard navigation to /saves
  // resets the current in-memory auth bootstrap before that page can list saves.
  await page.getByRole('button', { name: '加载存档' }).click();
  await expect(page).toHaveURL(/\/saves$/, { timeout: 15_000 });
  await expect(page.getByText(playerName)).toBeVisible({ timeout: 15_000 });
  await page.getByRole('button', { name: '展开声音' }).click();
  await expect(page.getByTestId('unified-sound-panel')).toBeVisible();
  const saveCard = page.getByText(playerName).locator('xpath=ancestor::*[.//button][1]');
  await saveCard.getByRole('button', { name: '继续' }).click();
  await expect(page).toHaveURL(/\/play$/, { timeout: 15_000 });

  await expect(page.getByRole('button', { name: '进入周中' })).toBeVisible({
    timeout: 15_000,
  });
  const visibleContinuation = choice.story_continuation
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/\\([\\`*{}\[\]()#+\-.!_>])/g, '$1')
    .replace(/\s+/g, ' ')
    .trim();
  await expect(page.locator('main')).toContainText(visibleContinuation.slice(0, 40));
  expect(eventRequests).toHaveLength(0);

  const stateAfterLoad = await (
    await page.request.get(`${API_URL}/api/games/${gameId}`)
  ).json();
  expect(stateAfterLoad.player_state.current_round).toBe(1);
  expect(stateAfterLoad.player_state.resume_view.phase).toBe('result');

  const acknowledgePromise = page.waitForResponse(
    (response) =>
      response.url().includes(`/games/${gameId}/resume-view/acknowledge`) &&
      response.status() === 200,
  );
  await page.getByRole('button', { name: '进入周中' }).click();
  await acknowledgePromise;
  await expect.poll(() => eventRequests.length).toBeGreaterThan(0);
});
