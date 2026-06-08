/**
 * E2E 测试辅助函数 - 认证相关
 *
 * ★ 使用纯 Cookie 认证（httpOnly）
 * - 不再使用 localStorage 存储 token
 * - 通过 Cookie 自动发送认证信息
 */
import { Page, BrowserContext, expect, APIResponse } from '@playwright/test';

export const API_HOST = process.env.E2E_BACKEND_HOST || '127.0.0.1';
export const API_PORT = process.env.E2E_BACKEND_PORT || '8000';
export const API_URL = `http://${API_HOST}:${API_PORT}`;

const API_HOSTS = ['localhost', '127.0.0.1', API_HOST, 'localhost.localdomain'];

type CreateGamePayload = {
  player_name: string;
  life_vision: string;
  character_settings: {
    era: { name: string; period: string };
    age: { age: number; stage: string };
    personality: { traits: string[] };
    background: { occupation: string };
  };
  language: string;
};

const defaultCreateGamePayload: CreateGamePayload = {
  player_name: 'E2E测试角色',
  life_vision: '探索世界',
  character_settings: {
    era: { name: '现代', period: '现代' },
    age: { age: 18, stage: '青年' },
    personality: { traits: ['勇敢', '好奇'] },
    background: { occupation: '学生' },
  },
  language: 'zh',
};

/**
 * 同步当前登录 Cookie 到 API request context 可能依赖的上下文。
 */
async function syncCookiesToContext(context: BrowserContext): Promise<void> {
  const cookies = await context.cookies();
  const apiCookies = cookies.filter(
    c => API_HOST.includes(c.domain) || API_HOSTS.includes(c.domain),
  );

  if (apiCookies.length > 0) {
    await context.addCookies(
      apiCookies.map(c => ({
        ...c,
        domain: 'localhost',
      })),
    );
  }
}

/**
 * 调整后端接口返回体，兼容不同字段名。
 */
async function resolveActiveGameId(response: APIResponse): Promise<number> {
  const data = await response.json();
  const gameId = (data?.game_id || data?.gameId) as number | undefined;
  if (!gameId || typeof gameId !== 'number') {
    throw new Error(`active 游戏接口返回无效 game_id: ${JSON.stringify(data)}`);
  }
  return gameId;
}

/**
 * 注册一个新用户并设置 Cookie
 */
export async function registerUser(
  context: BrowserContext,
  displayName: string = 'Test User'
): Promise<{ token: string; user: { user_id: number; display_name: string } } | null> {
  // 使用 context.request 确保 cookie 被保存到上下文中
  const registerResponse = await context.request.post(`${API_URL}/api/auth/register`, {
    data: { display_name: displayName }
  });

  if (registerResponse.ok()) {
    const data = await registerResponse.json();
    const cookies = await context.cookies();
    const apiCookies = cookies.filter(
      c => API_HOST.includes(c.domain) || API_HOSTS.includes(c.domain),
    );
    if (apiCookies.length > 0) {
      await context.addCookies(
        apiCookies.map(c => ({
          ...c,
          domain: 'localhost',
        })),
      );
    }
    return data;
  }
  return null;
}

/**
 * 确保用户已登录（如果没有则注册新用户）
 * 使用 Cookie 自动管理认证状态
 *
 * 策略：直接使用 API 注册（避免 UI 超时问题），然后让前端从 Cookie 恢复状态
 */
export async function ensureAuthenticated(page: Page, context: BrowserContext): Promise<void> {
  // 先访问页面，触发应用初始化
  await page.goto('/');

  // 等待页面加载完成（不用 networkidle，因为 SSE 连接会阻止它完成）
  await page.waitForLoadState('domcontentloaded');
  await page.waitForTimeout(1000);

  // 检查是否已登录（看是否有"登录"按钮）
  const loginButton = page.getByRole('button', { name: /登录/i });
  const isLoggedOut = await loginButton.isVisible().catch(() => false);

  if (isLoggedOut) {
    // 未登录，使用 API 直接注册（更可靠）
    const testUserName = `TestUser_${Date.now()}`;

    // 直接使用 page.request 调用 API，绕过 UI
    // ★ 使用 page.request 而非 context.request，确保 cookie 绑定到该 page
    const registerResponse = await page.request.post(`${API_URL}/api/auth/register`, {
      data: { display_name: testUserName }
    });

    if (!registerResponse.ok()) {
      const errorText = await registerResponse.text();
      throw new Error(`Registration failed: ${registerResponse.status()} ${errorText}`);
    }

    // 显式同步 cookie 到 context（WebKit 移动端需要）
    await syncCookiesToContext(context);

    // Cookie 已通过 page.request 自动设置到浏览器上下文中
    // 现在刷新页面，让前端从 Cookie 恢复登录状态
    await page.reload();
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(2000);

    // 等待 UI 更新为已登录状态（登录按钮应该消失）
    // 不硬性失败，Cookie 已经设置，UI 可能更新较慢
    try {
      await expect(loginButton).not.toBeVisible({ timeout: 10000 });
    } catch {
      // Cookie 已设置，即使 UI 未及时更新，后续页面导航会使用 Cookie
    }
  }
  // 已登录，无需操作
}

/**
 * 确保当前上下文既已登录又有活跃游戏。
 *
 * - 先确保认证完成
 * - 优先复用现有 active game
 * - 没有的话用同一 session 创建新游戏，避免出现匿名游戏导致 /play 恢复失败
 */
export async function ensureActiveGame(
  page: Page,
  context: BrowserContext,
  createPayload: Partial<CreateGamePayload> = {},
): Promise<number> {
  await ensureAuthenticated(page, context);
  await syncCookiesToContext(context);

  const payload: CreateGamePayload = {
    ...defaultCreateGamePayload,
    ...createPayload,
    character_settings: {
      ...defaultCreateGamePayload.character_settings,
      ...createPayload.character_settings,
      era: {
        ...defaultCreateGamePayload.character_settings.era,
        ...(createPayload.character_settings?.era || {}),
      },
      age: {
        ...defaultCreateGamePayload.character_settings.age,
        ...(createPayload.character_settings?.age || {}),
      },
      personality: {
        ...defaultCreateGamePayload.character_settings.personality,
        ...(createPayload.character_settings?.personality || {}),
      },
      background: {
        ...defaultCreateGamePayload.character_settings.background,
        ...(createPayload.character_settings?.background || {}),
      },
    },
  };

  // 先检查是否已有活跃游戏
  const activeResp = await page.request.get(`${API_URL}/api/games/active`);
  if (activeResp.ok()) {
    return resolveActiveGameId(activeResp);
  }

  if (activeResp.status() !== 404) {
    console.warn(`检查活跃游戏时出错: ${activeResp.status()}`);
  }

  const createResp = await page.request.post(`${API_URL}/api/games`, {
    data: payload,
  });

  if (createResp.status() === 401 || createResp.status() === 403) {
    // 保险：尝试刷新一次登录态后重试一次
    await ensureAuthenticated(page, context);
    await syncCookiesToContext(context);
    const retryResp = await page.request.post(`${API_URL}/api/games`, {
      data: payload,
    });

    if (!retryResp.ok()) {
      const retryText = await retryResp.text();
      throw new Error(`创建游戏失败（重试）: ${retryResp.status()} ${retryText}`);
    }
    return resolveActiveGameId(retryResp);
  }

  if (!createResp.ok()) {
    const errorText = await createResp.text();
    throw new Error(`创建游戏失败: ${createResp.status()} ${errorText}`);
  }

  return resolveActiveGameId(createResp);
}
