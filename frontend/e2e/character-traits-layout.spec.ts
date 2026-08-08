import { test, expect, type Page } from '@playwright/test';

async function expectLongTraitRowsContained(page: Page) {
  const fixture = page.getByRole('region', { name: '角色特质布局回归夹具' });
  const list = fixture.getByRole('list', { name: '角色特质' });
  const rows = list.getByRole('listitem');

  await expect(rows).toHaveCount(5);
  const listBox = await list.boundingBox();
  expect(listBox).not.toBeNull();

  for (const row of await rows.all()) {
    await expect(row).toBeVisible();
    const rowBox = await row.boundingBox();
    expect(rowBox).not.toBeNull();
    expect(rowBox!.x).toBeGreaterThanOrEqual(listBox!.x);
    expect(rowBox!.x + rowBox!.width).toBeLessThanOrEqual(listBox!.x + listBox!.width + 1);
    expect(rowBox!.width).toBeGreaterThanOrEqual(listBox!.width - 1);
    expect(await row.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
  }
}

for (const viewport of [
  { name: 'desktop', width: 1280, height: 720 },
  { name: '375px mobile', width: 375, height: 667 },
]) {
  test(`${viewport.name} contains long character traits in five full-width rows`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.goto('/e2e-regression?traitsLayout=1');

    await expectLongTraitRowsContained(page);
  });
}
