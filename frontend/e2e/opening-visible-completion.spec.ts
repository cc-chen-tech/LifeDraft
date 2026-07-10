import { test, expect } from '@playwright/test';

test('opening start waits for backend and visible text completion', async ({ page }) => {
  await page.goto('/e2e-regression');
  const fixture = page.getByRole('region', { name: '开场完成门控回归夹具' });
  const start = fixture.getByRole('button', { name: '开始我的人生' });

  await expect(start).toBeDisabled();
  await fixture.getByRole('button', { name: '模拟后端完成' }).click();
  await expect(start).toBeDisabled();
  await expect(fixture.getByTestId('opening-visible-text')).toHaveText('正在显示最终句子');

  await fixture.getByRole('button', { name: '模拟显示完成' }).click();
  await expect(fixture.getByTestId('opening-visible-text')).toHaveText('最终句子已经完整显示。');
  await expect(start).toBeEnabled();
});
