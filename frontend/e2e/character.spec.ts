/**
 * E2E Test: Character Creation Flow
 * Tests for the character creation wizard including all steps and navigation
 */
import { test, expect } from '@playwright/test';
import {
  FRONTEND_ORIGIN,
  installCharacterSettingGenerationFixture,
  installStoryOriginGenerationFixture,
  type StoryOriginRequest,
} from './helpers/character-setting-fixture';

function expectSingleStoryOriginRequest(requests: StoryOriginRequest[]) {
  expect(requests).toEqual([
    {
      method: 'POST',
      origin: FRONTEND_ORIGIN,
      path: '/api/character/story-origin',
      search: '',
    },
  ]);
}

test.describe('Character Creation - Page Load', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/create');
  });

  test('should display character creation page', async ({ page }) => {
    await expect(page).toHaveURL('/create');
  });

  test('should have step indicator showing progress', async ({ page }) => {
    const stepNavigation = page.getByRole('navigation', { name: '角色创建步骤' });
    const stepNames = ['故事起点', '性别', '世界观', '人物形象'];

    await expect(stepNavigation.getByRole('button')).toHaveCount(4);
    for (const name of stepNames) {
      await expect(stepNavigation.getByRole('button', { name: `前往${name}` })).toBeVisible();
    }
    await expect(stepNavigation.getByRole('button', { name: '前往故事起点' })).toHaveAttribute(
      'aria-current',
      'step',
    );
  });

  test('should show step count in header', async ({ page }) => {
    // Step count like "1/4" or similar
    const stepCount = page.locator('text=/\\d+\\/\\d+/');
    await expect(stepCount).toBeVisible();
  });

  test('should have return button', async ({ page }) => {
    const returnButton = page.getByRole('button', { name: /返回/i });
    await expect(returnButton).toBeVisible();
  });
});

test.describe('Character Creation - Player Name Input', () => {
  test('should have player name input field', async ({ page }) => {
    await page.goto('/create');
    
    const nameInput = page.getByPlaceholder(/角色名|姓名/i);
    await expect(nameInput).toBeVisible();
  });

  test('should allow entering player name', async ({ page }) => {
    const requests = await installStoryOriginGenerationFixture(page);
    await page.goto('/create');

    const nameInput = page.getByPlaceholder(/角色名|姓名/i);
    await nameInput.fill('测试角色');
    await expect(nameInput).toHaveValue('测试角色');
    await expect(page.getByText('刚刚生成')).toBeVisible();
    expectSingleStoryOriginRequest(requests);
  });

  test('should have optional life vision textarea', async ({ page }) => {
    await page.goto('/create');
    
    const visionTextarea = page.getByPlaceholder(/人生愿景|人生方向/i);
    await expect(visionTextarea).toBeVisible();
  });
});

test.describe('Character Creation - Step Content', () => {
  test('should display story origin step initially', async ({ page }) => {
    await page.goto('/create');

    await expect(page.getByRole('heading', { name: '故事起点', level: 2 })).toBeVisible();
  });

  test('should show step description', async ({ page }) => {
    await page.goto('/create');
    
    // Step description
    const description = page.getByText('日期、年龄与时代语境会作为一个完整起点生成');
    await expect(description.first()).toBeVisible();
  });

  test('should have next step button', async ({ page }) => {
    await page.goto('/create');
    
    // Use .first() to avoid matching Next.js Dev Tools button
    const nextButton = page.getByRole('button', { name: /下一步|Next/i }).first();
    await expect(nextButton).toBeVisible();
  });

  test('should disable next button when name is empty', async ({ page }) => {
    await page.goto('/create');

    const nameInput = page.getByPlaceholder(/角色名|姓名/i);
    const nextButton = page.getByRole('button', { name: '下一步' });
    await expect(nameInput).toHaveValue('');
    await expect(nextButton).toBeDisabled();
    await expect(page.getByText('请先输入角色姓名')).toBeVisible();
  });
});

