import { test, expect, Page, Request } from '@playwright/test';
import { registerUser } from './helpers/auth';

async function expectBrowserSpeechAttempt(page: Page): Promise<string> {
  await expect(page.getByTestId('voice-reading-mode')).toHaveText('browser_speech');
  await expect(page.getByTestId('voice-reading-spoken-length')).toHaveText(/[1-9]\d+/);
  await expect(page.getByTestId('voice-reading-audio-url')).toHaveText('');
  await expect(page.getByTestId('voice-reading-audio-player')).toHaveJSProperty('src', '');

  const state = await page.getByTestId('voice-reading-state').textContent();
  expect(state).toMatch(/^(playing|failed)$/);
  return state ?? '';
}

async function captureVoiceReadRequests(
  page: Page
): Promise<{ readRequests: Array<Record<string, unknown>>; detach: () => void }> {
  const readRequests: Array<Record<string, unknown>> = [];
  const listener = (request: Request) => {
    if (request.method() === 'POST' && request.url().includes('/api/voice-reading/read')) {
      const postData = request.postDataJSON();
      if (postData) {
        readRequests.push(postData as Record<string, unknown>);
      }
    }
  };
  page.on('request', listener);
  return {
    readRequests,
    detach: () => page.off('request', listener),
  };
}

async function expectBackendAudioAttempt(page: Page): Promise<void> {
  await expect(page.getByTestId('voice-reading-job')).toHaveText(/^\d+$/);
  await expect(page.getByTestId('voice-reading-audio-url')).toContainText(
    '/api/voice-reading/audio/'
  );
  await expect(page.getByTestId('voice-reading-mode')).toHaveText('audio');
  await expect(page.getByTestId('voice-reading-playback-mode')).toHaveText('audio');
  await expect
    .poll(async () => page.getByTestId('voice-reading-state').textContent(), {
      timeout: 15_000,
    })
    .toMatch(/^(ready|playing)$/);
  try {
    await expect(page.getByTestId('voice-reading-state')).toHaveText('playing', { timeout: 2_000 });
  } catch {
    if ((await page.getByTestId('voice-reading-state').textContent()) === 'ready') {
      await page.getByRole('button', { name: '播放语音' }).click();
    }
  }
  await expect(page.getByTestId('voice-reading-state')).toHaveText('playing', { timeout: 15_000 });
  await expect(page.getByTestId('voice-reading-audio-player')).toHaveJSProperty('readyState', 4);
  await expect
    .poll(async () =>
      page.getByTestId('voice-reading-audio-player').evaluate((element) => {
        const audio = element as HTMLAudioElement;
        return Number.isFinite(audio.duration) && audio.duration > 0;
      })
    )
    .toBe(true);
}

async function gotoRegressionPageAfterMusicSettles(page: Page): Promise<void> {
  await page.goto('/e2e-regression');
  await page.waitForLoadState('domcontentloaded');
  await expect(page.getByText('正在分析故事氛围...')).toHaveCount(0, { timeout: 60_000 });
}

async function gotoRegressionPageForVoiceControls(page: Page): Promise<void> {
  await page.goto('/e2e-regression');
  await page.waitForLoadState('domcontentloaded');
  await expect(page.getByRole('button', { name: '朗读故事' })).toBeVisible();
}

test.describe('Story voice reading without login', () => {
  test('unauthenticated reading stays on the story page and falls back to browser speech', async ({ page }) => {
    await gotoRegressionPageForVoiceControls(page);

    await page.getByRole('button', { name: '朗读故事' }).click();

    await expect(page).toHaveURL(/\/e2e-regression$/);
    await expect(page.getByTestId('voice-reading-source')).toHaveText('current_story');
    await expect(page.getByTestId('voice-reading-playback-mode')).toHaveText('browser_speech');
    await expect(page.getByTestId('voice-reading-audio-url')).toHaveText('');
    await expect(page.getByTestId('voice-reading-speech-text')).toHaveText('雨夜码头的旧账册被风吹开。');
  });
});

