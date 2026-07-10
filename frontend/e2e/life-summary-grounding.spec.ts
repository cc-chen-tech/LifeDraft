import { test, expect } from '@playwright/test';

test('grounded life summary panel shows exact range and supports close interaction', async ({ page }) => {
  await page.goto('/e2e-regression?lifeSummary=1');
  const fixture = page.getByRole('region', { name: '人生总结事实边界回归夹具' });

  await fixture.getByRole('button', { name: '打开已校验人生总结' }).click();
  const panel = page.getByRole('dialog', { name: '人生总结' });
  await expect(panel).toBeVisible();
  await expect(panel.getByText(/第1-4周/)).toBeVisible();
  await expect(panel).not.toContainText('半年');
  await expect(panel).not.toContainText('精力');
  await expect(panel).not.toContainText('情绪');
  await expect(panel).not.toContainText('学识');
  await expect(panel).not.toContainText('财富');
  await panel.getByRole('button', { name: '关闭人生总结' }).click();
  await expect(panel).toBeHidden();
});
