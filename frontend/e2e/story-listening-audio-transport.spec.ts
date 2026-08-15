import { expect, test, type Page, type Route } from '@playwright/test';

const GAME_ID = 880101;
const AUDIO_DURATION_SECONDS = 12;

type AudioFixture = {
  audioRequests: string[];
  rangeRequests: string[];
  choiceRequests: number;
};

type FixtureOptions = {
  failFirstAudioRequest?: boolean;
  progress?: { paragraphIndex: number; positionMs: number };
};

/**
 * Produce a short PCM WAV in memory so the browser decodes real audio without
 * committing an opaque binary fixture. The low sample rate keeps each test
 * fixture below 200 KiB while retaining enough duration for the 8s watchdog.
 */
function createPlayableWav(): Buffer {
  const sampleRate = 8_000;
  const sampleCount = sampleRate * AUDIO_DURATION_SECONDS;
  const dataLength = sampleCount * 2;
  const wav = Buffer.alloc(44 + dataLength);

  wav.write('RIFF', 0);
  wav.writeUInt32LE(36 + dataLength, 4);
  wav.write('WAVEfmt ', 8);
  wav.writeUInt32LE(16, 16);
  wav.writeUInt16LE(1, 20);
  wav.writeUInt16LE(1, 22);
  wav.writeUInt32LE(sampleRate, 24);
  wav.writeUInt32LE(sampleRate * 2, 28);
  wav.writeUInt16LE(2, 32);
  wav.writeUInt16LE(16, 34);
  wav.write('data', 36);
  wav.writeUInt32LE(dataLength, 40);
  for (let sample = 0; sample < sampleCount; sample += 1) {
    const amplitude = Math.round(Math.sin((sample / sampleRate) * Math.PI * 2 * 440) * 1_200);
    wav.writeInt16LE(amplitude, 44 + sample * 2);
  }
  return wav;
}

function parseRange(range: string | undefined, byteLength: number): { start: number; end: number } | null {
  if (!range) return null;
  const match = /^bytes=(\d*)-(\d*)$/.exec(range);
  if (!match) return null;
  const [, startText, endText] = match;
  if (!startText && !endText) return null;
  if (!startText) {
    const suffixLength = Number(endText);
    return { start: Math.max(0, byteLength - suffixLength), end: byteLength - 1 };
  }
  const start = Number(startText);
  const end = endText ? Math.min(Number(endText), byteLength - 1) : byteLength - 1;
  if (start > end || start >= byteLength) return null;
  return { start, end };
}

async function fulfillRangeAudio(route: Route, wav: Buffer, fixture: AudioFixture, shouldFail: boolean): Promise<void> {
  const request = route.request();
  const range = request.headers().range;
  fixture.audioRequests.push(new URL(request.url()).pathname);
  if (range) fixture.rangeRequests.push(range);

  if (shouldFail) {
    await route.fulfill({ status: 503, contentType: 'text/plain', body: 'temporary audio transport failure' });
    return;
  }

  const selection = parseRange(range, wav.length);
  if (range && !selection) {
    await route.fulfill({
      status: 416,
      headers: { 'accept-ranges': 'bytes', 'content-range': `bytes */${wav.length}` },
    });
    return;
  }
  const body = selection ? wav.subarray(selection.start, selection.end + 1) : wav;
  await route.fulfill({
    status: selection ? 206 : 200,
    contentType: 'audio/wav',
    headers: {
      'accept-ranges': 'bytes',
      'content-length': String(body.length),
      ...(selection ? { 'content-range': `bytes ${selection.start}-${selection.end}/${wav.length}` } : {}),
    },
    body,
  });
}

