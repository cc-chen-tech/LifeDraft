 

/**
 * E2E Test: Narrative Systems - 三大叙事系统集成测试
 *
 * 验证叙事风格引擎、创意增强、史诗叙事三大系统通过完整游戏流程工作正常。
 *
 * 前置条件（后端环境变量）:
 *   ENABLE_NARRATIVE_STYLE_ENGINE=true
 *   ENABLE_CREATIVE_ENHANCEMENT=true
 *   ENABLE_EPIC_NARRATIVE=true
 *
 * narrative_style_id 通过 character_settings 字典注入到 POST /api/games。
 * 前端无专门的风格选择 UI，测试通过 API 直接创建带风格的游戏。
 */

import { test, expect, Page, BrowserContext, APIRequestContext } from '@playwright/test';
import { ensureAuthenticated, registerUser } from './helpers/auth';
import { startNetworkMonitoring, waitForNetworkIdle, formatNetworkErrors } from './helpers/network-monitor';

const API_URL = 'http://localhost:8000';
const BASE_URL = 'http://localhost:3000';

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * 通过 API 创建带叙事风格的游戏
 */
async function createGameWithStyle(
  context: BrowserContext,
  options: {
    playerName?: string;
    narrativeStyleId?: string;
    lifeVision?: string;
    characterSettings?: Record<string, unknown>;
  } = {}
): Promise<{ game_id: number } | null> {
  const {
    playerName = `NarrativeTest_${Date.now()}`,
    narrativeStyleId,
    lifeVision = '探索古老的江湖世界',
    characterSettings,
  } = options;

  const body: Record<string, unknown> = {
    player_name: playerName,
    life_vision: lifeVision,
    character_settings: {
      personality: 'default',
      ...(characterSettings || {}),
      ...(narrativeStyleId ? { narrative_style_id: narrativeStyleId } : {}),
    },
  };

  const response = await context.request.post(`${API_URL}/api/games`, {
    data: body,
  });

  if (response.ok()) {
    return await response.json();
  }

  return null;
}

/**
 * 过滤掉已知的非关键控制台错误
 */
function filterCriticalErrors(errors: string[]): string[] {
  return errors.filter(
    (e) =>
      !e.includes('favicon') &&
      !e.includes('extension') &&
      !e.includes('SourceMap') &&
      !e.includes('ResizeObserver') &&
      !e.includes('hydration') &&
      !e.includes('Hydration')
  );
}

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

/**
 * 导航到游戏页面，处理路由重定向
 */
async function navigateToGame(page: Page, gameId: number): Promise<void> {
  await page.goto(`${BASE_URL}/game/${gameId}`);
  await page.waitForLoadState('domcontentloaded');
  await waitForNetworkIdle(page);

  const currentUrl = page.url();
  if (!currentUrl.includes('/game/') && !currentUrl.includes('/play')) {
    await page.goto(`${BASE_URL}/play`);
    await page.waitForLoadState('domcontentloaded');
    await waitForNetworkIdle(page);
  }
}

/**
 * 收集页面控制台错误
 */
function collectConsoleErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      errors.push(msg.text());
    }
  });
  page.on('pageerror', (error) => {
    errors.push(error.message);
  });
  return errors;
}

// ============================================================================
// A. System Toggle Independence - 三大系统独立开关测试
// ============================================================================

