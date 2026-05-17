import { test, expect } from '@playwright/test';
import { registerUser } from './helpers/auth';

test.describe('Story voice reading', () => {
  test.beforeEach(async ({ context }) => {
    const user = await registerUser(context, `VoiceReader_${Date.now()}`);
    expect(user).not.toBeNull();
  });

  test('reads current and historical story text through the backend asset API', async ({ page }) => {
    await page.goto('/e2e-regression');
    await page.waitForLoadState('domcontentloaded');

    await page.getByRole('button', { name: '朗读当前故事' }).click();
    await expect(page.getByTestId('voice-reading-source')).toHaveText('current_story');
    await expect(page.getByTestId('voice-reading-state')).toHaveText('playing');
    await expect(page.getByTestId('voice-reading-job')).toHaveText(/^\d+$/);
    await expect(page.getByTestId('voice-reading-audio-url')).toContainText(
      '/api/voice-reading/audio/'
    );
    await expect(page.getByTestId('voice-reading-audio-player')).toHaveJSProperty(
      'readyState',
      4
    );
    await expect
      .poll(async () =>
        page.getByTestId('voice-reading-audio-player').evaluate((element) => {
          const audio = element as HTMLAudioElement;
          return Number.isFinite(audio.duration) && audio.duration > 0;
        })
      )
      .toBe(true);
    await expect(page.getByRole('button', { name: '暂停朗读' })).toBeVisible();
    await expect(page.getByRole('button', { name: '停止朗读' })).toBeVisible();

    await page.getByRole('button', { name: '历史回顾' }).click();
    await page.getByRole('button', { name: '第 3 周 第 2 轮：码头边的对峙' }).click();
    await page.getByRole('button', { name: '朗读历史故事' }).click();

    await expect(page.getByTestId('voice-reading-source')).toHaveText('history_round');
    await expect(page.getByTestId('voice-reading-context')).toContainText('week=3 round=2 stage=event');
    await expect(page.getByTestId('voice-reading-job')).toHaveText(/^\d+$/);
    await expect(page.getByTestId('voice-reading-audio-url')).toContainText(
      '/api/voice-reading/audio/'
    );
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
    await expect(page.getByTestId('music-duck-state')).toHaveText('ducked');

    await page.getByRole('button', { name: '用户手动暂停音乐' }).click();
    await page.getByRole('button', { name: '停止朗读' }).click();
    await expect(page.getByTestId('music-duck-state')).toHaveText('user_paused');
  });

  test('failure state is retryable without blocking other panels', async ({ page }) => {
    await page.goto('/e2e-regression');
    await page.waitForLoadState('domcontentloaded');

    await page.getByRole('button', { name: '模拟朗读失败' }).click();
    await expect(page.getByTestId('voice-reading-state')).toHaveText('failed');
    await expect(page.getByRole('button', { name: '重试朗读' })).toBeVisible();

    await page.getByRole('button', { name: '收集' }).click();
    await expect(page.getByRole('heading', { name: '苏小二' })).toBeVisible();
  });
});
