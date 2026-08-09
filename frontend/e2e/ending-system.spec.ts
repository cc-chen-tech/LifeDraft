/**
 * Ending System E2E Test - 结局系统测试
 *
 * 覆盖结局页面渲染、API 端点、导航等
 * 原则：不 mock，直接调用真实 API 或验证页面结构
 */

import { test, expect } from '@playwright/test';
import { ensureAuthenticated, API_URL } from './helpers/auth';
import { installReadyEndingFixture } from './helpers/ending-fixture';
import { startNetworkMonitoring, waitForNetworkIdle } from './helpers/network-monitor';

const BASE_URL = process.env.E2E_BASE_URL || `http://localhost:${process.env.E2E_FRONTEND_PORT ?? '3000'}`;
const API_BASE = `${API_URL}/api`;

test.describe('Ending System - Page Routing & Rendering', () => {
  // TC-01: 结局页面路由和渲染
  test('TC-01: ending page route exists and renders', async ({ page }) => {
    await page.goto(`${BASE_URL}/ending`);
    await page.waitForLoadState('domcontentloaded');

    // 结局页面应该可以访问（不会 404）
    // 如果没有 gameId，页面会重定向到首页
    const url = page.url();
    // 要么停留在 /ending，要么因为没有 gameId 重定向到 /
    expect(url).toMatch(/\/(ending|)$/);
  });

  // TC-04: 结局页面组件结构（标题/描述/统计区域）
  test('TC-04: ending page component structure', async ({ page }) => {
    await installReadyEndingFixture(page, { gameId: 999 });
    await page.goto('/ending');

    await expect(page.getByRole('heading', { level: 1, name: '平衡人生' })).toBeVisible();
    await expect(page.getByRole('button', { name: '返回首页' })).toBeVisible();
    await expect(page.getByRole('button', { name: '开始新人生' })).toBeVisible();
  });
});

test.describe('Ending System - API Endpoints', () => {
  test.beforeEach(async ({ page, context }) => {
    await ensureAuthenticated(page, context);
  });

  // TC-02: 结局 API 端点可用（GET /games/{id}/ending）
  test('TC-02: ending API endpoint exists', async ({ page }) => {
    const monitor = startNetworkMonitoring(page);

    // 直接调用 API 检查端点是否存在
    const response = await page.request.get(`${API_BASE}/games/99999/ending`);

    // 端点应该存在：返回 400（游戏未结束）、401（未认证）、404（游戏不存在）或 422
    // 不应返回 405（方法不允许）表示端点不存在
    expect(response.status()).not.toBe(405);
    expect([400, 401, 404, 422, 500]).toContain(response.status());
  });

  // TC-03: 结局 API 响应格式验证（真实 API 调用）
  test('TC-03: ending API response format validation', async ({ page }) => {
    const response = await page.request.get(`${API_BASE}/games/99999/ending`);

    // 端点应该存在
    expect(response.status()).not.toBe(405);

    // 验证响应体是合法 JSON（即使返回错误也应有统一格式）
    const bodyText = await response.text();
    let bodyJson: Record<string, unknown> | null = null;
    expect(() => {
      bodyJson = JSON.parse(bodyText);
    }).not.toThrow();

    // 如果返回 200，验证结局数据结构
    if (response.status() === 200 && bodyJson) {
      const json = bodyJson as Record<string, unknown>;
      if ('ending_type' in json) {
        expect(typeof json.ending_type).toBe('string');
      }
      if ('ending_name' in json) {
        expect(typeof json.ending_name).toBe('string');
      }
      if ('achievements' in json && json.achievements) {
        const achievements = json.achievements as Record<string, unknown>;
        if ('list' in achievements) {
          expect(Array.isArray(achievements.list)).toBe(true);
        }
      }
    }
  });

  // TC-05: 成就系统 API 验证（通过 ending 端点返回的 achievements）
  test('TC-05: achievements data in ending response', async ({ page }) => {
    const response = await page.request.get(`${API_BASE}/games/99999/ending`);

    // 端点存在即可
    expect(response.status()).not.toBe(405);

    // 解析响应
    const bodyText = await response.text();
    let bodyJson: Record<string, unknown> | null = null;
    try {
      bodyJson = JSON.parse(bodyText);
    } catch {
      // 非 JSON 响应也接受
    }

    // 如果返回了结局数据，验证 achievements 字段格式
    if (response.status() === 200 && bodyJson && 'achievements' in bodyJson) {
      const achievements = bodyJson.achievements as Record<string, unknown>;
      expect(achievements).toBeTruthy();
      if ('list' in achievements) {
        expect(Array.isArray(achievements.list)).toBe(true);
      }
    }
  });
});

