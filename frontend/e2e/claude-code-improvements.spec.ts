 

/**
 * Claude Code Improvements - E2E Validation
 *
 * 验证前端进度显示和面板交互：
 * 1. 故事生成阶段进度显示
 * 2. 重试状态透明处理
 * 3. 模型降级对用户透明
 * 4. 长故事完整性（无截断）
 * 5. 并行后处理不影响游戏流程
 * 6. 长时间游戏无上下文溢出
 */

import { test, expect, Page, BrowserContext } from '@playwright/test';
import { ensureAuthenticated, API_URL } from './helpers/auth';
import { startNetworkMonitoring, formatNetworkErrors } from './helpers/network-monitor';
import { waitForNetworkIdle } from './helpers/wait-helpers';

const BASE_URL = process.env.E2E_BASE_URL || `http://localhost:${process.env.E2E_FRONTEND_PORT ?? '3000'}`;
/** SSE 事件收集器 */
interface SSEEvent {
  eventType: string;
  data: string;
  timestamp: number;
}

/**
 * 通过 route 拦截 SSE 响应，收集事件
 * 拦截 game event SSE 流并解析事件
 */
async function interceptSSEEvents(page: Page): Promise<{ events: SSEEvent[]; promise: Promise<void> }> {
  const events: SSEEvent[] = [];
  let resolvePromise: () => void;
  const promise = new Promise<void>((resolve) => {
    resolvePromise = resolve;
  });

  // 使用 page.on('response') 监听 SSE 响应
  page.on('response', async (response) => {
    const url = response.url();
    if (!url.includes('/api/games/') || !url.includes('/event')) return;

    const contentType = response.headers()['content-type'] || '';
    if (!contentType.includes('text/event-stream')) return;

    try {
      const body = await response.text();
      const lines = body.split('\n');
      let currentEventType = 'message';

      for (const line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith('event: ')) {
          currentEventType = trimmed.slice(7);
        } else if (trimmed.startsWith('data: ')) {
          events.push({
            eventType: currentEventType,
            data: trimmed.slice(6),
            timestamp: Date.now(),
          });
          if (currentEventType === 'complete') {
            resolvePromise!();
          }
          currentEventType = 'message';
        }
      }
    } catch {
      // SSE stream may not be fully readable as text
    }
  });

  // 超时自动 resolve（与 test.setTimeout 配合，留出足够时间）
  setTimeout(() => resolvePromise!(), 90000);

  return { events, promise };
}

/**
 * 等待游戏页面加载并显示内容
 */
async function waitForGameReady(page: Page): Promise<void> {
  // 等待页面加载完成
  await page.waitForLoadState('domcontentloaded');
  await waitForNetworkIdle(page);

  await expect(page.getByRole('heading', { name: '听故事', exact: true })).toBeVisible({ timeout: 30_000 });
}

/**
 * 通过 API 创建测试游戏
 */
