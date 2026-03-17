/**
 * E2E 测试辅助函数 - 认证相关
 *
 * ★ 使用纯 Cookie 认证（httpOnly）
 * - 不再使用 localStorage 存储 token
 * - 通过 Cookie 自动发送认证信息
 */
import { Page, BrowserContext, APIRequestContext } from '@playwright/test';

const API_URL = 'http://localhost:8000';

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
    return data;
  }
  return null;
}

/**
 * 确保用户已登录（如果没有则注册新用户）
 * 使用 Cookie 自动管理认证状态
 */
export async function ensureAuthenticated(page: Page, context: BrowserContext): Promise<void> {
  // 先访问页面
  await page.goto('/');

  // 尝试点击"新游戏"按钮，如果弹出登录框则需要认证
  const newGameButton = page.getByRole('button', { name: /新游戏|New Game/i });
  await newGameButton.click();

  // 等待短暂时间看是否出现登录/注册弹窗
  await page.waitForTimeout(500);

  // 检查是否出现了注册输入框（未登录状态）
  const nameInput = page.getByPlaceholder(/你的名字/i);
  const isLoginSheetVisible = await nameInput.isVisible().catch(() => false);

  if (isLoginSheetVisible) {
    // 未登录，需要注册
    await nameInput.fill(`TestUser_${Date.now()}`);

    const submitButton = page.getByRole('button', { name: /创建账户|登录/i }).first();
    await submitButton.click();

    // 等待注册完成（等待弹窗关闭或显示 private_id）
    await page.waitForTimeout(1000);

    // 如果有继续按钮，点击关闭弹窗
    const continueButton = page.getByRole('button', { name: /继续|确定|OK/i }).first();
    if (await continueButton.isVisible().catch(() => false)) {
      await continueButton.click();
    }
  } else {
    // 已经登录，点击新游戏可能已经导航了，返回首页
    await page.goto('/');
  }
}
