/**
 * E2E Test: Character Settings Persistence
 *
 * 验证角色创建流程中，所有 character_settings 都被正确持久化到后端。
 * 核心测试：拦截 PATCH /api/games/{game_id}/character-settings 请求，
 * 验证 payload 包含 family/relationships/traits/wealth。
 *
 * 注意：此测试使用真实后端 API，不 mock。
 * 完整流程包含多次 LLM 调用，耗时约 2-5 分钟。
 */
import { test, expect } from '@playwright/test';

test.describe('Character Creation - Settings Persistence', () => {
  test.setTimeout(300_000);

  test('should persist all character settings through game creation flow', async ({ page }) => {
    // 记录所有 API 调用
    const apiCalls: Array<{ url: string; method: string; body?: unknown }> = [];

    await page.route('**/api/**', async (route) => {
      const request = route.request();
      const url = request.url();
      const method = request.method();

      if (method === 'POST' || method === 'PATCH') {
        try {
          const body = request.postDataJSON?.();
          apiCalls.push({ url, method, body });
        } catch {
          apiCalls.push({ url, method });
        }
      }

      await route.continue();
    });

    await page.goto('/create');

    // 1. 填写角色姓名
    const nameInput = page.getByPlaceholder(/角色名|姓名/i);
    await nameInput.waitFor({ state: 'visible' });
    await nameInput.fill('持久化测试');

    // 2. 依次通过 4 个手动步骤：era -> age -> gender -> world
    // 每个步骤：等待内容生成 -> 点击"下一步"
    for (let step = 0; step < 4; step++) {
      // 等待当前步骤的 AI 生成完成（setting 内容出现）
      // 第一次页面加载时 era 可能已经生成，后续步骤需要等待
      await page.waitForTimeout(step === 0 ? 3000 : 10000);

      // 点击"下一步"保存当前 setting 并进入下一步
      const nextButton = page.getByRole('button', { name: /下一步/i }).first();
      await nextButton.waitFor({ state: 'visible' });

      // 等待按钮可用（生成完成后才可用）
      let retries = 0;
      while (!(await nextButton.isEnabled()) && retries < 30) {
        await page.waitForTimeout(1000);
        retries++;
      }

      await nextButton.click();
    }

    // 3. 现在应该在 portrait 步骤，等待后台 auto-generation 完成
    // auto-generation 完成后会显示 CompletionScreen，其中包含"开始游戏"按钮
    const startButton = page.getByRole('button', { name: /开始游戏/i });
    await startButton.waitFor({ state: 'visible', timeout: 180_000 });

    // 4. 点击"开始游戏"
    await startButton.click();

    // 5. 等待导航到 opening story
    await page.waitForURL('/story/opening', { timeout: 30_000 });

    // 6. 等待 PATCH 请求完成
    await page.waitForTimeout(3000);

    // 7. 验证 PATCH /character-settings 被调用
    const patchCalls = apiCalls.filter(
      (c) => c.method === 'PATCH' && c.url.includes('/character-settings')
    );

    expect(patchCalls.length, 'PATCH /character-settings 应该被调用').toBeGreaterThanOrEqual(1);

    const patchPayload = patchCalls[0].body as Record<string, unknown> | undefined;
    expect(patchPayload, 'PATCH payload 不应为空').toBeTruthy();
    expect(patchPayload?.character_settings, 'payload 应包含 character_settings').toBeTruthy();

    // 8. 验证 auto-generated 字段存在
    const cs = patchPayload?.character_settings as Record<string, unknown> | undefined;
    expect(cs).toBeTruthy();
    expect(cs).toHaveProperty('family');
    expect(cs).toHaveProperty('relationships');
    expect(cs).toHaveProperty('traits');
    expect(cs).toHaveProperty('wealth');

    // 9. 验证手动步骤的字段也存在
    expect(cs).toHaveProperty('era');
    expect(cs).toHaveProperty('age');
    expect(cs).toHaveProperty('gender');
    expect(cs).toHaveProperty('world');
  });
});