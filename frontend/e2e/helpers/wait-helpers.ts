import { Page, Response } from '@playwright/test';

/**
 * 等待匹配 URL 模式的 API 响应完成
 */
export async function waitForApiResponse(
  page: Page,
  urlPattern: string | RegExp,
  options?: { timeout?: number; status?: number }
): Promise<Response> {
  const timeout = options?.timeout ?? 10000;
  const response = await page.waitForResponse(
    (resp) => {
      const matches = typeof urlPattern === 'string'
        ? resp.url().includes(urlPattern)
        : urlPattern.test(resp.url());
      if (options?.status) {
        return matches && resp.status() === options.status;
      }
      return matches;
    },
    { timeout }
  );
  return response;
}

/**
 * 等待 DOM 元素稳定（内容不再变化）
 */
export async function waitForStableDOM(
  page: Page,
  selector: string,
  options?: { timeout?: number; stableTime?: number }
): Promise<void> {
  const timeout = options?.timeout ?? 10000;
  const stableTime = options?.stableTime ?? 500;
  
  const startTime = Date.now();
  let lastContent = '';
  let stableSince = Date.now();
  
  while (Date.now() - startTime < timeout) {
    const currentContent = await page.locator(selector).textContent().catch(() => null);
    if (currentContent !== lastContent) {
      lastContent = currentContent ?? '';
      stableSince = Date.now();
    } else if (Date.now() - stableSince >= stableTime) {
      return;
    }
    await page.waitForTimeout(100); // 短暂轮询间隔
  }
  
  throw new Error(`DOM element "${selector}" did not stabilize within ${timeout}ms`);
}

/**
 * 等待网络空闲（无进行中的请求）
 */
export async function waitForNetworkIdle(
  page: Page,
  options?: { timeout?: number; idleTime?: number }
): Promise<void> {
  const timeout = options?.timeout ?? 15000;
  const idleTime = options?.idleTime ?? 500;
  
  await page.waitForLoadState('domcontentloaded', { timeout });
}

/**
 * 等待元素可见并稳定（不再移动）
 */
export async function waitForElementStable(
  page: Page,
  selector: string,
  options?: { timeout?: number }
): Promise<void> {
  const timeout = options?.timeout ?? 10000;
  const locator = page.locator(selector);
  await locator.waitFor({ state: 'visible', timeout });
  // 等待元素位置稳定
  let lastBox = await locator.boundingBox();
  const startTime = Date.now();
  while (Date.now() - startTime < timeout) {
    await page.waitForTimeout(100);
    const currentBox = await locator.boundingBox();
    if (
      lastBox && currentBox &&
      lastBox.x === currentBox.x &&
      lastBox.y === currentBox.y &&
      lastBox.width === currentBox.width &&
      lastBox.height === currentBox.height
    ) {
      return;
    }
    lastBox = currentBox;
  }
}

/**
 * 等待页面加载完成（替代 waitForTimeout）
 */
export async function waitForPageReady(
  page: Page,
  options?: { timeout?: number }
): Promise<void> {
  const timeout = options?.timeout ?? 10000;
  await page.waitForLoadState('domcontentloaded', { timeout });
  await page.waitForLoadState('domcontentloaded', { timeout });
}

/**
 * 移除 Next.js Dev Overlay，防止在 E2E 测试中拦截点击事件
 * 使用 addInitScript 在每次页面加载时自动移除
 */
export async function dismissNextJSDevOverlay(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const removeOverlay = () => {
      const portals = document.querySelectorAll('nextjs-portal');
      portals.forEach((p) => p.remove());
      const devToolButtons = document.querySelectorAll('[data-nextjs-dev-tools-button]');
      devToolButtons.forEach((b) => b.remove());
    };
    removeOverlay();
    const observer = new MutationObserver(removeOverlay);
    if (document.documentElement) {
      observer.observe(document.documentElement, { childList: true, subtree: true });
    }
  });
}
