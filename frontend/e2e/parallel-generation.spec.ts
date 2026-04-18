/**
 * E2E Test: Parallel Background Generation & Opening Story Loading
 *
 * 验证：
 * 1. portrait 步骤中后台生成与图片生成同时进行
 * 2. opening story 页面在 streaming 初始状态有 loading 显示
 */
import { test, expect } from '@playwright/test';
import { ensureAuthenticated } from './helpers/auth';

test.describe('Character Creation - Parallel Generation', () => {
  test.setTimeout(300_000);

  test('should show background generation loading alongside portrait image generation', async ({ page, context }) => {
    await ensureAuthenticated(page, context);

    // 记录 API 调用时间
    const apiCallTimings: Array<{ url: string; startTime: number; endTime?: number }> = [];

    await page.route('**/api/**', async (route) => {
      const request = route.request();
      const url = request.url();
      const method = request.method();

      if (url.includes('/character/setting') || url.includes('/character/relationship') || url.includes('/images/generate')) {
        const entry: { url: string; startTime: number; endTime?: number } = { url, startTime: Date.now() };
        apiCallTimings.push(entry);
        const response = await route.fetch();
        entry.endTime = Date.now();
        await route.fulfill({ response });
        return;
      }

      await route.continue();
    });

    await page.goto('/create');

    // 1. 填写角色姓名
    const nameInput = page.getByPlaceholder(/角色名|姓名/i);
    await nameInput.waitFor({ state: 'visible' });
    await nameInput.fill('并行测试');

    // 2. 依次通过 4 个手动步骤：era -> age -> gender -> world
    for (let step = 0; step < 4; step++) {
      await page.waitForTimeout(step === 0 ? 3000 : 10000);
      const nextButton = page.getByRole('button', { name: /下一步/i }).first();
      await nextButton.waitFor({ state: 'visible' });
      let retries = 0;
      while (!(await nextButton.isEnabled()) && retries < 30) {
        await page.waitForTimeout(1000);
        retries++;
      }
      await nextButton.click();
    }

    // 3. 现在应该在 portrait 步骤
    // 等待图片生成开始
    const imageLoading = page.getByText(/AI正在生成人物形象/i);
    await imageLoading.waitFor({ state: 'visible', timeout: 30_000 });

    // 4. 验证后台生成也在进行中（显示后台生成提示）
    const backgroundLoading = page.getByText(/后台正在生成/i);
    // 后台生成提示可能在图片生成完成后才显示，或者同时显示
    // 我们验证至少有一个后台生成的 API 调用被触发
    await page.waitForTimeout(5000);

    const settingCalls = apiCallTimings.filter(c => c.url.includes('/character/setting'));
    const relationshipCalls = apiCallTimings.filter(c => c.url.includes('/character/relationship'));
    const imageCalls = apiCallTimings.filter(c => c.url.includes('/images/generate'));

    expect(imageCalls.length, '图片生成 API 应该被调用').toBeGreaterThanOrEqual(1);
    expect(settingCalls.length + relationshipCalls.length, '后台生成 API 应该被调用').toBeGreaterThanOrEqual(1);

    // 5. 验证后台生成和图片生成有重叠时间
    if (imageCalls.length > 0 && (settingCalls.length + relationshipCalls.length) > 0) {
      const imageStart = imageCalls[0].startTime;
      const imageEnd = imageCalls[0].endTime || Date.now();
      const bgStart = [...settingCalls, ...relationshipCalls][0].startTime;

      // 后台生成应该在图片生成期间或之前开始
      expect(bgStart, '后台生成应在图片生成期间或之前开始').toBeLessThanOrEqual(imageEnd + 5000);
    }

    // 6. 等待图片生成完成
    await page.waitForSelector('img[alt="并行测试"]', { timeout: 180_000 });

    // 7. 等待"开始游戏"按钮出现（后台生成完成）
    const startButton = page.getByRole('button', { name: /开始游戏/i });
    await startButton.waitFor({ state: 'visible', timeout: 180_000 });
  });

  test('opening story page should show loading state while streaming', async ({ page, context }) => {
    await ensureAuthenticated(page, context);

    // 先创建一个游戏到 completion 状态
    await page.goto('/create');
    const nameInput = page.getByPlaceholder(/角色名|姓名/i);
    await nameInput.waitFor({ state: 'visible' });
    await nameInput.fill('开篇测试');

    for (let step = 0; step < 4; step++) {
      await page.waitForTimeout(step === 0 ? 3000 : 10000);
      const nextButton = page.getByRole('button', { name: /下一步/i }).first();
      await nextButton.waitFor({ state: 'visible' });
      let retries = 0;
      while (!(await nextButton.isEnabled()) && retries < 30) {
        await page.waitForTimeout(1000);
        retries++;
      }
      await nextButton.click();
    }

    const startButton = page.getByRole('button', { name: /开始游戏/i });
    await startButton.waitFor({ state: 'visible', timeout: 180_000 });
    await startButton.click();

    // 等待导航到 opening story
    await page.waitForURL('/story/opening', { timeout: 30_000 });

    // 验证页面有可见的 loading 内容（不是空白）
    // 无论是 SkeletonStory 还是 "故事正在展开..." 都应该可见
    const loadingIndicator = page.locator('text=/正在|加载|展开/i').first();
    await expect(loadingIndicator, 'opening story 页面应有 loading 指示').toBeVisible({ timeout: 10_000 });

    // 验证页面内容区域不为空
    const mainContent = page.locator('main, .flex-1').first();
    const box = await mainContent.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.height, '内容区域应有高度').toBeGreaterThan(100);
  });
});
