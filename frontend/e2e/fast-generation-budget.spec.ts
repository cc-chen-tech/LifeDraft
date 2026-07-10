import { test, expect } from '@playwright/test';

test('fast generation progress shows budget-derived stage and expectation', async ({ page }) => {
  await page.goto('/e2e-regression?fastProgress=1');
  const progress = page.getByRole('status', { name: '快速生成进度' });

  await expect(progress).toBeVisible();
  await expect(progress.getByText('快速生成中')).toBeVisible();
  await expect(progress.getByText(/已等待 12 秒/)).toBeVisible();
  await expect(progress.getByText(/通常 20-45 秒/)).toBeVisible();
});
