import { test, expect } from '@playwright/test';

test('regeneration clears stale narration and old music target', async ({ page }) => {
  await page.goto('/e2e-regression?audioRegeneration=1');
  const fixture = page.getByRole('region', { name: '音频重新生成状态回归夹具' });

  await fixture.getByRole('button', { name: '模拟旧故事朗读' }).click();
  await expect(fixture.getByTestId('audio-regeneration-reading-state')).toHaveText('playing');
  await expect(fixture.getByTestId('audio-regeneration-music-target')).toHaveText('旧故事文本');

  await fixture.getByRole('button', { name: '开始重新生成' }).click();
  await expect(fixture.getByTestId('audio-regeneration-reading-state')).toHaveText('idle');
  await expect(fixture.getByTestId('audio-regeneration-audio-url')).toHaveText('none');
  await expect(fixture.getByTestId('audio-regeneration-music-target')).toHaveText('none');
  await expect(fixture.getByTestId('audio-regeneration-auto-ready')).toHaveText('false');
});