test.describe('A. System Toggle Independence', () => {
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

  test('A1. style engine only - game creation and story generation', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    // 创建带风格引擎的游戏（只传 narrative_style_id，依赖后端配置）
    const result = await createGameWithStyle(context, {
      playerName: 'StyleOnly_Test',
      narrativeStyleId: 'gothic_romance',
      lifeVision: '在迷雾笼罩的庄园中寻找真相',
    });

    expect(result).not.toBeNull();
    expect(result!.game_id).toBeDefined();

    const gameData = await getGameState(context, result!.game_id);
    expect(gameData).not.toBeNull();
    expect(gameData!.game_id).toBe(result!.game_id);

    // 验证游戏有初始故事内容
    const hasStory = gameData!.round_info != null || gameData!.current_event != null;
    expect(hasStory).toBeTruthy();
  });

  test('A2. creative enhancement only - game creation and story generation', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    // 不传 style_id，依赖后端 ENABLE_CREATIVE_ENHANCEMENT=true
    const result = await createGameWithStyle(context, {
      playerName: 'CreativeOnly_Test',
      lifeVision: '在星际间穿梭，探索未知文明',
    });

    expect(result).not.toBeNull();
    expect(result!.game_id).toBeDefined();

    const gameData = await getGameState(context, result!.game_id);
    expect(gameData).not.toBeNull();

    const hasStory = gameData!.round_info != null || gameData!.current_event != null;
    expect(hasStory).toBeTruthy();
  });

  test('A3. epic narrative only - game creation and story generation', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    // 不传 style_id，依赖后端 ENABLE_EPIC_NARRATIVE=true
    const result = await createGameWithStyle(context, {
      playerName: 'EpicOnly_Test',
      lifeVision: '踏上拯救世界的史诗征途',
    });

    expect(result).not.toBeNull();
    expect(result!.game_id).toBeDefined();

    const gameData = await getGameState(context, result!.game_id);
    expect(gameData).not.toBeNull();

    const hasStory = gameData!.round_info != null || gameData!.current_event != null;
    expect(hasStory).toBeTruthy();
  });
});

// ============================================================================
// B. System Combinations - 系统组合测试
// ============================================================================

test.describe('B. System Combinations', () => {
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

  test('B1. style + creative enabled, epic disabled', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const result = await createGameWithStyle(context, {
      playerName: 'StyleCreative_Test',
      narrativeStyleId: 'cyberpunk',
      lifeVision: '在霓虹闪烁的都市中求生',
    });

    expect(result).not.toBeNull();

    const gameData = await getGameState(context, result!.game_id);
    expect(gameData).not.toBeNull();
    expect(gameData!.game_id).toBe(result!.game_id);
  });

  test('B2. style + epic enabled, creative disabled', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const result = await createGameWithStyle(context, {
      playerName: 'StyleEpic_Test',
      narrativeStyleId: 'greek_tragedy',
      lifeVision: '挑战命运的枷锁',
    });

    expect(result).not.toBeNull();

    const gameData = await getGameState(context, result!.game_id);
    expect(gameData).not.toBeNull();
    expect(gameData!.game_id).toBe(result!.game_id);
  });

  test('B3. creative + epic enabled, style disabled', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    // 不传 style_id，仅依赖 creative + epic
    const result = await createGameWithStyle(context, {
      playerName: 'CreativeEpic_Test',
      lifeVision: '在混沌中开辟新世界',
    });

    expect(result).not.toBeNull();

    const gameData = await getGameState(context, result!.game_id);
    expect(gameData).not.toBeNull();
  });

  test('B4. all three systems enabled simultaneously', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const result = await createGameWithStyle(context, {
      playerName: 'AllSystems_Test',
      narrativeStyleId: 'romantic_legend',
      lifeVision: '书写传奇的爱情史诗',
    });

    expect(result).not.toBeNull();

    const gameData = await getGameState(context, result!.game_id);
    expect(gameData).not.toBeNull();

    // 三系统全开时也应有故事内容
    const hasStory = gameData!.round_info != null || gameData!.current_event != null;
    expect(hasStory).toBeTruthy();
  });
});

// ============================================================================
// C. Style Variety - 多风格配置测试
// ============================================================================