async function installFixture(page: Page, options: FixtureOptions = {}): Promise<AudioFixture> {
  const fixture: AudioFixture = { audioRequests: [], rangeRequests: [], choiceRequests: 0 };
  const wav = createPlayableWav();
  let failNextAudioRequest = options.failFirstAudioRequest === true;
  const story = [
    '第一段：雨后的书铺里，林舟发现了一封没有署名的信。',
    '第二段：他沿着墨迹留下的线索走向河边仓库。',
    '第三段：晨雾散去时，仓门后传来熟悉的脚步声。',
  ].join('\n\n');
  const timeline = {
    version: 2,
    start_date: '2026-08-13',
    current_date: '2026-08-13',
    day_index: 0,
    day_number: 1,
    completed_days: 0,
    week_number: 1,
    weekday: 4,
    total_days: 672,
  };
  const gameState = {
    game_id: GAME_ID,
    player_state: {
      player_name: '林舟',
      age: 22,
      timeline_version: 2,
      timeline,
      character_settings: { era: { year: 2026 }, age: { age: 22 } },
    },
    progress: { timeline },
    round_info: { timeline, current_round: 0, game_over: false },
    current_event: {
      event_id: 'audio-transport-day-0',
      revision: 1,
      story_date: '2026-08-13',
      event_description: story,
      options: [{ text: '拆开信封' }, { text: '先询问掌柜' }],
    },
    constraint_level: 'expert',
  };

  await page.route('**/api/auth/me', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ user_id: 1, public_id: 'AUDIO-E2E', display_name: 'Audio E2E' }),
  }));
  await page.route('**/api/games/active', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(gameState),
  }));
  await page.route(`**/api/games/${GAME_ID}`, (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(gameState),
  }));
  await page.route(`**/api/images/**/${GAME_ID}**`, (route) => route.fulfill({
    status: 404,
    contentType: 'application/json',
    body: JSON.stringify({ detail: 'fixture' }),
  }));
  await page.route('**/api/voice-reading/settings', (route) => route.fulfill({
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
  }));
  await page.route('**/api/voice-reading/progress**', (route) => {
    if (route.request().method() !== 'GET') return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
    if (!options.progress) return route.fulfill({ status: 404, contentType: 'application/json', body: '{}' });
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        paragraph_index: options.progress.paragraphIndex,
        position_ms: options.progress.positionMs,
        completed: false,
      }),
    });
  });
  await page.route('**/api/voice-reading/read', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({
      job_id: 777,
      status: 'ready',
      playback_mode: 'audio',
      provider: 'minimax',
      model: 'speech-02-turbo',
      message: '',
      segments: [0, 1, 2].map((paragraph_index) => ({
        paragraph_index,
        status: 'ready',
        audio_url: `/api/voice-reading/audio/fixture-${paragraph_index}.wav`,
        duration_ms: AUDIO_DURATION_SECONDS * 1_000,
        media_type: 'audio/wav',
      })),
    }),
  }));
  await page.route('**/api/voice-reading/audio/*.wav', (route) => {
    const shouldFail = failNextAudioRequest;
    failNextAudioRequest = false;
    return fulfillRangeAudio(route, wav, fixture, shouldFail);
  });
  await page.route(`**/api/games/${GAME_ID}/choice`, (route) => {
    fixture.choiceRequests += 1;
    return route.fulfill({
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
      body: `event: complete\ndata: ${JSON.stringify({ effects_applied: {}, story_continuation: '', game_over: false })}\n\ndata: [DONE]\n\n`,
    });
  });
  return fixture;
}

async function expectRealPlayback(page: Page): Promise<void> {
  await expect.poll(
    () => page.locator('audio').evaluate((audio) => !audio.paused && audio.currentTime > 0.05),
    { timeout: 15_000 },
  ).toBe(true);
}

test.describe('StoryListeningExperience audio transport', () => {
  test('autoplays generated WAV audio through the Range-aware fixture', async ({ page }) => {
    const fixture = await installFixture(page);
    await page.goto(`/play?gameId=${GAME_ID}`);

    await expect(page.getByRole('heading', { name: '听故事' })).toBeVisible();
    await expectRealPlayback(page);
    await expect.poll(() => fixture.audioRequests.length).toBeGreaterThan(0);
    await expect.poll(() => fixture.rangeRequests.length).toBeGreaterThan(0);
  });

  test('reloads and resumes after the first real audio request fails', async ({ page }) => {
    const fixture = await installFixture(page, { failFirstAudioRequest: true });
    await page.goto(`/play?gameId=${GAME_ID}`);

    await expect.poll(() => fixture.audioRequests.length).toBe(1);
    await expect.poll(() => fixture.audioRequests.length, { timeout: 15_000 }).toBeGreaterThanOrEqual(2);
    // A delayed retry may lose the browser's autoplay gesture. The transport
    // recovery is complete once the real source has reloaded; a user click is
    // then the portable way to resume on both configured browser projects.
    const resumeButton = page.getByRole('button', { name: '播放朗读' });
    if (await resumeButton.isVisible()) await resumeButton.click();
    await expectRealPlayback(page);
  });

  test('autoplays the persisted middle paragraph rather than restarting from the first', async ({ page }) => {
    const fixture = await installFixture(page, { progress: { paragraphIndex: 1, positionMs: 0 } });
    await page.goto(`/play?gameId=${GAME_ID}`);

    await expect(page.getByText('第 2 段', { exact: true })).toBeVisible();
    await expect(page.locator('audio')).toHaveAttribute('src', '/api/voice-reading/audio/fixture-1.wav');
    await expectRealPlayback(page);
    expect(fixture.audioRequests[0]).toBe('/api/voice-reading/audio/fixture-1.wav');
  });

  test('a choice during recovery prevents the old failed audio from being restarted', async ({ page }) => {
    const fixture = await installFixture(page, { failFirstAudioRequest: true });
    await page.goto(`/play?gameId=${GAME_ID}`);

    await expect.poll(() => fixture.audioRequests.length).toBe(1);
    await page.getByRole('button', { name: '拆开信封' }).click();
    await expect.poll(() => fixture.choiceRequests).toBe(1);
    await page.waitForTimeout(8_500);
    expect(fixture.audioRequests).toHaveLength(1);
  });
});
