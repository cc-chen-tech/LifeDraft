import { expect, test, type Page } from '@playwright/test';

const ancientOrigin = {
  revision: 1,
  start_date: '0960-01-01',
  starting_age: 20,
  era_description: '北宋初年的州城',
  life_stage_description: '初入成年的人生阶段',
  world_context: '驿路与坊市连接地方社会',
};

const modernOrigin = {
  revision: 2,
  start_date: '2026-08-13',
  starting_age: 28,
  era_description: '2020年代中期的现代都市',
  life_stage_description: '职业发展逐渐进入稳定探索期',
  world_context: 'AI工具与数字内容行业快速变化',
};

async function installCreationRoutes(page: Page) {
  let originCalls = 0;
  let worldCalls = 0;
  const patchBodies: Array<Record<string, unknown>> = [];
  const portraitRevisions: Array<number | undefined> = [];
  const worldPreviousSettings: Array<Record<string, unknown>> = [];

  await page.route('**/api/character/story-origin', async (route) => {
    originCalls += 1;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(originCalls === 1 ? ancientOrigin : modernOrigin),
    });
  });
  await page.route('**/api/character/setting', async (route) => {
    const body = route.request().postDataJSON() as Record<string, unknown>;
    const settingType = String(body.setting_type);
    let response: Record<string, unknown>;
    if (settingType === 'gender') {
      response = { gender: '女', gender_description: '女性' };
    } else if (settingType === 'world') {
      worldCalls += 1;
      worldPreviousSettings.push(
        (body.previous_settings as Record<string, unknown>) ?? {},
      );
      response = worldCalls === 1
        ? { world_type: '历史现实', world_description: '旧州城世界' }
        : { world_type: '现代现实', world_description: '新都市世界' };
    } else if (settingType === 'family') {
      response = { family_description: '旧起点生成的家庭背景' };
    } else {
      response = { traits_description: '旧起点生成的性格' };
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(response),
    });
  });
  let personIndex = 0;
  await page.route('**/api/character/relationship', async (route) => {
    personIndex += 1;
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        name: `旧人物${personIndex}`,
        role: '旧关系',
        relationship: '来自旧起点的关系',
      }),
    });
  });
  await page.route('**/api/character/relationships-summary', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ relationships_description: '旧起点生成的人际关系' }),
    }),
  );
  await page.route('**/api/games', (route) => {
    if (route.request().method() !== 'POST') return route.continue();
    return route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        game_id: 701,
        player_state: {},
        progress: {},
        round_info: {},
        current_event: null,
        constraint_level: 'expert',
      }),
    });
  });
  await page.route('**/api/games/701/story-origin', async (route) => {
    patchBodies.push(route.request().postDataJSON() as Record<string, unknown>);
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        story_origin: modernOrigin,
        timeline: {
          version: 2,
          start_date: modernOrigin.start_date,
          current_date: modernOrigin.start_date,
          day_index: 0,
          day_number: 1,
          completed_days: 0,
          week_number: 1,
          weekday: 4,
          total_days: 672,
        },
        character_settings: {
          story_origin: modernOrigin,
          start_date: modernOrigin.start_date,
          era: {
            year: 2026,
            era_description: modernOrigin.era_description,
            world_context: modernOrigin.world_context,
          },
          age: {
            age: 28,
            birth_year: 1998,
            age_description: modernOrigin.life_stage_description,
          },
          gender: { gender: '女', gender_description: '女性' },
        },
      }),
    });
  });
  await page.route('**/api/images/character/generate-async', async (route) => {
    const body = route.request().postDataJSON() as {
      extra_context?: { origin_revision?: number };
    };
    portraitRevisions.push(body.extra_context?.origin_revision);
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        job_id: portraitRevisions.length,
        game_id: 701,
        status: 'failed',
        image_id: null,
        attempt_count: 1,
        error_code: 'fixture',
        error_message: '测试夹具不生成图片',
      }),
    });
  });

  return { patchBodies, portraitRevisions, worldPreviousSettings };
}