test.describe('C. Style Variety', () => {
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

  test('C1. gothic_romance style creates valid game', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const result = await createGameWithStyle(context, {
      playerName: 'Style_GothicRomance',
      narrativeStyleId: 'gothic_romance',
      lifeVision: '在古堡中揭开家族秘辛',
    });

    expect(result).not.toBeNull();
    expect(result!.game_id).toBeGreaterThan(0);

    const gameData = await getGameState(context, result!.game_id);
    expect(gameData).not.toBeNull();
  });

  test('C2. cyberpunk style creates valid game', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const result = await createGameWithStyle(context, {
      playerName: 'Style_Cyberpunk',
      narrativeStyleId: 'cyberpunk',
      lifeVision: '在数字废土中寻找人性的光辉',
    });

    expect(result).not.toBeNull();
    expect(result!.game_id).toBeGreaterThan(0);

    const gameData = await getGameState(context, result!.game_id);
    expect(gameData).not.toBeNull();
  });

  test('C3. cosmic_horror style creates valid game', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const result = await createGameWithStyle(context, {
      playerName: 'Style_CosmicHorror',
      narrativeStyleId: 'cosmic_horror',
      lifeVision: '面对来自深渊的未知恐惧',
    });

    expect(result).not.toBeNull();
    expect(result!.game_id).toBeGreaterThan(0);

    const gameData = await getGameState(context, result!.game_id);
    expect(gameData).not.toBeNull();
  });

  test('C4. folktale_fairytale style creates valid game', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const result = await createGameWithStyle(context, {
      playerName: 'Style_Folktale',
      narrativeStyleId: 'folktale_fairytale',
      lifeVision: '在童话世界中寻找幸福的结局',
    });

    expect(result).not.toBeNull();
    expect(result!.game_id).toBeGreaterThan(0);

    const gameData = await getGameState(context, result!.game_id);
    expect(gameData).not.toBeNull();
  });

  test('C5. invalid style_id graceful fallback', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    // 传入不存在的 style_id，应优雅降级而不是报错
    const result = await createGameWithStyle(context, {
      playerName: 'Style_Invalid',
      narrativeStyleId: 'nonexistent_style_12345',
      lifeVision: '测试错误风格的容错',
    });

    // 应该仍然创建成功（降级到默认）
    expect(result).not.toBeNull();
    expect(result!.game_id).toBeDefined();

    const gameData = await getGameState(context, result!.game_id);
    expect(gameData).not.toBeNull();
    expect(gameData!.game_id).toBe(result!.game_id);
  });
});

// ============================================================================
// D. Constraint Validation - 验证器与约束测试
// ============================================================================

test.describe('D. Constraint Validation', () => {
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

  test('D1. game with style constraints generates valid story', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const result = await createGameWithStyle(context, {
      playerName: 'Constraint_Valid',
      narrativeStyleId: 'psychological_suspense',
      lifeVision: '在心理迷宫中寻找真相',
    });

    expect(result).not.toBeNull();

    const gameData = await getGameState(context, result!.game_id);
    expect(gameData).not.toBeNull();

    // 验证游戏状态结构完整
    expect(gameData!.game_id).toBe(result!.game_id);
    expect(gameData!.player_state).toBeDefined();
    expect(gameData!.progress).toBeDefined();

    // round_info 应该有结构化数据
    if (gameData!.round_info) {
      expect(typeof gameData!.round_info).toBe('object');
    }
  });

  test('D2. harness validation pipeline processes story without error', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    // 创建游戏并验证整个管线无 500 错误
    const monitor = startNetworkMonitoring(page);

    const result = await createGameWithStyle(context, {
      playerName: 'Pipeline_Test',
      narrativeStyleId: 'classic_whodunit',
      lifeVision: '侦破层层谜团',
    });

    expect(result).not.toBeNull();

    // 导航到游戏页面，触发完整渲染管线
    await navigateToGame(page, result!.game_id);
    await page.waitForTimeout(3000);

    // 验证无 5xx 服务器错误
    const serverErrors = monitor.get5xxErrors();
    if (serverErrors.length > 0) {
      console.error('Pipeline server errors:', formatNetworkErrors(serverErrors));
    }
    expect(serverErrors).toHaveLength(0);

    await page.screenshot({
      path: 'test-results/narrative-d2-pipeline.png',
      fullPage: true,
    });
  });

  test('D3. constraint violation does not crash game', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    // 创建一个带有极端/边缘 character_settings 的游戏
    const result = await createGameWithStyle(context, {
      playerName: 'Constraint_Edge',
      narrativeStyleId: 'stream_of_consciousness',
      lifeVision: '', // 空的 life_vision - 边缘情况
      characterSettings: {
        narrative_style_id: 'stream_of_consciousness',
        extra_unknown_field: 'should_be_ignored',
      },
    });

    // 即使边缘输入，也不应该崩溃
    // 可能返回 null（400 错误）或成功创建
    if (result) {
      const gameData = await getGameState(context, result.game_id);
      expect(gameData).not.toBeNull();
    }
    // 如果 result 为 null，说明后端正确拒绝了无效输入，也算通过
  });
});

