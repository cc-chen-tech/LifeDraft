import { test, expect } from '@playwright/test';
import { API_URL } from './helpers/auth';

test('credential and save icon controls expose stable names', async ({ page }) => {
  const displayName = `无障碍测试_${Date.now()}`;

  await page.goto('/');
  await page.getByRole('button', { name: '注册' }).click();
  await page.getByPlaceholder('你的名字').fill(displayName);
  await page.getByRole('button', { name: '创建账户' }).click();

  await expect(page.getByRole('button', { name: '复制私有密钥' })).toBeVisible();
  await page.getByRole('button', { name: '我已保存密钥，开始体验' }).click();

  const createResponse = await page.request.post(`${API_URL}/api/games`, {
    data: {
      player_name: '无障碍存档',
      life_vision: '验证无障碍交互名称',
      character_settings: {
        era: { name: '现代', period: '现代' },
        age: { age: 28, stage: '青年' },
        personality: { traits: ['务实'] },
        background: { occupation: '产品经理' },
      },
      language: 'zh',
    },
  });
  expect(createResponse.ok()).toBe(true);
  const created = await createResponse.json();

  await page.goto('/saves');
  await expect(
    page.getByRole('button', {
      name: `删除存档 无障碍存档（存档 ${created.game_id}）`,
    }),
  ).toBeVisible();
});
