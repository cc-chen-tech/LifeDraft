/**
 * Network Monitor Helper - 网络监控辅助函数
 *
 * 用于在E2E测试中监控API调用，捕获404/500错误
 */

import { Page, Request, Response } from '@playwright/test';

export interface NetworkError {
  url: string;
  method: string;
  status: number;
  statusText: string;
  timestamp: string;
  body?: string;
}

export interface NetworkMonitor {
  errors: NetworkError[];
  requests: Request[];
  responses: Response[];
  get4xxErrors: () => NetworkError[];
  get5xxErrors: () => NetworkError[];
  get404Errors: () => NetworkError[];
  clear: () => void;
}

/**
 * 启动网络监控，捕获所有API请求和响应
 */
export function startNetworkMonitoring(page: Page): NetworkMonitor {
  const monitor: NetworkMonitor = {
    errors: [],
    requests: [],
    responses: [],

    get4xxErrors: () => monitor.errors.filter(e => e.status >= 400 && e.status < 500),
    get5xxErrors: () => monitor.errors.filter(e => e.status >= 500),
    get404Errors: () => monitor.errors.filter(e => e.status === 404),

    clear: () => {
      monitor.errors = [];
      monitor.requests = [];
      monitor.responses = [];
    },
  };

  // 监听所有请求
  page.on('request', (request) => {
    if (request.url().includes('/api/')) {
      monitor.requests.push(request);
    }
  });

  // 监听所有响应
  page.on('response', async (response) => {
    const url = response.url();
    if (!url.includes('/api/')) return;

    monitor.responses.push(response);

    const status = response.status();

    // 记录4xx和5xx错误
    if (status >= 400) {
      const request = response.request();
      let body = '';

      try {
        // 尝试读取错误响应体
        body = await response.text();
      } catch {
        // 忽略读取错误
      }

      const error: NetworkError = {
        url,
        method: request.method(),
        status,
        statusText: response.statusText(),
        timestamp: new Date().toISOString(),
        body: body.length > 500 ? body.substring(0, 500) + '...' : body,
      };

      monitor.errors.push(error);

      // 在控制台输出错误，方便调试
      console.error(`[Network Error] ${request.method()} ${url} - ${status} ${response.statusText()}`);
      if (status === 404) {
        // 检查是路由不存在还是资源不存在
        const isRouteNotFound = body.includes('Not Found') && !body.includes('game_id') && !body.includes('Game not found');
        if (isRouteNotFound) {
          console.error(`  → API endpoint not found. Check if frontend path matches backend route.`);
        } else {
          console.error(`  → Resource not found (expected for new users without active game).`);
        }
      }
    }
  });

  // 监听请求失败
  page.on('requestfailed', (request) => {
    const url = request.url();
    if (!url.includes('/api/')) return;

    const error: NetworkError = {
      url,
      method: request.method(),
      status: 0,
      statusText: request.failure()?.errorText || 'Request Failed',
      timestamp: new Date().toISOString(),
    };

    monitor.errors.push(error);
    console.error(`[Request Failed] ${request.method()} ${url} - ${error.statusText}`);
  });

  return monitor;
}

/**
 * 等待所有网络请求完成
 */
export async function waitForNetworkIdle(page: Page, timeout = 5000): Promise<void> {
  try {
    await page.waitForLoadState('networkidle', { timeout });
  } catch {
    // 超时忽略，继续执行
  }
}

/**
 * 格式化网络错误报告
 */
export function formatNetworkErrors(errors: NetworkError[]): string {
  if (errors.length === 0) {
    return 'No network errors detected.';
  }

  const lines = [
    `Network Errors Summary (${errors.length} errors):`,
    '─────────────────────────────────────────────────',
  ];

  // 按状态码分组
  const byStatus = errors.reduce((acc, error) => {
    acc[error.status] = acc[error.status] || [];
    acc[error.status].push(error);
    return acc;
  }, {} as Record<number, NetworkError[]>);

  Object.entries(byStatus).forEach(([status, errs]) => {
    lines.push(`\n[Status ${status}] ${errs.length} error(s):`);
    errs.forEach(e => {
      lines.push(`  ${e.method} ${e.url}`);
      if (e.status === 404) {
        lines.push(`  → Endpoint not found - check API path`);
      }
    });
  });

  return lines.join('\n');
}
