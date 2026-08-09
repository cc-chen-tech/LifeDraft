import { test, expect } from '@playwright/test';
import { ensureAuthenticated, API_URL } from './helpers/auth';
import { openPlayTools } from './helpers/play-tools';

test('realistic modern setup selects nonfiction instead of cyberpunk', async ({ page, context }) => {
  await ensureAuthenticated(page, context);
  const response = await context.request.post(`${API_URL}/api/games`, {
    data: {
      player_name: '现实风格角色',
      life_vision: '现实主义产品经理成长，不要超自然或赛博朋克',
      character_settings: {
        era: { year: 2026, era_description: '当代上海现实主义职场，不使用未来科技设定' },
        world: {
          world_description: '与现实世界一致，明确无超自然元素、禁止赛博朋克',
          technology_level: '现实中的人工智能产品、企业网络和办公软件',
          social_system: '现实法律和商业制度',
        },
        background: { occupation: '产品经理' },
        traits: { personality: ['务实', '理性'] },
      },
      language: 'zh',
    },
  });
  expect(response.ok()).toBe(true);
  const game = await response.json();

  await page.goto(`/play?gameId=${game.game_id}`);
  const toolsDialog = await openPlayTools(page);
  await toolsDialog.getByRole('button', { name: '叙事风格', exact: true }).click();

  await expect(toolsDialog.getByRole('radio', { name: /非虚构小说/ })).toBeChecked();
  await expect(toolsDialog.getByRole('radio', { name: /赛博朋克/ })).not.toBeChecked();
});
