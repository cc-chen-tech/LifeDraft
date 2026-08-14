import { test, expect } from '@playwright/test';
import {
  FRONTEND_ORIGIN,
  installStoryOriginGenerationFixture,
} from './helpers/character-setting-fixture';

test.describe('no-mock regression coverage', () => {
  test('register sheet focuses the display name field when opened', async ({ page }) => {
    await page.goto('/');

    await page.getByRole('button', { name: '注册' }).click();

    await expect(page.getByPlaceholder('你的名字')).toBeFocused();
  });

  test('creation step indicators expose accessible names', async ({ page }) => {
    await page.goto('/create');

    const stepNavigation = page.getByRole('navigation', { name: '角色创建步骤' });
    const currentStep = stepNavigation.getByRole('button', { name: '前往故事起点' });
    await expect(currentStep).toBeVisible();
    await expect(currentStep).toHaveAttribute('aria-current', 'step');
    await expect(currentStep).toBeDisabled();

    for (const name of ['性别', '世界观', '人物形象']) {
      const futureStep = stepNavigation.getByRole('button', { name: `前往${name}` });
      await expect(futureStep).toBeVisible();
      await expect(futureStep).toBeDisabled();
      await expect(futureStep).not.toHaveAttribute('aria-current', 'step');
    }
  });

  test('creation generation uses calm loading and exits after backend success', async ({ page }) => {
    const requests = await installStoryOriginGenerationFixture(page, 500);
    await page.goto('/create');

    const nameInput = page.getByPlaceholder('输入你的角色名');
    const visionInput = page.getByPlaceholder('描述你希望的人生方向...');
    await expect(nameInput).toBeEditable();
    await expect(visionInput).toBeEditable();
    await visionInput.fill('古代江湖，重视关系和悬疑推进');
    await nameInput.fill('陆明');
    await expect(nameInput).toHaveValue('陆明');
    await expect(visionInput).toHaveValue('古代江湖，重视关系和悬疑推进');

    const loading = page.getByRole('status');
    await expect(
      loading.getByRole('heading', { name: '角色设定，正在成形' }),
    ).toBeVisible();
    await expect(loading).toContainText('正在写作');

    await expect(page.getByText('刚刚生成')).toBeVisible();
    await expect(page.getByRole('button', { name: '下一步' })).toBeEnabled();
    expect(requests).toEqual([
      {
        method: 'POST',
        origin: FRONTEND_ORIGIN,
        path: '/api/character/story-origin',
        search: '',
      },
    ]);
  });

  test('choice buttons expose stable accessible names', async ({ page }) => {
    await page.goto('/e2e-regression');
    const choicesFixture = page.getByRole('region', { name: '选项可访问名称回归夹具' });

    await expect(
      choicesFixture.getByRole('button', { name: '选择 1：追随江边脚印，查看雾中来客留下的痕迹。' }),
    ).toBeVisible();
    await expect(
      choicesFixture.getByRole('button', { name: '选择 2：先回船舱取火折子，再探桥下暗影。' }),
    ).toBeVisible();
    await expect(choicesFixture.getByRole('button', { name: '提交自定义选择' })).toBeVisible();
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
    await expect(page.getByRole('button', { name: '打开聊天' })).toHaveClass(/pointer-events-auto/);
  });

  test('normal browser pointer clicks still reach midweek choices near the opened chat control', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/e2e-regression');

    await page.getByRole('button', { name: '打开聊天' }).click();
    await expect(page.locator('[data-testid="chat-bar-panel"]')).toBeVisible();

    await page
      .getByRole('region', { name: '周中浏览器点击回归夹具' })
      .evaluate((element) => element.scrollIntoView({ block: 'start' }));

    const targetChoice = page.getByRole('button', {
      name: '选择 1：周中先追问账册来源，再决定是否赴约。',
    });
    await expect(targetChoice).toBeVisible();
    await expect(page.getByTestId('normal-click-choice')).toHaveText('none');

    await targetChoice.evaluate((element) => (element as HTMLButtonElement).click());
    await expect(page.getByTestId('normal-click-choice')).toHaveText('midweek-source');
    await page
      .getByTestId('reset-normal-click-choice')
      .evaluate((element) => (element as HTMLButtonElement).click());
    await expect(page.getByTestId('normal-click-choice')).toHaveText('none');

    const box = await targetChoice.boundingBox();
    expect(box).not.toBeNull();
    const clickPoint = {
      x: box!.x + box!.width / 2,
      y: box!.y + box!.height / 2,
    };

    const hitTarget = await page.evaluate(
      ({ x, y }) => {
        const element = document.elementFromPoint(x, y);
        const button = element?.closest('button');
        return {
          directTagName: element?.tagName ?? '',
          role: button?.getAttribute('role') ?? '',
          ariaLabel: button?.getAttribute('aria-label') ?? '',
          testId: element?.getAttribute('data-testid') ?? '',
          tagName: button?.tagName ?? '',
        };
      },
      clickPoint,
    );

    expect(hitTarget).toMatchObject({
      tagName: 'BUTTON',
      ariaLabel: '选择 1：周中先追问账册来源，再决定是否赴约。',
    });

    await page.mouse.click(clickPoint.x, clickPoint.y);

    await expect(page.getByTestId('normal-click-choice')).toHaveText('midweek-source');
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

  test('collection panel surfaces auto-collected recognized story entities', async ({ page }) => {
    await page.goto('/e2e-regression');

    await page.getByRole('button', { name: '收集' }).click();

    await expect(page.getByTestId('auto-collection-state')).toHaveText('collected');
    await expect(page.getByRole('heading', { name: '赵掌柜' })).toBeVisible();
    await expect(page.getByText('铜钥匙')).toBeVisible();
  });
});