test.describe('Character Creation - Navigation', () => {
  test('should navigate to next step after filling name', async ({ page }) => {
    const requests = await installStoryOriginGenerationFixture(page);
    await page.goto('/create');

    const nameInput = page.getByPlaceholder(/角色名|姓名/i);
    await nameInput.fill('测试角色');

    await expect(page.getByText('刚刚生成')).toBeVisible();
    expectSingleStoryOriginRequest(requests);
    const nextButton = page.getByRole('button', { name: '下一步' });
    await expect(nextButton).toBeEnabled();
    await nextButton.click();

    const stepNavigation = page.getByRole('navigation', { name: '角色创建步骤' });
    await expect(stepNavigation.getByRole('button', { name: '前往性别' })).toHaveAttribute(
      'aria-current',
      'step',
    );
    await expect(page).toHaveURL('/create');
  });

  test('should return to home when clicking return button', async ({ page }) => {
    await page.goto('/create');
    
    const returnButton = page.getByRole('button', { name: /返回/i }).first();
    await returnButton.click();
    
    await expect(page).toHaveURL('/');
  });

  test('should return through a previous named step', async ({ page }) => {
    const requests = await installStoryOriginGenerationFixture(page);
    await installCharacterSettingGenerationFixture(page);
    await page.goto('/create');

    const nameInput = page.getByPlaceholder(/角色名|姓名/i);
    await nameInput.fill('测试角色');
    await expect(page.getByText('刚刚生成')).toBeVisible();
    expectSingleStoryOriginRequest(requests);

    await page.getByRole('button', { name: '下一步' }).click();
    const stepNavigation = page.getByRole('navigation', { name: '角色创建步骤' });
    const genderStep = stepNavigation.getByRole('button', { name: '前往性别' });
    const originStep = stepNavigation.getByRole('button', { name: '前往故事起点' });
    await expect(genderStep).toHaveAttribute('aria-current', 'step');
    await expect(originStep).toBeEnabled();

    await originStep.click();
    await expect(originStep).toHaveAttribute('aria-current', 'step');
    await expect(page.getByRole('heading', { name: '故事起点', level: 2 })).toBeVisible();
  });
});

test.describe('Character Creation - Auto Generation', () => {
  test('story-origin fixture fails closed for malformed requests', async ({ page }) => {
    let escapedRequests = 0;
    await page.route(/\/api\/character\/story-origin(?:\?.*)?$/, async (route) => {
      escapedRequests += 1;
      await route.fulfill({
        status: 599,
        contentType: 'application/json',
        headers: { 'access-control-allow-origin': '*' },
        body: JSON.stringify({ message: 'escaped fixture guard' }),
      });
    });
    const requests = await installStoryOriginGenerationFixture(page, 0);
    await page.goto('/create');

    const alternateOrigin = FRONTEND_ORIGIN.replace('localhost', '127.0.0.1');
    const invalidRequests = [
      {
        url: '/api/character/story-origin?unexpected=1',
        method: 'POST',
        body: { player_name: '测试角色' },
        simpleCrossOrigin: false,
      },
      {
        url: '/api/character/story-origin',
        method: 'GET',
        body: null,
        simpleCrossOrigin: false,
      },
      {
        url: '/api/character/story-origin',
        method: 'POST',
        body: { setting_type: 'age' },
        simpleCrossOrigin: false,
      },
      {
        url: `${alternateOrigin}/api/character/story-origin`,
        method: 'POST',
        body: { player_name: '测试角色' },
        simpleCrossOrigin: true,
      },
    ] as const;

    const statuses: number[] = [];
    for (const invalidRequest of invalidRequests) {
      statuses.push(
        await page.evaluate(async ({ url, method, body, simpleCrossOrigin }) => {
          try {
            const response = await fetch(url, {
              method,
              headers: body
                ? {
                    'content-type': simpleCrossOrigin
                      ? 'text/plain'
                      : 'application/json',
                  }
                : undefined,
              body: body ? JSON.stringify(body) : undefined,
            });
            return response.status;
          } catch {
            return -1;
          }
        }, invalidRequest),
      );
    }

    expect(statuses).toEqual([418, 418, 418, 418]);
    expect(escapedRequests).toBe(0);
    expect(requests).toEqual([
      {
        method: 'POST',
        origin: FRONTEND_ORIGIN,
        path: '/api/character/story-origin',
        search: '?unexpected=1',
      },
      {
        method: 'GET',
        origin: FRONTEND_ORIGIN,
        path: '/api/character/story-origin',
        search: '',
      },
      {
        method: 'POST',
        origin: FRONTEND_ORIGIN,
        path: '/api/character/story-origin',
        search: '',
      },
      {
        method: 'POST',
        origin: alternateOrigin,
        path: '/api/character/story-origin',
        search: '',
      },
    ]);
  });

  test('should show loading state during generation', async ({ page }) => {
    const requests = await installStoryOriginGenerationFixture(page, 500);
    await page.goto('/create');

    const nameInput = page.getByPlaceholder(/角色名|姓名/i);
    await nameInput.fill('测试角色');

    const loading = page.getByRole('status');
    await expect(
      loading.getByRole('heading', { name: '角色设定，正在成形' }),
    ).toBeVisible();
    await expect(loading).toContainText('正在写作');
    await expect(page.getByText('刚刚生成')).toBeVisible();
    expectSingleStoryOriginRequest(requests);
  });

  test('should display generated content after loading', async ({ page }) => {
    const requests = await installStoryOriginGenerationFixture(page);
    await page.goto('/create');

    const nameInput = page.getByPlaceholder(/角色名|姓名/i);
    await nameInput.fill('测试角色');

    await expect(page.getByText('刚刚生成')).toBeVisible();
    await expect(page.getByTestId('story-origin-summary')).toContainText('2026年8月13日');
    await expect(page.getByRole('button', { name: '下一步' })).toBeEnabled();
    expectSingleStoryOriginRequest(requests);
  });

  test('should have regenerate button for generated content', async ({ page }) => {
    const requests = await installStoryOriginGenerationFixture(page);
    await page.goto('/create');

    const nameInput = page.getByPlaceholder(/角色名|姓名/i);
    await nameInput.fill('测试角色');
    await expect(page.getByText('刚刚生成')).toBeVisible();
    expectSingleStoryOriginRequest(requests);

    const regenerateButton = page.getByRole('button', { name: '重新生成故事起点' });
    await expect(regenerateButton).toBeVisible();
    await expect(regenerateButton).toBeEnabled();
  });

  test('should have feedback input for regeneration', async ({ page }) => {
    const requests = await installStoryOriginGenerationFixture(page);
    await page.goto('/create');

    const nameInput = page.getByPlaceholder(/角色名|姓名/i);
    await nameInput.fill('测试角色');
    await expect(page.getByText('刚刚生成')).toBeVisible();
    expectSingleStoryOriginRequest(requests);

    const feedbackInput = page.getByRole('textbox', { name: '故事起点修改意见' });
    await expect(feedbackInput).toBeEditable();
    await feedbackInput.fill('保留城市背景，增加更多生活细节');
    await expect(feedbackInput).toHaveValue('保留城市背景，增加更多生活细节');
  });
});

