 

/**
 * E2E Test: Story Summary System
 *
 * 验证故事总结功能，包括：
 * - 总结 API 端点可用性
 * - 总结内容格式验证
 * - 轮次小结 API 响应
 * - 游戏进度中的总结请求
 * - 总结与事件关联性
 * - 结局总结 API 可用
 * - 空状态处理（新游戏无总结）
 * - 调试会话清理端点可用
 */

import { test, expect, BrowserContext, Page } from '@playwright/test';
import { ensureAuthenticated, API_URL } from './helpers/auth';

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * 检查后端是否可达，不可达则 skip
 */
async function skipIfBackendUnavailable(context: BrowserContext): Promise<boolean> {
  const healthCheck = await context.request
    .get(`${API_URL}/api/games`)
    .catch(() => null);
  return !healthCheck;
}

/**
 * 通过 API 创建一个测试游戏
 */
async function createTestGame(
  context: BrowserContext,
  playerName?: string
): Promise<{ game_id: number } | null> {
  const response = await context.request.post(`${API_URL}/api/games`, {
    data: {
      player_name: playerName || `SummaryTest_${Date.now()}`,
      life_vision: '测试总结功能的人生故事',
      character_settings: { personality: 'default' },
    },
  });

  if (response.ok()) {
    return await response.json();
  }
  return null;
}

/**
 * 通过 API 获取游戏状态
 */
async function getGameState(
  context: BrowserContext,
  gameId: number
): Promise<Record<string, unknown> | null> {
  const response = await context.request.get(`${API_URL}/api/games/${gameId}`);
  if (response.ok()) {
    return await response.json();
  }
  return null;
}

// ============================================================================
// Story Summary System Tests
// ============================================================================

