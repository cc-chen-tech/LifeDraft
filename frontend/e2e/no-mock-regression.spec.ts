import { test, expect } from '@playwright/test';

test.describe('no-mock regression coverage', () => {
  test('register sheet focuses the display name field when opened', async ({ page }) => {
    await page.goto('/');

    await page.getByRole('button', { name: '注册' }).click();

    await expect(page.getByPlaceholder('你的名字')).toBeFocused();
  });

  test('creation step indicators expose accessible names', async ({ page }) => {
    await page.goto('/create');

    await expect(page.getByRole('button', { name: '第 1 步：时代背景' })).toBeVisible();
    await expect(page.getByRole('button', { name: '第 2 步：年龄阶段' })).toBeVisible();
    await expect(page.getByRole('button', { name: '第 3 步：性别' })).toBeVisible();
    await expect(page.getByRole('button', { name: '第 4 步：世界观' })).toBeVisible();
    await expect(page.getByRole('button', { name: '第 5 步：人物形象' })).toBeVisible();
  });

  test('creation generation exits loading after backend success or failure', async ({ page }) => {
    await page.goto('/create');

    await page.getByPlaceholder('输入你的角色名').fill('陆明');
    await page.getByPlaceholder('描述你希望的人生方向...').fill('古代江湖，重视关系和悬疑推进');

    await expect
      .poll(
        async () => {
          const loadingVisible = await page.getByText('AI正在生成时代背景...').isVisible();
          const nextEnabled = await page.getByRole('button', { name: '下一步' }).isEnabled();
          const errorVisible = await page.getByText('生成失败，请重试').isVisible();
          return !loadingVisible && (nextEnabled || errorVisible);
        },
        {
          message: 'creation flow should not stay stuck in AI loading state',
          timeout: 70000,
        },
      )
      .toBe(true);
  });

  test('choice buttons expose stable accessible names', async ({ page }) => {
    await page.goto('/e2e-regression');

    await expect(
      page.getByRole('button', { name: '选择 1：追随江边脚印，查看雾中来客留下的痕迹。' }),
    ).toBeVisible();
    await expect(
      page.getByRole('button', { name: '选择 2：先回船舱取火折子，再探桥下暗影。' }),
    ).toBeVisible();
    await expect(page.getByRole('button', { name: '提交自定义选择' })).toBeVisible();
  });

  test('stream retry replaces active story attempt instead of duplicating it', async ({ page }) => {
    await page.goto('/e2e-regression');

    await page.getByRole('button', { name: '模拟首轮 stream' }).click();
    await expect(page.getByTestId('streamed-story')).toContainText('账册被人翻开');

    await page.getByRole('button', { name: '模拟 retry 替换' }).click();

    await expect(page.getByTestId('streamed-story')).toContainText('苏小二按住账册');
    await expect(page.getByTestId('streamed-story')).not.toContainText('账册被人翻开');
    await expect(page.getByTestId('streamed-story')).not.toContainText('retrying:');
  });

  test('collapsed bottom assistant only receives pointer events on its button', async ({ page }) => {
    await page.goto('/e2e-regression');

    const launcher = page.locator('[data-testid="chat-bar-launcher"]');
    await expect(launcher).toHaveClass(/pointer-events-none/);
    await expect(page.getByRole('button', { name: '打开剧情助手' })).toHaveClass(/pointer-events-auto/);
  });

  test('history review stays pinned to selected round with matching scene image state', async ({ page }) => {
    await page.goto('/e2e-regression');

    await page.getByRole('button', { name: '历史回顾' }).click();
    await page.getByRole('button', { name: '第 3 周 第 2 轮：码头边的对峙' }).click();

    await expect(page.getByTestId('history-story')).toContainText('码头边的对峙');
    await expect(page.getByTestId('history-scene-image-state')).toHaveText('week=3 round=2 stage=event');

    await page.getByRole('button', { name: '模拟当前故事更新' }).click();

    await expect(page.getByTestId('history-story')).toContainText('码头边的对峙');
    await expect(page.getByTestId('current-story')).toContainText('当前故事已经更新');
  });

  test('collection panel keeps data visible during background refresh', async ({ page }) => {
    await page.goto('/e2e-regression');

    await page.getByRole('button', { name: '收集' }).click();
    await expect(page.getByTestId('collection-refresh-state')).toHaveText('idle');
    await expect(page.getByRole('heading', { name: '苏小二' })).toBeVisible();

    await page.getByRole('button', { name: '刷新收集' }).click();

    await expect(page.getByTestId('collection-refresh-state')).toHaveText('refreshing');
    await expect(page.getByRole('heading', { name: '苏小二' })).toBeVisible();
    await expect(page.getByAltText('苏小二')).toBeVisible();
  });
});