test('four-step origin flow replaces the complete chronology and invalidates old dependents', async ({ page }) => {
  const evidence = await installCreationRoutes(page);
  await page.goto('/create');

  const stepNames = ['故事起点', '性别', '世界观', '人物形象'];
  for (const name of stepNames) {
    await expect(page.getByRole('button', { name: `前往${name}` })).toBeVisible();
  }
  await expect(page.locator('input[type="date"], input[type="number"]')).toHaveCount(0);
  await expect(page.getByRole('button', { name: /前往时代背景|前往年龄阶段/ })).toHaveCount(0);

  await page.getByPlaceholder('输入你的角色名').fill('阿衡');
  await expect(page.getByTestId('story-origin-summary')).toContainText('960年1月1日');
  await expect(page.getByTestId('story-origin-summary')).toContainText('20岁');
  await expect(page.getByText('出生年份')).toHaveCount(0);
  await page.getByRole('button', { name: '下一步' }).click();

  await expect(page.getByRole('heading', { name: '性别' })).toBeVisible();
  await expect(page.getByText('女性')).toBeVisible();
  await page.getByRole('button', { name: '下一步' }).click();

  await expect(page.getByRole('heading', { name: '世界观' })).toBeVisible();
  await expect(page.getByText('旧州城世界')).toBeVisible();
  await page.getByRole('button', { name: '下一步' }).click();

  await expect(page.getByRole('heading', { name: '人物形象' })).toBeVisible();
  await page.getByRole('button', { name: /继续生成角色/ }).click();
  await expect(page.getByRole('heading', { name: '角色设定完成' })).toBeVisible();
  await expect(page.getByTestId('story-origin-summary')).toContainText('960年1月1日');

  await page.getByRole('button', { name: '修改故事起点' }).click();
  await page.getByLabel('故事起点修改意见').fill('从960年、20岁改为2026年8月13日、28岁');
  await page.getByRole('button', { name: '重新生成故事起点' }).click();
  await expect(page.getByTestId('story-origin-summary')).toContainText('2026年8月13日');
  await expect(page.getByTestId('story-origin-summary')).toContainText('28岁');
  await page.getByRole('button', { name: '下一步' }).click();

  await expect(page.getByRole('heading', { name: '世界观' })).toBeVisible();
  await expect(page.getByText('新都市世界')).toBeVisible();
  expect(evidence.patchBodies).toEqual([
    { expected_revision: 1, story_origin: modernOrigin },
  ]);
  const replacementContext = evidence.worldPreviousSettings.at(-1) ?? {};
  expect(replacementContext).not.toHaveProperty('family');
  expect(replacementContext).not.toHaveProperty('relationships');
  expect(replacementContext).not.toHaveProperty('traits');
  expect(replacementContext).not.toHaveProperty('character_images');

  await page.getByRole('button', { name: '下一步' }).click();
  await expect(page.getByRole('heading', { name: '人物形象' })).toBeVisible();
  await expect.poll(() => evidence.portraitRevisions).toEqual([1, 2]);
});

test('a conflicting legacy preset opens at story-origin review instead of completion', async ({ page }) => {
  await page.route('**/api/presets', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          preset_id: 91,
          preset_name: '年代冲突预设',
          player_name: '旧角色',
          life_vision: '进入现代内容行业',
          created_at: '2026-08-13T00:00:00Z',
          character_settings: {
            story_origin: {
              ...ancientOrigin,
              start_date: '2026-08-13',
              era_description: '公元960年的州城',
            },
            story_origin_needs_review: true,
            start_date: '2026-08-13',
            era: { year: 2026, era_description: '公元960年的州城' },
            age: { age: 20, birth_year: 2006 },
            world: { world_description: '不能直接沿用的旧世界' },
          },
        },
      ]),
    }),
  );

  await page.goto('/presets');
  await page.getByRole('button', { name: '使用角色预设“年代冲突预设”' }).click();

  await expect(page).toHaveURL(/\/create$/);
  await expect(page.getByRole('heading', { name: '故事起点' })).toBeVisible();
  await expect(page.getByText('1/4')).toBeVisible();
  await expect(page.getByTestId('story-origin-summary')).toContainText('2026年8月13日');
  await expect(page.getByTestId('story-origin-summary')).toContainText('公元960年的州城');
  await expect(page.getByRole('heading', { name: '角色设定完成' })).toHaveCount(0);
});