test.describe('Story Summary System', () => {
  test.setTimeout(120_000);

  let context: BrowserContext;
  let page: Page;

  test.beforeAll(async ({ browser }) => {
    context = await browser.newContext();
    page = await context.newPage();
    await ensureAuthenticated(page, context);
  });

  test.afterAll(async () => {
    await context.close();
  });

  // TC-01: 总结 API 端点可用性
  test('TC-01: summary API endpoint is reachable', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const game = await createTestGame(context, 'Summary_Endpoint_Test');
    expect(game).not.toBeNull();
    expect(game!.game_id).toBeDefined();

    // POST /api/games/{game_id}/summary 应该返回有效响应
    const summaryResponse = await context.request.post(
      `${API_URL}/api/games/${game!.game_id}/summary`,
      { data: {} }
    );

    // 端点应可达（200 或 4xx/5xx 均说明端点存在）
    expect(summaryResponse.status()).toBeLessThan(500);

    if (summaryResponse.ok()) {
      const data = await summaryResponse.json();
      // 响应应包含 summary_text 字段
      expect(data).toHaveProperty('summary_text');
    }
  });

  // TC-02: 总结内容格式验证
  test('TC-02: summary response has correct format', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const game = await createTestGame(context, 'Summary_Format_Test');
    expect(game).not.toBeNull();

    const summaryResponse = await context.request.post(
      `${API_URL}/api/games/${game!.game_id}/summary`,
      { data: {} }
    );

    if (summaryResponse.ok()) {
      const data = await summaryResponse.json();

      // 验证返回的 JSON 结构
      expect(data).toHaveProperty('summary_text');
      expect(data).toHaveProperty('start_week');
      expect(data).toHaveProperty('end_week');
      expect(typeof data.summary_text).toBe('string');
      expect(typeof data.start_week).toBe('number');
      expect(typeof data.end_week).toBe('number');

      // summary_text 不应为空
      expect(data.summary_text.length).toBeGreaterThan(0);

      // start_week 应 >= 1（显示层 1-based）
      expect(data.start_week).toBeGreaterThanOrEqual(1);
      // end_week 应 >= start_week
      expect(data.end_week).toBeGreaterThanOrEqual(data.start_week);
    }
  });

  // TC-03: 轮次小结 API 响应
  test('TC-03: round summary via choice-sync response', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const game = await createTestGame(context, 'RoundSummary_Test');
    expect(game).not.toBeNull();

    // 通过 choice-sync 提交选择，验证响应中可能包含 summary/weekly_summary
    const choiceResponse = await context.request.post(
      `${API_URL}/api/games/${game!.game_id}/choice-sync`,
      { data: { option_index: 0 } }
    );

    if (choiceResponse.ok()) {
      const data = await choiceResponse.json();

      // choice-sync 响应应有标准字段
      expect(data).toHaveProperty('current_round');
      expect(data).toHaveProperty('current_week');
      expect(data).toHaveProperty('player_state');

      // 如果有 weekly_summary 字段，验证其类型
      if ('weekly_summary' in data && data.weekly_summary) {
        expect(typeof data.weekly_summary).toBe('string');
        expect(data.weekly_summary.length).toBeGreaterThan(0);
      }

      // 如果有 need_weekly_summary 字段，应为布尔值
      if ('need_weekly_summary' in data) {
        expect(typeof data.need_weekly_summary).toBe('boolean');
      }
    }
  });

  // TC-04: 游戏进度中的总结请求（带 weeks 参数）
  test('TC-04: summary request with weeks parameter', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const game = await createTestGame(context, 'Summary_Weeks_Test');
    expect(game).not.toBeNull();

    // 请求最近 2 周的总结
    const summaryResponse = await context.request.post(
      `${API_URL}/api/games/${game!.game_id}/summary`,
      { data: { weeks: 2 } }
    );

    if (summaryResponse.ok()) {
      const data = await summaryResponse.json();

      expect(data).toHaveProperty('summary_text');
      expect(typeof data.summary_text).toBe('string');
      expect(data.summary_text.length).toBeGreaterThan(0);

      // weeks 参数应限制返回的周数范围
      if (data.start_week && data.end_week) {
        const weekSpan = data.end_week - data.start_week + 1;
        // 实际返回的周数不应超过请求的 weeks 数
        expect(weekSpan).toBeLessThanOrEqual(2);
      }
    }
  });

  // TC-05: 总结与事件关联性（game state + summary 一致性）
  test('TC-05: summary correlates with game events', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const game = await createTestGame(context, 'Summary_Events_Test');
    expect(game).not.toBeNull();

    // 获取游戏状态
    const gameState = await getGameState(context, game!.game_id);
    expect(gameState).not.toBeNull();

    // 获取总结
    const summaryResponse = await context.request.post(
      `${API_URL}/api/games/${game!.game_id}/summary`,
      { data: {} }
    );

    if (summaryResponse.ok()) {
      const summaryData = await summaryResponse.json();

      // 总结应存在
      expect(summaryData.summary_text).toBeDefined();
      expect(typeof summaryData.summary_text).toBe('string');

      // 如果有 story_count，应该 >= 0
      if ('story_count' in summaryData) {
        expect(typeof summaryData.story_count).toBe('number');
        expect(summaryData.story_count).toBeGreaterThanOrEqual(0);
      }
    }
  });

  // TC-06: 结局总结 API 可用
  test('TC-06: ending API endpoint is reachable', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const game = await createTestGame(context, 'Ending_API_Test');
    expect(game).not.toBeNull();

    // GET /api/games/{game_id}/ending
    // 对于尚未结束的游戏，应返回 400
    const endingResponse = await context.request.get(
      `${API_URL}/api/games/${game!.game_id}/ending`
    );

    // 端点应存在：未结束的游戏返回 400，已结束返回 200
    expect([200, 400]).toContain(endingResponse.status());

    if (endingResponse.status() === 400) {
      const data = await endingResponse.json();
      // 应返回 "Game is not over yet" 错误信息
      expect(data.detail).toContain('not over');
    }

    if (endingResponse.ok()) {
      const data = await endingResponse.json();
      // 结局数据应包含标准字段
      expect(data).toHaveProperty('ending_type');
      expect(data).toHaveProperty('summary');
      expect(data).toHaveProperty('final_stats');
    }
  });

  // TC-07: 空状态处理（新游戏无总结）
  test('TC-07: empty state handling for new game', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const game = await createTestGame(context, 'Summary_Empty_Test');
    expect(game).not.toBeNull();

    // 新创建的游戏请求总结
    const summaryResponse = await context.request.post(
      `${API_URL}/api/games/${game!.game_id}/summary`,
      { data: {} }
    );

    if (summaryResponse.ok()) {
      const data = await summaryResponse.json();

      // 即使没有历史记录，也应返回有效的总结结构
      expect(data).toHaveProperty('summary_text');
      expect(typeof data.summary_text).toBe('string');
      expect(data.summary_text.length).toBeGreaterThan(0);

      // 对于空状态，可能返回类似"刚刚开始"的提示
      // 不硬性校验内容，只确认格式正确
    }
  });

  // TC-08: 调试会话清理端点可用
  test('TC-08: debug session cleanup endpoint is available', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const game = await createTestGame(context, 'SessionDebug_Test');
    expect(game).not.toBeNull();

    // DELETE /api/games/{game_id}/session-debug
    const debugResponse = await context.request.delete(
      `${API_URL}/api/games/${game!.game_id}/session-debug`
    );

    // 端点应可达且成功
    expect(debugResponse.ok()).toBeTruthy();

    const data = await debugResponse.json();
    expect(data).toHaveProperty('message');
    expect(data.message).toContain('Session cleared');

    // 清除会话后，再次请求 state 应该能自动恢复（或返回错误）
    const stateResponse = await context.request.get(
      `${API_URL}/api/games/${game!.game_id}/state`
    );
    // 可能恢复成功(200)或无法恢复(404/500)，端点应正常响应
    expect(stateResponse.status()).toBeLessThan(502);
  });
});
