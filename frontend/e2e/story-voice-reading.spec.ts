import { test, expect, Page } from '@playwright/test';
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

test.describe('Story voice reading', () => {
  test.beforeEach(async ({ context }) => {
    const user = await registerUser(context, `VoiceReader_${Date.now()}`);
    expect(user).not.toBeNull();
  });

  test('reads current and historical story text through browser speech synthesis', async ({ page }) => {
    await page.goto('/e2e-regression');
    await page.waitForLoadState('domcontentloaded');

    await page.getByRole('button', { name: '朗读当前故事' }).click();
    await expect(page.getByTestId('voice-reading-source')).toHaveText('current_story');
    const currentState = await expectBrowserSpeechAttempt(page);
    if (currentState === 'playing') {
      await expect(page.getByRole('button', { name: '暂停朗读' })).toBeVisible();
    }
    await expect(page.getByRole('button', { name: '停止朗读' })).toBeVisible();

    await page.getByRole('button', { name: '历史回顾' }).click();
    await page.getByRole('button', { name: '第 3 周 第 2 轮：码头边的对峙' }).click();
    await page.getByRole('button', { name: '朗读历史故事' }).click();

    await expect(page.getByTestId('voice-reading-source')).toHaveText('history_round');
    await expect(page.getByTestId('voice-reading-context')).toContainText('week=3 round=2 stage=event');
    await expectBrowserSpeechAttempt(page);
  });

  test('auto-read supersedes stale regenerated attempts and preserves music intent', async ({ page }) => {
    await page.goto('/e2e-regression');
    await page.waitForLoadState('domcontentloaded');

    await page.getByRole('button', { name: '启用自动朗读' }).click();
    await page.getByRole('button', { name: '模拟首轮 stream' }).click();
    await page.getByRole('button', { name: '完成自动朗读入队' }).click();
    await expect(page.getByTestId('voice-reading-queue')).toHaveText('账册被人翻开');

    await page.getByRole('button', { name: '模拟 retry 替换' }).click();
    await page.getByRole('button', { name: '完成自动朗读入队' }).click();
    await expect(page.getByTestId('voice-reading-queue')).toHaveText('苏小二按住账册');
    await expect(page.getByTestId('voice-reading-queue')).not.toContainText('账册被人翻开');

    await page.getByRole('button', { name: '模拟音乐播放中' }).click();
    await page.getByRole('button', { name: '朗读当前故事' }).click();
    const duckState = await page.getByTestId('music-duck-state').textContent();
    expect(duckState).toMatch(/^(ducked|restored)$/);

    if (duckState === 'ducked') {
      await page.getByRole('button', { name: '用户手动暂停音乐' }).click();
      await page.getByRole('button', { name: '停止朗读' }).click();
      await expect(page.getByTestId('music-duck-state')).toHaveText('user_paused');
    }
  });

  test('completed browser speech returns controls to a resumable state', async ({ page }) => {
    await page.goto('/e2e-regression');
    await page.waitForLoadState('domcontentloaded');

    await page.getByRole('button', { name: '模拟音乐播放中' }).click();
    await page.getByRole('button', { name: '朗读当前故事' }).click();
    await expectBrowserSpeechAttempt(page);

    await page.getByRole('button', { name: '模拟朗读结束' }).click();

    await expect(page.getByTestId('voice-reading-state')).toHaveText('idle');
    await expect(page.getByRole('button', { name: '继续朗读' })).toBeVisible();
    await expect(page.getByTestId('music-duck-state')).toHaveText('restored');
  });

  test('pause and continue controls drive browser speech state', async ({ page }) => {
    await page.goto('/e2e-regression');
    await page.waitForLoadState('domcontentloaded');

    await page.getByRole('button', { name: '朗读当前故事' }).click();
    const state = await expectBrowserSpeechAttempt(page);
    if (state === 'failed') {
      await expect(page.getByRole('button', { name: '重试朗读' })).toBeVisible();
      return;
    }

    await page.getByRole('button', { name: '暂停朗读' }).click();
    await expect(page.getByTestId('voice-reading-state')).toHaveText('paused');

    await page.getByRole('button', { name: '继续朗读' }).click();
    await expect(page.getByTestId('voice-reading-state')).toHaveText('playing');
    await expect(page.getByTestId('voice-reading-mode')).toHaveText('browser_speech');
  });

  test('failure state is retryable without blocking other panels', async ({ page }) => {
    await page.addInitScript(() => {
      (window as typeof window & { __speechSpeakCount?: number }).__speechSpeakCount = 0;
      const speech = window.speechSynthesis;
      const originalSpeak = speech.speak.bind(speech);
      speech.speak = (utterance: SpeechSynthesisUtterance) => {
        (window as typeof window & { __speechSpeakCount?: number }).__speechSpeakCount =
          ((window as typeof window & { __speechSpeakCount?: number }).__speechSpeakCount ?? 0) + 1;
        originalSpeak(utterance);
      };
    });
    await page.goto('/e2e-regression');
    await page.waitForLoadState('domcontentloaded');

    await page.getByRole('button', { name: '模拟音乐播放中' }).click();
    await page.getByRole('button', { name: '朗读当前故事' }).click();
    const duckState = await page.getByTestId('music-duck-state').textContent();
    expect(duckState).toMatch(/^(ducked|restored)$/);

    await page.getByRole('button', { name: '模拟朗读失败' }).click();
    await expect(page.getByTestId('voice-reading-state')).toHaveText('failed');
    await expect(page.getByTestId('music-duck-state')).toHaveText('restored');
    await expect(page.getByRole('button', { name: '重试朗读' })).toBeVisible();

    await page.getByRole('button', { name: '重试朗读' }).click();
    await expectBrowserSpeechAttempt(page);
    await expect
      .poll(() =>
        page.evaluate(
          () => (window as typeof window & { __speechSpeakCount?: number }).__speechSpeakCount ?? 0
        )
      )
      .toBe(2);

    await page.getByRole('button', { name: '收集' }).click();
    await expect(page.getByRole('heading', { name: '苏小二' })).toBeVisible();
  });
});