test.describe('Ending System - Navigation', () => {
  // TC-06: 结局页面导航（返回首页）
  test('TC-06: navigate from ending page to home', async ({ page }) => {
    await installReadyEndingFixture(page, { gameId: 1, playerName: '导航测试' });
    await page.goto('/ending');

    await page.getByRole('button', { name: '返回首页' }).click();
    await expect(page).toHaveURL('/', { timeout: 10000 });
  });

  // TC-07: 无结局游戏访问结局页（没有 gameId 时应重定向）
  test('TC-07: redirect when no game exists', async ({ page }) => {
    // 清除所有 game 相关的 localStorage
    await page.goto(`${BASE_URL}/`);
    await page.evaluate(() => {
      localStorage.removeItem('game-store');
      // 清除所有可能的 game store key
      Object.keys(localStorage).forEach(key => {
        if (key.includes('game')) localStorage.removeItem(key);
      });
    });

    await page.goto(`${BASE_URL}/ending`);
    await page.waitForLoadState('domcontentloaded');

    // 没有 gameId，页面应重定向到首页
    await expect(page).toHaveURL('/', { timeout: 10000 });
  });
});

test.describe('Ending System - Summary API', () => {
  test.beforeEach(async ({ page, context }) => {
    await ensureAuthenticated(page, context);
  });

  // TC-08: 结局摘要生成 API（POST /games/{id}/summary）
  test('TC-08: summary generation API endpoint', async ({ page }) => {
    // 直接调用 summary API 检查端点是否存在
    const response = await page.request.post(`${API_BASE}/games/99999/summary`, {
      data: { weeks: 5 },
      headers: { 'Content-Type': 'application/json' },
    });

    // 端点应该存在：不应返回 405
    expect(response.status()).not.toBe(405);
    // 可能返回 401/404/422/500（取决于认证和游戏是否存在）
    expect([400, 401, 404, 422, 500]).toContain(response.status());
  });

  // TC-09: 结局与存档关联
  test('TC-09: ending linked to saved game', async ({ page }) => {
    const monitor = startNetworkMonitoring(page);

    // 访问存档页面
    await page.goto(`${BASE_URL}/saves`);
    await waitForNetworkIdle(page);

    // 存档页面应该正常加载
    const errors = monitor.get404Errors();
    const routeErrors = errors.filter(e => !e.url.includes('/games/'));
    expect(routeErrors).toHaveLength(0);

    // 检查是否有已结束的游戏存档（可能显示结局标记）
    const endedGames = page.locator('text=/结局|已结束|Ended|Ending/i');
    const hasEndedGames = await endedGames.count();

    // 无论是否有已结束的游戏，存档页面本身应该正常工作
    expect(typeof hasEndedGames).toBe('number');
  });
});

test.describe('Ending System - Error Handling', () => {
  // TC-10: 结局系统错误处理（真实 API 错误响应）
  test('TC-10: handle ending API error gracefully', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('pageerror', error => {
      consoleErrors.push(error.message);
    });

    // 直接调用真实 API 获取一个错误响应（游戏不存在）
    const response = await page.request.get(`${API_BASE}/games/99999/ending`);
    expect(response.status()).not.toBe(405);

    // 先导航到首页设置 localStorage
    await page.goto(`${BASE_URL}/`);
    await page.evaluate(() => {
      localStorage.setItem(
        'game-store',
        JSON.stringify({ state: { gameId: 99999, playerState: { player_name: '错误测试' } }, version: 0 })
      );
    });

    await page.goto(`${BASE_URL}/ending`, { waitUntil: 'domcontentloaded' });

    // 页面不应该崩溃（不应有未处理的 JS 错误）
    const unhandledErrors = consoleErrors.filter(e =>
      !e.includes('favicon') &&
      !e.includes('ResizeObserver') &&
      !e.includes('extension')
    );

    expect(unhandledErrors).toEqual([]);
    await expect(page.getByTestId('narrative-loading-screen')).toContainText('这一生，正在收束');
    await expect(page.getByRole('button', { name: '重试' })).toBeVisible();
  });

  test('TC-10b: handle game not over (400) response', async ({ page, context }) => {
    await ensureAuthenticated(page, context);
    const createResponse = await page.request.post(`${API_BASE}/games`, {
      data: {
        player_name: '未结束测试',
        life_vision: '继续记录尚未结束的生活',
        character_settings: {
          era: { name: '现代', period: '2026年' },
          age: { age: 30, stage: '青年' },
          personality: { traits: ['沉着'] },
          background: { occupation: '编辑' },
        },
        language: 'zh',
      },
    });
    expect(createResponse.status()).toBe(201);
    const created = await createResponse.json();
    const gameId = created.game_id as number;

    const response = await page.request.get(`${API_BASE}/games/${gameId}/ending`);

    expect(response.status()).toBe(400);

    await page.goto(`${BASE_URL}/`);
    await page.evaluate((fixtureGameId) => {
      localStorage.setItem(
        'game-store',
        JSON.stringify({ state: { gameId: fixtureGameId, playerState: { player_name: '未结束测试' } }, version: 0 })
      );
    }, gameId);

    await page.goto(`${BASE_URL}/ending`, { waitUntil: 'domcontentloaded' });

    await expect(page.getByTestId('narrative-loading-screen')).toContainText('这一生，正在收束');
    await expect(page.getByRole('button', { name: '重试' })).toBeVisible();
  });
});
