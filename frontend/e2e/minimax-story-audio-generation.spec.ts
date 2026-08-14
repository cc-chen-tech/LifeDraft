import { test, expect, Page } from '@playwright/test';
import { ensureActiveGame, registerUser } from './helpers/auth';

async function openRegressionFixture(page: Page, gameId?: number): Promise<void> {
  const url = gameId ? `/e2e-regression?gameId=${gameId}` : '/e2e-regression';
  await page.goto(url);
  await page.waitForLoadState('domcontentloaded');
  await expect(page.getByRole('button', { name: '朗读故事' })).toBeVisible();
  await expect(page.getByTestId('voice-reading-audio-player')).toHaveCount(1);
}

async function ensureVoiceAudioPlaying(page: Page): Promise<void> {
  await expect(page.getByTestId('voice-reading-mode')).toHaveText('audio', { timeout: 15_000 });
  await expect(page.getByTestId('voice-reading-playback-mode')).toHaveText('audio');
  await expect(page.getByTestId('voice-reading-audio-url')).toContainText('/api/voice-reading/audio/');
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
}

test.describe('MiniMax story audio generation', () => {
  test.beforeEach(async ({ context }) => {
    const user = await registerUser(context, `MiniMaxAudio_${Date.now()}`);
    expect(user).not.toBeNull();
  });

  test('provider story narration attaches decodable audio without using browser speech fallback', async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('story_voice_e2e_provider', 'minimax');
    });
    await openRegressionFixture(page);

    await page.getByRole('button', { name: '朗读故事' }).click();

    await ensureVoiceAudioPlaying(page);
    await expect(page.getByTestId('voice-reading-provider')).toHaveText('minimax');
    await expect(page.getByTestId('voice-reading-audio-player')).toHaveJSProperty('readyState', 4);
    await expect
      .poll(async () =>
        page.getByTestId('voice-reading-audio-player').evaluate((element) => {
          const audio = element as HTMLAudioElement;
          return !audio.paused && Number.isFinite(audio.duration) && audio.duration > 0;
        })
      )
      .toBe(true);
    await expect(page.getByTestId('voice-reading-speech-text')).toHaveText('');
  });

  test('generated MiniMax music appears in future queue without replacing current track', async ({ page }) => {
    await openRegressionFixture(page);

    await page.getByRole('button', { name: '触发 MiniMax 音乐生成夹具' }).click();

    await expect(page.getByTestId('current-music-source')).toHaveText('netease');
    await expect(page.getByTestId('current-music-title')).toHaveText('网易云 当前曲');
    await expect(page.getByTestId('music-queue-order')).toContainText('AI MiniMax 雨夜追逐');
    await expect(page.getByTestId('generated-music-provider')).toHaveText('minimax');
    await expect(page.getByTestId('generated-music-source')).toHaveText('ai_generated');
    await expect(page.getByTestId('generated-music-audio')).toHaveJSProperty('readyState', 4);
  });

  test('real generated MiniMax music is inserted into future store queue', async ({ page, context }) => {
    const gameId = await ensureActiveGame(page, context, {
      player_name: 'MiniMax音乐队列测试角色',
      life_vision: '验证故事音乐生成后进入后续队列',
    });
    await openRegressionFixture(page, gameId);

    await page.getByRole('button', { name: '触发 MiniMax 音乐生成', exact: true }).click();

    await expect(page.getByTestId('real-current-music-title')).toHaveText('全局音乐夹具');
    await expect(page.getByTestId('real-music-queue-order')).toContainText(
      'AI MiniMax 雨夜追逐 | 网易云 下一曲 | 网易云 后续曲',
      { timeout: 15_000 }
    );
    await expect(page.getByTestId('real-generated-music-url')).toContainText('/api/music/generated/');
  });

  test('auto-read stays off by default and starts only after final story when enabled', async ({ page }) => {
    await page.addInitScript(() => {
      window.localStorage.setItem('story_voice_e2e_provider', 'minimax');
    });
    await openRegressionFixture(page);

    await page.getByRole('button', { name: '模拟 retry 替换' }).click();
    await expect(page.getByTestId('voice-reading-state')).toHaveText('idle');
    await expect(page.getByTestId('voice-reading-audio-url')).toHaveText('');

    await page.reload();
    await expect(page.getByRole('button', { name: '朗读故事' })).toBeVisible();
    await page.getByRole('checkbox', { name: '自动朗读' }).check();
    await page.getByRole('button', { name: '模拟首轮 stream' }).click();
    await expect(page.getByTestId('voice-reading-state')).toHaveText('idle');

    await page.getByRole('button', { name: '模拟 retry 替换' }).click();
    await ensureVoiceAudioPlaying(page);
    await expect(page.getByTestId('voice-reading-provider')).toHaveText('minimax');
    await expect(page.getByTestId('voice-reading-audio-player')).toHaveJSProperty('readyState', 4);
  });
});
