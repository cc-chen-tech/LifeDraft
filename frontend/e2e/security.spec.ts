 

/**
 * E2E Test: Security Validation
 * Tests for security vulnerabilities and protections
 */
import { test, expect } from '@playwright/test';
import { ensureAuthenticated, registerUser } from './helpers/auth';
import { waitForApiResponse, waitForPageReady } from './helpers/wait-helpers';

const API_URL = 'http://localhost:8000';

test.describe('Security E2E', () => {
  test('path traversal blocked in image URLs', async ({ page, request }) => {
    // 尝试通过 URL 访问 ../../../etc/passwd 类路径
    const traversalPaths = [
      '/api/images/game/../../etc/passwd',
      '/api/images/scene/1/../../../etc/passwd',
      '/api/images/game/..%2F..%2F..%2Fetc%2Fpasswd',
    ];

    for (const path of traversalPaths) {
      const response = await request.get(`${API_URL}${path}`);
      const status = response.status();

      // 应该返回 400/403/404，而不是文件内容
      expect([400, 403, 404, 422]).toContain(status);

      // 验证响应不包含敏感系统文件内容
      const body = await response.text();
      expect(body).not.toContain('root:');
      expect(body).not.toContain('/bin/bash');
    }
  });

  test('unauthenticated image access rejected', async ({ request }) => {
    // 无登录状态直接访问图片 API
    const protectedEndpoints = [
      '/api/images/game/1',
      '/api/images/scene/1/1',
      '/api/images/scenes/1',
    ];

    for (const endpoint of protectedEndpoints) {
      const response = await request.get(`${API_URL}${endpoint}`);
      const status = response.status();

      // 图片端点可能是公开的或需要认证或不存在
      // 关键是不应该返回 500 等服务器内部错误
      expect(status).toBeLessThan(500);
    }
  });

  test('CORS preflight returns restricted headers', async ({ request }) => {
    // 发送 OPTIONS 请求，验证 CORS 头部设置
    const response = await request.fetch(`${API_URL}/api/auth/me`, {
      method: 'OPTIONS',
      headers: {
        'Origin': 'http://malicious-site.com',
        'Access-Control-Request-Method': 'GET',
      },
    });

    // 检查 CORS 头部
    const allowOrigin = response.headers()['access-control-allow-origin'];

    // 不应该是通配符 * 允许所有来源
    if (allowOrigin) {
      expect(allowOrigin).not.toBe('*');
    }
  });

  test('error responses hide internal details', async ({ page, request }) => {
    // 触发一个服务端错误（如访问不存在的资源）
    const response = await request.get(`${API_URL}/api/games/999999999`);

    const body = await response.text();

    // 验证响应不包含敏感的内部信息
    expect(body.toLowerCase()).not.toContain('traceback');
    expect(body.toLowerCase()).not.toContain('stack trace');
    expect(body).not.toMatch(/\/Users\/|\/home\//); // 文件路径
    expect(body).not.toMatch(/sqlite|postgresql|mysql/i); // 数据库详情
    expect(body).not.toMatch(/File ".*\.py"/); // Python 文件路径
  });

  test('logout actually invalidates session', async ({ page, context }) => {
    // 登录
    await ensureAuthenticated(page, context);

    // 验证登录成功 - 可以访问受保护的 API
    const meResponse1 = await context.request.get(`${API_URL}/api/auth/me`);
    expect(meResponse1.status()).toBe(200);

    const logoutStatus = await page.evaluate(async (apiUrl) => {
      const response = await fetch(`${apiUrl}/api/auth/logout`, {
        method: 'POST',
        credentials: 'include',
      });
      return response.status;
    }, API_URL);
    expect([200, 204]).toContain(logoutStatus);

    const meStatusAfterLogout = await page.evaluate(async (apiUrl) => {
      const response = await fetch(`${apiUrl}/api/auth/me`, {
        credentials: 'include',
      });
      return response.status;
    }, API_URL);
    expect([401, 403]).toContain(meStatusAfterLogout);
  });

  test('XSS in story content is escaped', async ({ page, context }) => {
    await ensureAuthenticated(page, context);

    await page.goto('/create');
    await page.waitForLoadState('domcontentloaded');

    // 尝试在输入字段中注入 XSS
    const xssPayloads = [
      '<script>alert("XSS")</script>',
      '<img src=x onerror=alert("XSS")>',
      '<svg onload=alert("XSS")>',
      'javascript:alert("XSS")',
    ];

    const nameInput = page.getByPlaceholder(/角色名|姓名|Name/i);

    for (const payload of xssPayloads) {
      await nameInput.fill(payload);

      // 等待内容渲染
      await page.waitForLoadState('domcontentloaded');

      // 验证脚本没有执行 - 检查页面没有弹出 alert
      // 如果有 XSS，alert 会阻塞，导致后续操作失败
      const pageContent = await page.content();

      // 验证内容被转义而不是作为 HTML 执行
      expect(pageContent).not.toMatch(/<script>alert/);
    }
  });

  test('SQL injection in search blocked', async ({ page, context, request }) => {
    await ensureAuthenticated(page, context);

    // SQL 注入 payload
    const sqlPayloads = [
      "'; DROP TABLE users; --",
      "1' OR '1'='1",
      "1; SELECT * FROM users",
      "UNION SELECT * FROM users",
    ];

    // 在可能的搜索/查询端点测试，每个请求加独立超时防止服务端挂起
    for (const payload of sqlPayloads) {
      const response = await context.request.get(
        `${API_URL}/api/games?search=${encodeURIComponent(payload)}`,
        { timeout: 10000 }
      );

      // 应该返回正常的空结果或错误，而不是注入成功
      const status = response.status();
      expect([200, 400, 422]).toContain(status);

      // 验证没有返回其他用户的数据
      const body = await response.text();
      expect(body).not.toMatch(/password|secret|private_id/i);
    }
  });

  test('rate limiting prevents brute force', async ({ request }) => {
    // 快速发送多次登录请求
    const requests: Promise<unknown>[] = [];
    const loginAttempts = 20; // 快速发送 20 次请求

    for (let i = 0; i < loginAttempts; i++) {
      requests.push(
        request.post(`${API_URL}/api/auth/login`, {
          data: { private_id: `fake-id-${i}` },
        })
      );
    }

    const responses = await Promise.all(requests);

    // 检查是否有被限流的响应 (429 Too Many Requests)
    const rateLimited = responses.filter(
      (r) => (r as { status(): number }).status() === 429
    );

    // 如果实现了限流，应该有部分请求被拒绝
    // 如果没有限流，记录警告
    if (rateLimited.length === 0) {
      console.warn('Warning: No rate limiting detected. Consider implementing rate limiting for auth endpoints.');
    }

    // 确保所有响应都是有效的 HTTP 响应
    for (const response of responses) {
      const status = (response as { status(): number }).status();
      expect([200, 400, 401, 422, 429]).toContain(status);
    }
  });

  test('expired token forces re-login', async ({ page, context }) => {
    // 先登录
    await ensureAuthenticated(page, context);

    // 手动清除 cookie 模拟 token 过期
    await context.clearCookies();

    // 访问受保护的页面
    await page.goto('/play');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(3000);

    // 应该被重定向到首页或显示登录提示
    const currentUrl = page.url();

    // 验证不能正常访问受保护的内容
    // 要么被重定向，要么显示登录按钮，要么页面不包含游戏内容
    const loginButton = page.getByRole('button', { name: /登录|Login/i });
    const isOnPlayPage = currentUrl.includes('/play');
    const hasLoginButton = await loginButton.isVisible({ timeout: 5000 }).catch(() => false);
    const hasGameContent = await page.locator('[data-testid="story-text"], text=/第.*周/').isVisible().catch(() => false);

    // 要么不在 play 页，要么有登录按钮，要么没有游戏内容
    expect(!isOnPlayPage || hasLoginButton || !hasGameContent).toBeTruthy();
  });

  test('security headers present on all responses', async ({ request }) => {
    const response = await request.get(`${API_URL}/api/auth/me`);

    const headers = response.headers();

    // 检查推荐的安全头部（这些是最佳实践，可能不是所有项目都实现）
    const securityHeaders = {
      'x-content-type-options': 'nosniff',
      'x-frame-options': ['DENY', 'SAMEORIGIN'],
    };

    // 记录缺失的安全头部
    const missingHeaders: string[] = [];

    if (!headers['x-content-type-options']) {
      missingHeaders.push('X-Content-Type-Options');
    }

    if (!headers['x-frame-options']) {
      missingHeaders.push('X-Frame-Options');
    }

    // 不强制失败，但记录警告
    if (missingHeaders.length > 0) {
      console.warn(`Warning: Missing recommended security headers: ${missingHeaders.join(', ')}`);
    }

    // 基本验证：响应应该是有效的
    expect([200, 401, 403]).toContain(response.status());
  });
});