test.describe('Story voice reading', () => {
  test.describe.configure({ mode: 'serial' });

  test.beforeEach(async ({ context }) => {
    const user = await registerUser(context, `VoiceReader_${Date.now()}`);
    expect(user).not.toBeNull();
  });

  test('reads current and historical story text through the backend asset API', async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('story_voice_e2e_provider', 'local');
    });
    await gotoRegressionPageAfterMusicSettles(page);

    await page.getByRole('button', { name: '朗读故事' }).click();
    await expect(page.getByTestId('voice-reading-source')).toHaveText('current_story');
    await expectBackendAudioAttempt(page);
    await expect(page.getByRole('button', { name: '暂停朗读' })).toBeVisible();
    await expect(page.getByRole('button', { name: '停止' })).toBeVisible();

    await page.getByRole('button', { name: '历史回顾' }).click();
    await page.getByRole('button', { name: '第 3 周 第 2 轮：码头边的对峙' }).click();
    await page.getByRole('button', { name: '朗读历史故事' }).click();

    await expect(page.getByTestId('voice-reading-source')).toHaveText('history_round');
    await expect(page.getByTestId('voice-reading-context')).toContainText('week=3 round=2 stage=event');
    await expectBackendAudioAttempt(page);
  });

  test('uses browser speech fallback with the actual story text when backend audio is unavailable', async ({ page }) => {
    const { readRequests, detach } = await captureVoiceReadRequests(page);

    await page.addInitScript(() => {
      window.localStorage.setItem('story_voice_e2e_provider', 'browser');
    });
    await gotoRegressionPageAfterMusicSettles(page);

    await page.getByRole('button', { name: '朗读故事' }).click();

    await expect(page.getByTestId('voice-reading-source')).toHaveText('current_story');
    const fallbackState = await expectBrowserSpeechAttempt(page);
    await expect(page.getByTestId('voice-reading-playback-mode')).toHaveText('browser_speech');
    await expect(page.getByTestId('voice-reading-speech-text')).toHaveText('雨夜码头的旧账册被风吹开。');
    await expect.poll(async () => readRequests.length).toBe(1);
    const readPayload = readRequests.at(-1) as Record<string, unknown> | undefined;
    expect(readPayload).toBeDefined();
    expect((readPayload as { context: { text: string } }).context.text).toBe('雨夜码头的旧账册被风吹开。');
    detach();
    if (fallbackState === 'playing') {
      await expect
        .poll(async () =>
          page.evaluate(() => {
            const synth = window.speechSynthesis;
            return synth.speaking || synth.pending;
          })
        )
        .toBe(true);
    }
  });

  test('auto-read supersedes stale regenerated attempts and preserves music intent', async ({ page }) => {
    await gotoRegressionPageAfterMusicSettles(page);

    await page.getByRole('checkbox', { name: '自动朗读' }).check();
    await page.getByRole('button', { name: '模拟首轮 stream' }).click();
    await page.getByRole('button', { name: '完成自动朗读入队' }).click();
    await expect(page.getByTestId('voice-reading-queue')).toHaveText('账册被人翻开');

    await page.getByRole('button', { name: '模拟 retry 替换' }).click();
    await page.getByRole('button', { name: '完成自动朗读入队' }).click();
    await expect(page.getByTestId('voice-reading-queue')).toHaveText('苏小二按住账册');
    await expect(page.getByTestId('voice-reading-queue')).not.toContainText('账册被人翻开');

    await page.getByRole('button', { name: '模拟音乐播放中' }).click();
    await page.getByRole('button', { name: '朗读故事' }).click();
    const duckState = await page.getByTestId('music-duck-state').textContent();
    expect(duckState).toMatch(/^(ducked|restored)$/);

    if (duckState === 'ducked') {
      await page.getByRole('button', { name: '用户手动暂停音乐' }).click();
      await page.getByRole('button', { name: '停止' }).click();
      await expect(page.getByTestId('music-duck-state')).toHaveText('user_paused');
    }
  });

  test('ended audio returns controls to a resumable state', async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('story_voice_e2e_provider', 'local');
    });
    await gotoRegressionPageAfterMusicSettles(page);

    await page.getByRole('button', { name: '模拟音乐播放中' }).click();
    await page.getByRole('button', { name: '朗读故事' }).click();
    await expectBackendAudioAttempt(page);

    await page.getByRole('button', { name: '模拟朗读结束' }).click();

    await expect(page.getByTestId('voice-reading-state')).toHaveText('idle');
    await expect(page.getByRole('button', { name: '朗读故事' })).toBeVisible();
    await expect(page.getByRole('button', { name: '继续朗读' })).toHaveCount(0);
    await expect(page.getByTestId('music-duck-state')).toHaveText('restored');
  });

  test('pause and continue controls drive the browser audio element', async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('story_voice_e2e_provider', 'local');
    });
    await gotoRegressionPageAfterMusicSettles(page);

    await page.getByRole('button', { name: '朗读故事' }).click();
    await expectBackendAudioAttempt(page);

    await page.getByRole('button', { name: '暂停朗读' }).click();
    await expect(page.getByTestId('voice-reading-state')).toHaveText('paused');

    await page.getByRole('button', { name: '继续朗读' }).click();
    await expect(page.getByTestId('voice-reading-state')).toHaveText('playing');
    await expect(page.getByTestId('voice-reading-mode')).toHaveText('audio');
  });

  test('manual failure cancels a pending backend audio response', async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('story_voice_e2e_provider', 'local');
    });
    await gotoRegressionPageAfterMusicSettles(page);

    await page.getByRole('button', { name: '朗读故事' }).click();
    await page.getByRole('button', { name: '模拟朗读失败' }).click();

    await expect(page.getByTestId('voice-reading-state')).toHaveText('failed');
    await page.waitForTimeout(1500);
    await expect(page.getByTestId('voice-reading-state')).toHaveText('failed');
    await expect(page.getByTestId('voice-reading-audio-url')).toHaveText('');
    await expect(page.getByRole('button', { name: '重试朗读' })).toBeVisible();
  });

  test('failure state is retryable without blocking other panels', async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('story_voice_e2e_provider', 'browser');
    });
    await gotoRegressionPageAfterMusicSettles(page);

    let readingRequestCount = 0;
    page.on('request', (request) => {
      if (request.method() === 'POST' && request.url().includes('/api/voice-reading/read')) {
        readingRequestCount += 1;
      }
    });

    await page.getByRole('button', { name: '模拟音乐播放中' }).click();
    await page.getByRole('button', { name: '朗读故事' }).click();
    const duckState = await page.getByTestId('music-duck-state').textContent();
    expect(duckState).toMatch(/^(ducked|restored)$/);

    await page.getByRole('button', { name: '模拟朗读失败' }).click();
    await expect(page.getByTestId('voice-reading-state')).toHaveText('failed');
    await expect(page.getByTestId('music-duck-state')).toHaveText('restored');
    await expect(page.getByRole('button', { name: '重试朗读' })).toBeVisible();

    await page.getByRole('button', { name: '重试朗读' }).click();
    await expectBrowserSpeechAttempt(page);
    await expect.poll(() => readingRequestCount).toBe(2);

    await page.getByRole('button', { name: '收集' }).click();
    await expect(page.getByRole('heading', { name: '苏小二' })).toBeVisible();
  });
});