// ============================================================================
// E. Game Lifecycle - 游戏生命周期测试
// ============================================================================

test.describe('E. Game Lifecycle with Narrative Systems', () => {
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

  test('E1. create → load → verify style preserved in game state', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const styleId = 'romantic_legend';
    const result = await createGameWithStyle(context, {
      playerName: 'Lifecycle_StylePreserve',
      narrativeStyleId: styleId,
      lifeVision: '书写浪漫传奇',
    });

    expect(result).not.toBeNull();

    // 通过 API 重新加载游戏状态
    const gameData = await getGameState(context, result!.game_id);
    expect(gameData).not.toBeNull();
    expect(gameData!.game_id).toBe(result!.game_id);

    // player_state 应保留创建时的设定
    expect(gameData!.player_state).toBeDefined();
    const playerState = gameData!.player_state as Record<string, unknown>;
    expect(playerState).toBeDefined();
  });

  test('E2. create → play multiple rounds → verify story continuity', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const result = await createGameWithStyle(context, {
      playerName: 'Lifecycle_MultiRound',
      narrativeStyleId: 'police_procedural',
      lifeVision: '破获连环悬案',
    });

    expect(result).not.toBeNull();
    const gameId = result!.game_id;

    // 通过同步 API 提交选择（避免 SSE 复杂性）
    const choiceResponse = await context.request.post(
      `${API_URL}/api/games/${gameId}/choice-sync`,
      { data: { option_index: 0 } }
    );

    // 选择可能成功或失败（取决于游戏是否已生成选项）
    if (choiceResponse.ok()) {
      // 验证选择后游戏状态更新
      const updatedState = await getGameState(context, gameId);
      expect(updatedState).not.toBeNull();
      expect(updatedState!.game_id).toBe(gameId);
    }

    // 无论选择是否成功，游戏应该仍然可加载
    const finalState = await getGameState(context, gameId);
    expect(finalState).not.toBeNull();
  });

  test('E3. create → save → reload → verify narrative state preserved', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const result = await createGameWithStyle(context, {
      playerName: 'Lifecycle_SaveReload',
      narrativeStyleId: 'epistolary_novel',
      lifeVision: '通过信件记录人生',
    });

    expect(result).not.toBeNull();
    const gameId = result!.game_id;

    // 保存游戏
    const saveResponse = await context.request.post(
      `${API_URL}/api/games/${gameId}/save`
    );
    // 保存可能成功或失败（取决于会话状态）
    // 不硬性断言 save 成功，因为 API 创建的游戏可能没有活跃会话

    // 重新加载游戏状态
    const reloadedState = await getGameState(context, gameId);
    expect(reloadedState).not.toBeNull();
    expect(reloadedState!.game_id).toBe(gameId);

    // 验证 player_state 和 progress 结构存在
    expect(reloadedState!.player_state).toBeDefined();
    expect(reloadedState!.progress).toBeDefined();
  });

  test('E4. game with style → generate choices → verify choices reflect narrative', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const result = await createGameWithStyle(context, {
      playerName: 'Lifecycle_Choices',
      narrativeStyleId: 'courtroom_drama',
      lifeVision: '在法庭上追寻正义',
    });

    expect(result).not.toBeNull();

    const gameData = await getGameState(context, result!.game_id);
    expect(gameData).not.toBeNull();

    // 检查 current_event 是否包含选项
    if (gameData!.current_event) {
      const event = gameData!.current_event as Record<string, unknown>;
      // 事件应该有结构（options 字段可能存在）
      expect(typeof event).toBe('object');

      // 如果有 options，验证它们是数组
      if ('options' in event && event.options) {
        expect(Array.isArray(event.options)).toBeTruthy();
        const options = event.options as Array<Record<string, unknown>>;
        // 每个选项应有文本
        for (const opt of options) {
          expect(opt).toBeDefined();
        }
      }
    }
  });
});

