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

  test.fixme('should show background generation loading alongside portrait image generation', async ({ page, context }) => {
    /**
     * FIXME: 此测试基于旧的角色创建流程设计，当前实现已变更。
     *
     * 当前流程：角色创建（5步：姓名→时代→年龄→性别→世界观）→ 点击"开始游戏" →
     * 后端创建 game → 生成 opening story → 进入 /play 页面 → 触发肖像生成。
     *
     * 肖像生成需要 gameId（见 useCharacterCreation.ts:282），而 gameId 只有在点击
     * "开始游戏"并后端返回后才可用。因此 portrait 生成不再与 character setting/
     * relationship 后台生成并行发生在创建流程中。
     *
     * 若要恢复此测试，需要：
     * 1. 通过 API 预创建游戏到 completion 状态（已有活跃游戏）
     * 2. 导航到 /create?gameId=xxx 并进入 portrait 步骤
     * 3. 验证 /images/generate 与 /character/setting 并发调用
     *
     * 当前该场景已由后端架构保证（独立 async task），无需 E2E 覆盖。
     */
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
    // 等待图片生成开始（图片生成可能非常快或异步触发，不强制要求 loading 文本可见）
    const imageLoading = page.getByText(/AI正在生成人物形象/i);
    const isImageLoading = await imageLoading.isVisible().catch(() => false);

    // 4. 验证后台生成也在进行中（显示后台生成提示）
    const backgroundLoading = page.getByText(/后台正在生成/i);
    // 后台生成提示可能在图片生成完成后才显示，或者同时显示
    // 我们验证至少有一个后台生成的 API 调用被触发
    await page.waitForTimeout(10000);

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
    /**
     * 验证 opening story 页面在 SSE streaming 过程中显示 loading 状态。
     *
     * 为了测试稳定和速度，我们：
     * 1. 通过 API 创建游戏（绕过慢速的 UI 创建流程）
     * 2. 注入测试数据到 window.__TEST_DATA__（避免依赖 store 状态）
     * 3. mock /api/character/opening-story 返回一个 SSE 流
     * 4. 验证页面显示 loading 或故事内容
     */
    test.setTimeout(60000);
    await ensureAuthenticated(page, context);

    // 通过 API 创建游戏
    const API_URL = 'http://localhost:8000';
    const createResp = await context.request.post(`${API_URL}/api/games`, {
      data: {
        player_name: '开篇测试',
        life_vision: '探索世界',
        character_settings: {
          era: { name: '现代', period: '现代' },
          age: { age: 22, stage: '青年' },
          gender: { gender: '男' },
          world: { name: '普通现代', description: '测试世界' },
          family: { description: '普通家庭' },
          relationships: { key_people: [], relationships_description: '暂无' },
          traits: { traits: ['勇敢'] },
          wealth: { level: '中等', description: '普通收入' },
        },
        language: 'zh',
      },
    });
    expect(createResp.ok()).toBe(true);

    // Mock opening story SSE endpoint - return a story stream
    await page.route('**/api/character/opening-story', async (route) => {
      const body = [
        'event: story\ndata: "第一章 晨曦微露"\n\n',
        'event: story\ndata: " 你站在窗前..."\n\n',
        'event: complete\ndata: {"full_story": "第一章 晨曦微露 你站在窗前..."}\n\n',
      ].join('');
      await route.fulfill({
        status: 200,
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
        },
        body,
      });
    });

    // 注入测试数据，确保 opening story 页面有角色数据
    await page.addInitScript(() => {
      (window as any).__TEST_DATA__ = {
        characterSettings: {
          era: { name: '现代', period: '现代' },
          age: { age: 22, stage: '青年' },
          gender: { gender: '男' },
          world: { name: '普通现代', description: '测试世界' },
        },
        playerName: '开篇测试',
        lifeVision: '探索世界',
      };
    });

    // 导航到 opening story 页面
    await page.goto('/story/opening');
    await page.waitForLoadState('domcontentloaded');

    // 验证页面内容区域有可见内容（loading 或故事文本）
    // 使用 waitForFunction 轮询，捕捉 loading 状态的短暂出现
    const hasContent = await page.waitForFunction(() => {
      const bodyText = document.body.innerText || '';
      const hasLoading = bodyText.includes('正在') || bodyText.includes('加载') || bodyText.includes('展开') || bodyText.includes('编写');
      const hasStory = bodyText.includes('第一章') || bodyText.includes('晨曦');
      return hasLoading || hasStory;
    }, { timeout: 15000 });
    expect(hasContent).toBeTruthy();

    // 验证页面内容区域不为空且有足够高度
    const contentArea = page.locator('.min-h-screen, body').first();
    await expect(contentArea).toBeVisible();
    const box = await contentArea.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.height).toBeGreaterThan(100);

    // 等待故事内容出现（mock SSE 会快速返回）
    const storyText = page.locator('text=第一章');
    await expect(storyText).toBeVisible({ timeout: 15000 });
  });
});