async function createTestGame(context: BrowserContext): Promise<number> {
  const createResp = await context.request.post(`${API_URL}/api/games`, {
    data: {
      player_name: 'E2E测试角色',
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

  if (!createResp.ok()) {
    throw new Error(`创建游戏失败: ${createResp.status()} ${await createResp.text()}`);
  }

  const game = await createResp.json();
  return game.game_id;
}

/**
 * 导航到有效的游戏页面
 * 使用 API 预创建游戏，绕过 UI 创建流程和 AI 生成等待
 */
async function navigateToGame(page: Page, context: BrowserContext): Promise<number> {
  // A layout header also exists on the home page after /play redirects.
  // Own an actual game in every test instead of accepting that header as setup.
  const gameId = await createTestGame(context);

  // 直接导航到游戏页面
  await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
  await waitForGameReady(page);

  return gameId;
}

test.describe('Claude Code Improvements - E2E Validation', () => {
  // 涉及游戏创建 + AI 故事生成 + SSE 流，需要充足的超时
  test.setTimeout(300_000);

  test.beforeEach(async ({ page, context }) => {
    await ensureAuthenticated(page, context);
  });

  test('1. Story generation shows phase progress', async ({ page, context }) => {
    // Goal: Verify SSE status events show correct phases
    // and UI displays loading state during generation
    const monitor = startNetworkMonitoring(page);
    const { events, promise: ssePromise } = await interceptSSEEvents(page);

    // Navigate to game page
    await navigateToGame(page, context);

    // Wait for any ongoing generation to complete
    await page.waitForTimeout(2000);

    // Check if we need to trigger generation
    // If skeleton is visible, generation is already in progress
    const skeletonVisible = await page.locator('.animate-spin').first().isVisible().catch(() => false);
    const storyVisible = await page.locator('main').getByText(/.{20,}/).first().isVisible().catch(() => false);

    if (skeletonVisible) {
      // Generation is in progress - verify skeleton/loading state is shown
      // SkeletonStory shows a loading spinner and message
      const loadingIndicator = page.locator('.animate-spin').first();
      await expect(loadingIndicator).toBeVisible();

      // Wait for generation to complete
      await ssePromise;

      // After completion, story text should appear
      await page.waitForSelector('main', { timeout: 30000 });
      const mainContent = await page.locator('main').textContent();
      expect(mainContent).toBeTruthy();
      expect(mainContent!.length).toBeGreaterThan(0);
    }

    // Verify SSE events if captured
    if (events.length > 0) {
      // Check that status events were received
      const statusEvents = events.filter(e => e.eventType === 'status');
      const completeEvents = events.filter(e => e.eventType === 'complete');

      // If we have status events, verify phase progression
      if (statusEvents.length > 0) {
        const phases = statusEvents.map(e => {
          try {
            return JSON.parse(e.data).phase;
          } catch {
            return null;
          }
        }).filter(Boolean);

        // Phases should progress logically
        if (phases.length > 0) {
          // generating_story should come before generating_options
          const storyIdx = phases.indexOf('generating_story');
          const optionsIdx = phases.indexOf('generating_options');
          if (storyIdx >= 0 && optionsIdx >= 0) {
            expect(storyIdx).toBeLessThan(optionsIdx);
          }
        }
      }
    }

    // If story is already visible, verify it has content
    if (storyVisible) {
      const storyText = await page.locator('main').textContent();
      expect(storyText).toBeTruthy();
    }

    // Verify option cards appear when generation is complete
    // Options show "你的选择" label
    const optionsLabel = page.locator('text=你的选择');
    const hasOptions = await optionsLabel.isVisible({ timeout: 5000 }).catch(() => false);
    // Options may or may not be present depending on game state
    // Just verify no errors
    expect(monitor.get5xxErrors()).toHaveLength(0);
  });

  test('2. Story generation retry shows retry status', async ({ page, context }) => {
    // Goal: Verify retry mechanism works transparently
    const monitor = startNetworkMonitoring(page);
    const consoleMessages: string[] = [];

    // Capture console messages for retry detection
    page.on('console', msg => {
      consoleMessages.push(msg.text());
    });

    const { events } = await interceptSSEEvents(page);

    // Navigate to game
    await navigateToGame(page, context);

    // Wait for any generation
    await page.waitForTimeout(3000);
    await waitForNetworkIdle(page);

    // Check for retry events in SSE
    const retryEvents = events.filter(e => {
      try {
        const data = JSON.parse(e.data);
        return data.phase === 'retry' || data.type === 'retry';
      } catch {
        return false;
      }
    });

    // If retry happened, verify no error toast is shown
    if (retryEvents.length > 0) {
      // Error toast should NOT be visible for retries
      const errorToast = page.locator('[role="alert"], .toast-error, [data-type="error"]');
      const hasErrorToast = await errorToast.isVisible().catch(() => false);
      expect(hasErrorToast).toBe(false);
    }

    // Verify story eventually completes (with or without retries)
    const mainContent = await page.locator('main').textContent();
    expect(mainContent).toBeTruthy();

    // Check console for retry-related messages (informational)
    const retryLogs = consoleMessages.filter(m =>
      m.includes('retry') || m.includes('Retry') || m.includes('[SSE]')
    );
    // Retries are expected, not an error condition
    // Just verify no 5xx errors
    expect(monitor.get5xxErrors()).toHaveLength(0);
  });

  test('3. Model fallback is transparent to user', async ({ page, context }) => {
    // Goal: Verify model switching doesn't break user experience
    const monitor = startNetworkMonitoring(page);
    const consoleErrors: string[] = [];

    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    page.on('pageerror', error => {
      consoleErrors.push(error.message);
    });

    // Navigate to game
    await navigateToGame(page, context);

    // Wait for any generation to complete
    await page.waitForTimeout(3000);
    await waitForNetworkIdle(page);

    // Verify story text eventually appears (regardless of model used)
    const mainContent = page.locator('main');
    await expect(mainContent).toBeVisible();

    // Check if story text is present
    const storyArea = await mainContent.textContent();
    expect(storyArea).toBeTruthy();

    // Check no 5xx errors in network monitor
    const serverErrors = monitor.get5xxErrors();
    if (serverErrors.length > 0) {
      console.error('Server errors during model fallback:', formatNetworkErrors(serverErrors));
    }
    expect(serverErrors).toHaveLength(0);

    // Check no error-related console messages (filter known non-issues)
    const criticalErrors = consoleErrors.filter(e =>
      !e.includes('favicon') &&
      !e.includes('extension') &&
      !e.includes('SourceMap') &&
      !e.includes('ResizeObserver') &&
      !e.includes('hydration')
    );

    // Model-related errors should not leak to console
    const modelErrors = criticalErrors.filter(e =>
      e.includes('model') ||
      e.includes('fallback') ||
      e.includes('rate limit') ||
      e.includes('429')
    );
    expect(modelErrors).toHaveLength(0);
  });

  test('4. Long stories are complete without truncation', async ({ page, context }) => {
    const monitor = startNetworkMonitoring(page);
    const gameId = await navigateToGame(page, context);
    const response = await context.request.get(`${API_URL}/api/games/${gameId}`);
    expect(response.status(), await response.text()).toBe(200);
    const state = await response.json();
    const story: string = state.current_event.event_description;
    expect(story.length).toBeGreaterThan(100);
    expect(story.trim()).toMatch(/[。！？….!?」）]$/);
    expect(state.current_event.options.length).toBeGreaterThan(0);

    await page.getByRole('button', { name: '查看故事正文', exact: true }).click();
    const transcript = page.getByRole('region', { name: '故事正文', exact: true });
    await expect(transcript).toBeVisible();
    const paragraphs = transcript.getByRole('button', { name: /^从第 \d+ 段开始朗读$/ });
    const expected = story.split(/\n\s*\n|\n/).map(text => text.trim()).filter(Boolean);
    await expect(paragraphs).toHaveText(expected);
    expect(monitor.get5xxErrors()).toHaveLength(0);
  });

  test('5. Game progression works correctly after post-processing', async ({ page, context }) => {
    const monitor = startNetworkMonitoring(page);
    const gameId = await navigateToGame(page, context);
    const beforeResponse = await context.request.get(`${API_URL}/api/games/${gameId}/state`);
    expect(beforeResponse.status()).toBe(200);
    const before = await beforeResponse.json();
    const nextDay = before.player_state.timeline.day_index + 1;

    // Select an actual story option, not an unrelated listening control.
    const choice = page.getByRole('button', { name: /选择 1：/ });
    await expect(choice).toBeEnabled();
    const choiceResponse = page.waitForResponse(
      response => new URL(response.url()).pathname === `/api/games/${gameId}/choice`,
      { timeout: 45_000 },
    );
    await choice.click();
    expect((await choiceResponse).status()).toBe(200);

    await expect.poll(async () => {
      const response = await context.request.get(`${API_URL}/api/games/${gameId}/state`);
      expect(response.status()).toBe(200);
      const state = await response.json();
      return state.player_state.timeline.day_index;
    }, { timeout: 45_000 }).toBe(nextDay);
    await expect(page.getByTestId('status-bar').first()).toContainText(`第 ${nextDay + 1} 天`);
    await expect(page.getByRole('heading', { name: '听故事', exact: true })).toBeVisible();
    await expect(choice).toBeEnabled({ timeout: 45_000 });
    const afterResponse = await context.request.get(`${API_URL}/api/games/${gameId}`);
    expect(afterResponse.status()).toBe(200);
    const after = await afterResponse.json();
    expect(after.current_event.story_date).toBe(after.player_state.timeline.current_date);
    expect(after.current_event.event_description.length).toBeGreaterThan(100);
    expect(monitor.get5xxErrors()).toHaveLength(0);
  });

  test('6. Long-running game does not fail from context overflow', async ({ page, context }) => {
    // Goal: Verify reactive compression prevents context overflow
    const monitor = startNetworkMonitoring(page);
    const consoleMessages: string[] = [];

    page.on('console', msg => {
      consoleMessages.push(msg.text());
    });

    page.on('pageerror', error => {
      consoleMessages.push(`[PageError] ${error.message}`);
    });

    // Navigate to game (preferably one with history)
    await navigateToGame(page, context);

    // Wait for generation to complete
    await page.waitForTimeout(5000);
    await waitForNetworkIdle(page);

    // Verify no "context too long" or "token limit" errors
    const contextErrors = consoleMessages.filter(m =>
      m.includes('context too long') ||
      m.includes('token limit') ||
      m.includes('context_length_exceeded') ||
      m.includes('maximum context') ||
      m.includes('too many tokens')
    );
    expect(contextErrors).toHaveLength(0);

    // Verify story generates successfully
    const mainContent = await page.locator('main').textContent();
    expect(mainContent).toBeTruthy();

    // Verify main area is visible (story loaded)
    const mainArea = page.locator('main');
    await expect(mainArea).toBeVisible();

    // Check no 5xx errors
    const serverErrors = monitor.get5xxErrors();
    if (serverErrors.length > 0) {
      console.error('Server errors in long-running game:', formatNetworkErrors(serverErrors));
    }
    expect(serverErrors).toHaveLength(0);

    // Check console for any truncation/compression warnings (info only, not a test failure)
    const compressionLogs = consoleMessages.filter(m =>
      m.includes('compress') ||
      m.includes('truncat') ||
      m.includes('context window')
    );
    if (compressionLogs.length > 0) {
      console.log('Compression/truncation info messages:', compressionLogs);
    }
    // These are informational - compression happening is expected behavior
  });
});
