import { expect, test } from '@playwright/test';

test.describe('Atomic relationship regeneration', () => {
  test('invalid candidate keeps old content and never persists', async ({ page }) => {
    let summaryCalls = 0;
    let patchCalls = 0;
    await page.route('**/api/character/relationship', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }),
    );
    await page.route('**/api/character/relationships-summary', (route) => {
      summaryCalls += 1;
      return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
    });
    await page.route('**/api/games/901/character-settings', (route) => {
      patchCalls += 1;
      return route.fulfill({ status: 200, contentType: 'application/json', body: '{"success":true}' });
    });

    await page.goto('/e2e-regression?relationshipRegeneration=1');
    await expect(page.getByText(/旧关系摘要/)).toBeVisible();
    await page.getByRole('button', { name: '给人际关系反馈重新生成' }).click();
    await page.getByTestId('relationships-feedback-input').fill('保留陈晓峰的原职业');
    await page.getByRole('button', { name: '重新生成人际关系' }).click();

    await expect(
      page.getByText('人际关系生成结果不完整，已保留原设定'),
    ).toBeVisible();
    await expect(page.getByText(/旧关系摘要/)).toBeVisible();
    await expect(page.getByTestId('relationships-feedback-input')).toHaveValue('保留陈晓峰的原职业');
    expect(summaryCalls).toBe(0);
    expect(patchCalls).toBe(0);
  });

  test('valid candidate persists once and then replaces the visible relationship data', async ({ page }) => {
    const people = [
      { name: '陈晓峰', role: '前同事', relationship: '仍在原公司全职任职' },
      { name: '周丽', role: '律师', relationship: '继续提供法律咨询' },
    ];
    let personCalls = 0;
    const patchPayloads: unknown[] = [];
    await page.route('**/api/character/relationship', async (route) => {
      const requestBody = route.request().postDataJSON();
      expect(requestBody.feedback).toBe('保留陈晓峰的原职业');
      expect(requestBody.existing_people).toEqual(people.slice(0, personCalls));
      const person = people[personCalls++];
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(person),
      });
    });
    await page.route('**/api/character/relationships-summary', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ relationships_description: '新关系摘要：职业与合作关系保持一致。' }),
      }),
    );
    await page.route('**/api/games/901/character-settings', async (route) => {
      patchPayloads.push(route.request().postDataJSON());
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: '{"success":true,"message":"saved"}',
      });
    });

    await page.goto('/e2e-regression?relationshipRegeneration=1');
    await page.getByRole('button', { name: '给人际关系反馈重新生成' }).click();
    await page.getByTestId('relationships-feedback-input').fill('保留陈晓峰的原职业');
    await page.getByRole('button', { name: '重新生成人际关系' }).click();

    await expect(page.getByText('新关系摘要：职业与合作关系保持一致。')).toBeVisible();
    await expect(page.getByText(/旧关系摘要/)).toHaveCount(0);
    expect(personCalls).toBe(2);
    expect(patchPayloads).toEqual([
      {
        character_settings: {
          relationships: {
            relationships_description: '新关系摘要：职业与合作关系保持一致。',
            key_people: people,
          },
        },
      },
    ]);
  });
});