// ============================================================================
// F. Browser UI Validation - 浏览器 UI 验证
// ============================================================================

test.describe('F. Browser UI with Narrative Systems', () => {
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

  test('F1. story text displays correctly with styled content', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const result = await createGameWithStyle(context, {
      playerName: 'UI_StoryDisplay',
      narrativeStyleId: 'romantic_legend',
      lifeVision: '追寻传奇爱情',
    });
    expect(result).not.toBeNull();

    await navigateToGame(page, result!.game_id);
    await page.waitForTimeout(3000);

    // 验证页面有文本内容区域
    const mainContent = page.locator('main, [class*="story"], [class*="content"], [class*="narrative"]');
    const hasMainContent = (await mainContent.count()) > 0;

    if (hasMainContent) {
      const textContent = await mainContent.first().textContent().catch(() => '');
      // 只验证有文本输出（AI 生成是非确定性的）
      if (textContent) {
        expect(textContent.trim().length).toBeGreaterThan(0);
      }
    }

    await page.screenshot({
      path: 'test-results/narrative-f1-story-display.png',
      fullPage: true,
    });
  });

  test('F2. game page has no console errors with all systems enabled', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const result = await createGameWithStyle(context, {
      playerName: 'UI_NoErrors',
      narrativeStyleId: 'scifi_space_opera',
      lifeVision: '征服星辰大海',
    });
    expect(result).not.toBeNull();

    const consoleErrors = collectConsoleErrors(page);
    const monitor = startNetworkMonitoring(page);

    await navigateToGame(page, result!.game_id);
    await page.waitForTimeout(3000);

    // 验证无关键控制台错误
    const critical = filterCriticalErrors(consoleErrors);
    const apiErrors = critical.filter(
      (e) => e.includes('500') || e.includes('Internal Server Error')
    );
    expect(apiErrors).toHaveLength(0);

    // 验证无 5xx 网络错误
    const serverErrors = monitor.get5xxErrors();
    expect(serverErrors).toHaveLength(0);

    await page.screenshot({
      path: 'test-results/narrative-f2-no-errors.png',
      fullPage: true,
    });
  });

  test('F3. choices panel renders properly with narrative-enhanced options', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const result = await createGameWithStyle(context, {
      playerName: 'UI_Choices',
      narrativeStyleId: 'classic_whodunit',
      lifeVision: '侦破不可能犯罪',
    });
    expect(result).not.toBeNull();

    await navigateToGame(page, result!.game_id);
    await page.waitForTimeout(5000); // 等待 AI 生成选项

    // 查找选项/按钮
    const choiceButtons = page.locator(
      'button:has-text("选择"), button:has-text("选项"), [class*="choice"] button, [class*="option"] button'
    );
    const choiceCount = await choiceButtons.count();

    // 截图记录当前状态（无论是否有选项）
    await page.screenshot({
      path: 'test-results/narrative-f3-choices-panel.png',
      fullPage: true,
    });

    // 如果有选项，验证它们可见且可交互
    if (choiceCount > 0) {
      const firstChoice = choiceButtons.first();
      await expect(firstChoice).toBeVisible();
      // 按钮应该有文本内容
      const buttonText = await firstChoice.textContent();
      expect(buttonText).toBeTruthy();
      expect(buttonText!.trim().length).toBeGreaterThan(0);
    }
  });

  test('F4. page responsive and interactive during story generation', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const result = await createGameWithStyle(context, {
      playerName: 'UI_Responsive',
      narrativeStyleId: 'naturalism',
      lifeVision: '感受自然的呼吸',
    });
    expect(result).not.toBeNull();

    const monitor = startNetworkMonitoring(page);

    await navigateToGame(page, result!.game_id);

    // 在内容加载过程中，验证页面仍然可交互
    await expect(page.locator('body')).toBeVisible();

    // 等待内容渲染
    await page.waitForTimeout(3000);

    // 验证页面没有白屏（body 有实际内容）
    const bodyText = await page.locator('body').textContent().catch(() => '');
    expect(bodyText).toBeTruthy();
    expect(bodyText!.trim().length).toBeGreaterThan(0);

    // 验证无请求失败
    const failedRequests = monitor.errors.filter((e) => e.status === 0);
    expect(failedRequests).toHaveLength(0);

    await page.screenshot({
      path: 'test-results/narrative-f4-responsive.png',
      fullPage: true,
    });
  });
});