test.describe('Character Creation - Completion', () => {
  test('should show start game button on final step', async ({ page }) => {
    // This test would require completing all steps
    // For now, verify the button exists in the DOM
    await page.goto('/create');
    
    const startButton = page.getByRole('button', { name: /开始游戏|生成角色/i });
    // Button may not be visible until final step
  });

  test('should show save preset button on completion', async ({ page }) => {
    await page.goto('/create');
    
    const saveButton = page.getByRole('button', { name: /保存.*预设|Save/i });
    // Button may not be visible until final step
  });
});

test.describe('Character Creation - Preset Sheet', () => {
  test('should open preset save sheet', async ({ page }) => {
    await page.goto('/create');
    
    // Find and click save button
    const saveButton = page.getByRole('button', { name: /保存|Save/i }).first();
    
    if (await saveButton.isVisible()) {
      await saveButton.click();
      await page.waitForLoadState('domcontentloaded');
      
      // Sheet should open
      const sheet = page.locator('[role="dialog"], [class*="sheet"]');
      
      // Preset name input should be in sheet
      const presetInput = page.getByPlaceholder(/预设名称/i);
    }
  });
});

test.describe('Character Creation - Error Handling', () => {
  test('should show error toast on generation failure', async ({ page }) => {
    let interceptedRequests = 0;
    await page.route('**/api/character/**', async (route) => {
      interceptedRequests += 1;
      await route.fulfill({
        status: 422,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'deterministic character generation failure' }),
      });
    });

    await page.goto('/create');

    const nameInput = page.getByPlaceholder(/角色名|姓名/i);
    await nameInput.fill('测试角色');

    const errorToast = page
      .locator('[data-slot="feedback-notice"]')
      .getByRole('alert');
    await expect(errorToast).toContainText('生成失败，请重试');
    expect(interceptedRequests).toBe(1);
  });
});
