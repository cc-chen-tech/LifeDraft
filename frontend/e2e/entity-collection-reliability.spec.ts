import { expect, test } from '@playwright/test';
import { ensureActiveGame } from './helpers/auth';

test('recognized entity add leaves blocking state after the real durable response', async ({ page, context }) => {
  const gameId = await ensureActiveGame(page, context, { player_name: '实体可靠性测试角色' });

  await page.goto(`/e2e-regression?entityCollectionAdd=1&gameId=${gameId}`);
  await page.getByRole('button', { name: '添加识别实体' }).click();

  await expect(page.getByTestId('entity-add-state')).toHaveText('saved', { timeout: 15_000 });
  await expect(page.getByText('添加中...')).not.toBeVisible();

  const response = await page.request.get(`/api/collection/${gameId}/details`);
  expect(response.ok()).toBeTruthy();
  const collection = await response.json();
  expect(collection.characters.map((entry: { name: string }) => entry.name)).toContain('陈远');
  expect(collection.items.map((entry: { name: string }) => entry.name)).toContain('银色戒指');
});