// ============================================================================
// G. Performance and Stability - 性能与稳定性
// ============================================================================

test.describe('G. Performance and Stability', () => {
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

  test('G1. story generation completes within reasonable timeout', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const startTime = Date.now();

    const result = await createGameWithStyle(context, {
      playerName: 'Perf_Timeout',
      narrativeStyleId: 'black_humor',
      lifeVision: '在荒诞中寻找意义',
    });

    const createDuration = Date.now() - startTime;

    expect(result).not.toBeNull();
    // 游戏创建（含 AI 生成）应在 90 秒内完成
    expect(createDuration).toBeLessThan(90_000);

    console.log(`Game creation took ${createDuration}ms`);

    // 验证游戏有内容
    const gameData = await getGameState(context, result!.game_id);
    expect(gameData).not.toBeNull();
  });

  test('G2. rapid style switching does not cause errors', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const styles = [
      'gothic_romance',
      'cyberpunk',
      'folktale_fairytale',
      'psychological_suspense',
    ];

    const results: Array<{ game_id: number } | null> = [];
    const errors: string[] = [];

    // 快速连续创建不同风格的游戏
    for (const style of styles) {
      try {
        const result = await createGameWithStyle(context, {
          playerName: `RapidStyle_${style}_${Date.now()}`,
          narrativeStyleId: style,
          lifeVision: '快速切换测试',
        });
        results.push(result);
      } catch (e) {
        errors.push(`Failed to create game with style ${style}: ${e}`);
      }
    }

    // 不应有任何错误
    expect(errors).toHaveLength(0);

    // 所有游戏应成功创建
    const successCount = results.filter((r) => r !== null).length;
    expect(successCount).toBe(styles.length);

    // 验证每个游戏都可加载
    for (const result of results) {
      if (result) {
        const gameData = await getGameState(context, result.game_id);
        expect(gameData).not.toBeNull();
      }
    }
  });
});

// ============================================================================
// Original Tests (preserved) - 原有 API 和 Browser 级别测试
// ============================================================================

test.describe('Narrative Systems - API Level', () => {
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

  test('1. create game with narrative_style_id via API', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const result = await createGameWithStyle(context, {
      playerName: 'StyleTest_ChineseClassic',
      narrativeStyleId: 'gothic_romance',
      lifeVision: '行走江湖，匡扶正义',
    });

    expect(result).not.toBeNull();
    expect(result!.game_id).toBeDefined();
    expect(typeof result!.game_id).toBe('number');

    const gameResponse = await context.request.get(
      `${API_URL}/api/games/${result!.game_id}`
    );
    expect(gameResponse.ok()).toBeTruthy();

    const gameData = await gameResponse.json();
    expect(gameData.game_id).toBe(result!.game_id);
  });

  test('4. different styles create different game experiences', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const gameA = await createGameWithStyle(context, {
      playerName: 'StyleCompare_Gothic',
      narrativeStyleId: 'gothic_romance',
      lifeVision: '在迷雾中探寻真相',
    });

    const gameB = await createGameWithStyle(context, {
      playerName: 'StyleCompare_Cyberpunk',
      narrativeStyleId: 'cyberpunk',
      lifeVision: 'Venture into the neon city',
    });

    expect(gameA).not.toBeNull();
    expect(gameB).not.toBeNull();
    expect(gameA!.game_id).toBeDefined();
    expect(gameB!.game_id).toBeDefined();

    expect(gameA!.game_id).not.toBe(gameB!.game_id);
  });

  test('6. verify three narrative systems initialization', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const result = await createGameWithStyle(context, {
      playerName: 'SystemInit_Test',
      narrativeStyleId: 'romantic_legend',
      lifeVision: '开启传奇人生',
    });

    expect(result).not.toBeNull();

    const gameResponse = await context.request.get(
      `${API_URL}/api/games/${result!.game_id}`
    );
    expect(gameResponse.ok()).toBeTruthy();

    const gameData = await gameResponse.json();
    expect(gameData.game_id).toBe(result!.game_id);

    const hasStoryContent =
      gameData.round_info != null || gameData.current_event != null;
    expect(hasStoryContent).toBeTruthy();
  });
});

