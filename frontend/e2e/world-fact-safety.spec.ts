import { test, expect } from '@playwright/test';
import { ensureAuthenticated, API_URL } from './helpers/auth';

test('qualified world claims remain visible through real API state and browser display', async ({
  page,
  context,
}) => {
  await ensureAuthenticated(page, context);
  const qualifier = '故事设定假设，不代表现实法规或统计：';
  const response = await context.request.post(`${API_URL}/api/games`, {
    data: {
      player_name: '世界事实边界角色',
      life_vision: '现实主义教育科技产品经理成长',
      character_settings: {
        era: { year: 2026, era_description: '当代中国现实主义' },
        world: {
          world_description: `${qualifier}需要取得数据隐私保护认证（DSR）。`,
          technology_level: `${qualifier}备案周期固定为4-6个月。`,
          social_system: '遵循现实社会的一般制度。',
          economy: `${qualifier}风险投资同比下降40%。`,
        },
      },
      language: 'zh',
    },
  });
  expect(response.ok()).toBe(true);
  const game = await response.json();

  await page.goto(`/e2e-regression?worldFact=1&gameId=${game.game_id}`);
  const panel = page.getByRole('region', { name: '世界事实边界回归夹具' });

  await expect(panel).toBeVisible();
  await expect(panel.getByText(/故事设定假设，不代表现实法规或统计/).first()).toBeVisible();
  await expect(panel.getByText(/数据隐私保护认证（DSR）/)).toBeVisible();
  await expect(panel.getByText(/风险投资同比下降40%/)).toBeVisible();
});
