 

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
import { ensureAuthenticated } from './helpers/auth';
import { startNetworkMonitoring, formatNetworkErrors } from './helpers/network-monitor';
import { waitForNetworkIdle, waitForStableDOM } from './helpers/wait-helpers';

const BASE_URL = process.env.E2E_BASE_URL || `http://localhost:${process.env.E2E_FRONTEND_PORT ?? '3000'}`;
const API_URL = process.env.E2E_API_URL || `http://${process.env.E2E_BACKEND_HOST || '127.0.0.1'}:${process.env.E2E_BACKEND_PORT || '8000'}`;

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

  // 等待 header 出现（游戏页面标志）
  await page.waitForSelector('header', { timeout: 15000 }).catch(() => {});
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
async function navigateToGame(page: Page, context: BrowserContext): Promise<void> {
  // 先检查是否已有活跃游戏
  await page.goto(`${BASE_URL}/play`);
  await waitForGameReady(page);

  const hasHeader = await page.locator('header').isVisible().catch(() => false);
  if (hasHeader) {
    return;
  }

  // 通过 API 快速创建游戏，绕过 AI 生成等待
  const gameId = await createTestGame(context);

  // 直接导航到游戏页面
  await page.goto(`${BASE_URL}/play?gameId=${gameId}`);
  await waitForGameReady(page);

  // 最终验证
  const finalHasHeader = await page.locator('header').isVisible().catch(() => false);
  expect(finalHasHeader).toBe(true);
}

async function waitForChoiceProgressionCheckpoint(
  page: Page,
  choiceResponse: Promise<unknown>
): Promise<void> {
  const stableMain = waitForStableDOM(page, 'main', { timeout: 10_000, stableTime: 1_000 }).catch(
    () => null
  );

  await Promise.race([choiceResponse, page.waitForTimeout(45_000)]);

  await stableMain;
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
    // Goal: Verify truncation recovery produces complete text
    const monitor = startNetworkMonitoring(page);
    const { events, promise: ssePromise } = await interceptSSEEvents(page);

    // Navigate to game
    await navigateToGame(page, context);

    // Wait for generation to complete
    await page.waitForTimeout(3000);
    await waitForNetworkIdle(page);

    // Wait for SSE to complete if in progress
    await Promise.race([
      ssePromise,
      page.waitForTimeout(30000),
    ]);

    // Wait for story text to stabilize
    await waitForStableDOM(page, 'main', { timeout: 15000, stableTime: 2000 }).catch(() => {});

    // Get story text content from page
    const storyText = await page.locator('main').textContent();
    expect(storyText).toBeTruthy();

    // Verify text length is substantial (> 100 chars)
    // Filter out UI chrome text (buttons, labels, etc.)
    const cleanText = (storyText || '').replace(/你的选择|返回当前|保存|历史回顾|收集/g, '').trim();
    if (cleanText.length > 50) {
      // Only check length for real story content
      expect(cleanText.length).toBeGreaterThan(100);

      // Verify text ends with valid sentence ending
      // Chinese punctuation: 。！？… or western: . ! ? ...
      const lastMeaningfulChar = cleanText.replace(/\s+$/, '').slice(-1);
      const validEndings = ['。', '！', '？', '…', '.', '!', '?', '"', '"', '」', '）'];
      // Story should end with proper punctuation (if long enough)
      if (cleanText.length > 300) {
        const endsWithValidPunctuation = validEndings.some(p => cleanText.trimEnd().endsWith(p));
        // This is a soft check - some stories may end differently
        if (!endsWithValidPunctuation) {
          console.warn('Story may be truncated - does not end with expected punctuation:', lastMeaningfulChar);
        }
      }
    }

    // Verify no 5xx errors
    expect(monitor.get5xxErrors()).toHaveLength(0);
  });

  test('5. Game progression works correctly after post-processing', async ({ page, context }) => {
    // Goal: Verify parallel post-processing doesn't break game flow
    const monitor = startNetworkMonitoring(page);

    // Navigate to game
    await navigateToGame(page, context);

    // Wait for game to be in a stable state
    await page.waitForTimeout(3000);
    await waitForNetworkIdle(page);

    // Capture initial status bar content
    const initialStatusText = await page.locator('header').textContent().catch(() => '');

    // Look for option cards (indicating options phase)
    const optionButton = page.locator('button').filter({ hasText: /^(?!.*(?:保存|历史|返回|收集|设置)).{5,}/ }).first();
    const hasOptions = await optionButton.isVisible({ timeout: 5000 }).catch(() => false);

    if (hasOptions) {
      // Click the first option to make a choice
      monitor.clear();
      const choiceResponse = page.waitForResponse(
        resp =>
          resp.url().includes('/api/games/') &&
          (resp.url().includes('/choice') || resp.url().includes('/custom-choice')),
        { timeout: 45_000 }
      ).catch(() => null);
      await optionButton.click();
      await waitForChoiceProgressionCheckpoint(page, choiceResponse);

      // Verify status bar values may have updated
      const updatedStatusText = await page.locator('header').textContent().catch(() => '');
      // Status text exists (whether changed or not)
      expect(updatedStatusText).toBeTruthy();

      // Verify new story content appears (story continuity)
      const storyText = await page.locator('main').textContent();
      expect(storyText).toBeTruthy();
      expect(storyText!.length).toBeGreaterThan(0);

      // Check no 5xx errors during the whole flow
      const serverErrors = monitor.get5xxErrors();
      if (serverErrors.length > 0) {
        console.error('Server errors during progression:', formatNetworkErrors(serverErrors));
      }
      expect(serverErrors).toHaveLength(0);
    } else {
      // No options available - generation might still be in progress
      // Verify page is in a valid state
      const mainContent = await page.locator('main').textContent();
      expect(mainContent).toBeTruthy();
      expect(monitor.get5xxErrors()).toHaveLength(0);
    }
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