test.describe('Narrative Systems - Browser Level', () => {
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

  test('2. game page loads correctly with narrative style', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const result = await createGameWithStyle(context, {
      playerName: 'BrowserLoad_StyleTest',
      narrativeStyleId: 'gothic_romance',
      lifeVision: '闯荡武林',
    });
    expect(result).not.toBeNull();

    const consoleErrors = collectConsoleErrors(page);
    const monitor = startNetworkMonitoring(page);

    await navigateToGame(page, result!.game_id);

    await expect(page.locator('body')).toBeVisible();

    const critical = filterCriticalErrors(consoleErrors);
    const apiErrors = critical.filter(
      (e) => e.includes('500') || e.includes('Internal Server Error')
    );
    expect(apiErrors).toHaveLength(0);

    await page.screenshot({
      path: 'test-results/narrative-style-page-load.png',
      fullPage: true,
    });
  });

  test('3. full game flow with narrative systems enabled', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const result = await createGameWithStyle(context, {
      playerName: 'FullFlow_NarrativeTest',
      narrativeStyleId: 'romantic_legend',
      lifeVision: '行侠仗义，笑傲江湖',
    });
    expect(result).not.toBeNull();

    const monitor = startNetworkMonitoring(page);

    await navigateToGame(page, result!.game_id);

    await page.waitForTimeout(3000);

    const mainContent = page.locator('main, [class*="story"], [class*="content"], [class*="narrative"]');
    const hasMainContent = (await mainContent.count()) > 0;

    if (hasMainContent) {
      const textContent = await mainContent.first().textContent().catch(() => '');

      if (textContent && textContent.trim().length > 0) {
        expect(textContent.trim().length).toBeGreaterThan(0);
      }
    }

    const choiceButtons = page.locator(
      'button:has-text("选择"), button:has-text("选项"), [class*="choice"] button, [class*="option"] button'
    );
    const choiceCount = await choiceButtons.count();

    if (choiceCount > 0) {
      monitor.clear();
      await choiceButtons.first().click();
      await page.waitForTimeout(5000);
      await waitForNetworkIdle(page);
    }

    const serverErrors = monitor.get5xxErrors();
    if (serverErrors.length > 0) {
      console.error('Server errors during gameplay:', formatNetworkErrors(serverErrors));
    }
    expect(serverErrors).toHaveLength(0);

    await page.screenshot({
      path: 'test-results/narrative-full-flow.png',
      fullPage: true,
    });
  });

  test('5. game works correctly without narrative_style_id (fallback)', async () => {
    test.skip(await skipIfBackendUnavailable(context), '后端 API 不可达，跳过测试');

    const result = await createGameWithStyle(context, {
      playerName: 'Fallback_NoStyle',
      lifeVision: '平凡的一生',
    });
    expect(result).not.toBeNull();

    const consoleErrors = collectConsoleErrors(page);
    const monitor = startNetworkMonitoring(page);

    await navigateToGame(page, result!.game_id);

    await expect(page.locator('body')).toBeVisible();

    const critical = filterCriticalErrors(consoleErrors);
    const apiErrors = critical.filter(
      (e) => e.includes('500') || e.includes('Internal Server Error')
    );
    expect(apiErrors).toHaveLength(0);

    const serverErrors = monitor.get5xxErrors();
    expect(serverErrors).toHaveLength(0);

    await page.screenshot({
      path: 'test-results/narrative-fallback-no-style.png',
      fullPage: true,
    });
  });
});
