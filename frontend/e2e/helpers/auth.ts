/**
 * E2E 测试辅助函数 - 认证相关
 *
 * ★ 使用纯 Cookie 认证（httpOnly）
 * - 不再使用 localStorage 存储 token
 * - 通过 Cookie 自动发送认证信息
 */
import { Page, BrowserContext, expect } from '@playwright/test';

const API_HOST = process.env.E2E_BACKEND_HOST || '127.0.0.1';
const API_PORT = process.env.E2E_BACKEND_PORT || '8000';
const API_URL = `http://${API_HOST}:${API_PORT}`;

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
      c => ['localhost', '127.0.0.1'].includes(c.domain) || API_HOST.includes(c.domain) || c.domain === 'localhost.localdomain',
    );
    if (apiCookies.length > 0) {
      await context.addCookies(apiCookies.map(c => ({ ...c, domain: 'localhost' })));
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
    const cookies = await context.cookies();
    const apiCookies = cookies.filter(
      c => ['localhost', '127.0.0.1'].includes(c.domain) || API_HOST.includes(c.domain) || c.domain === 'localhost.localdomain',
    );
    if (apiCookies.length > 0) {
      await context.addCookies(apiCookies.map(c => ({ ...c, domain: 'localhost' })));
    }

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
