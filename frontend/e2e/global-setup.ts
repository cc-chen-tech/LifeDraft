/**
 * Playwright Global Setup - 服务器健康检查
 *
 * 在所有测试开始前执行：
 * 1. 检查前端 (configured port) 是否可达
 * 2. 检查后端 (port 8000) 是否可达
 * 3. 验证 AI API 连通性（可选，不阻塞非 AI 测试）
 */

const FRONTEND_URL = `http://localhost:${process.env.E2E_FRONTEND_PORT ?? '3000'}`;
const BACKEND_HOST = process.env.E2E_BACKEND_HOST || '127.0.0.1';
const BACKEND_PORT = process.env.E2E_BACKEND_PORT || '8000';
const BACKEND_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}`;

async function checkService(url: string, label: string, timeoutMs = 5000): Promise<boolean> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const resp = await fetch(url, { signal: controller.signal });
    clearTimeout(timer);
    // 任何 HTTP 响应（包括 401/404）都说明服务在运行
    return resp.status > 0;
  } catch {
    clearTimeout(timer);
    return false;
  }
}

async function waitForService(url: string, label: string, maxWaitMs = 30_000): Promise<boolean> {
  const start = Date.now();
  const interval = 2000;
  while (Date.now() - start < maxWaitMs) {
    if (await checkService(url, label)) {
      console.log(`  ✓ ${label} 就绪 (${url})`);
      return true;
    }
    await new Promise(r => setTimeout(r, interval));
  }
  return false;
}

export default async function globalSetup() {
  console.log('\n╔══════════════════════════════════════════╗');
  console.log('║   E2E Global Setup - 服务健康检查         ║');
  console.log('╚══════════════════════════════════════════╝\n');

  // 1. 检查前端
  const frontendAlive = await checkService(FRONTEND_URL, '前端');
  if (frontendAlive) {
    console.log(`  ✓ 前端就绪 (${FRONTEND_URL})`);
  } else {
    // 前端由 Playwright webServer 管理，这里只做提示
    console.log(`  ⚠ 前端未就绪 (${FRONTEND_URL}) - 将由 Playwright webServer 启动`);
  }

  // 2. 检查后端
  const backendAlive = await checkService(BACKEND_URL, '后端');
  if (backendAlive) {
    console.log(`  ✓ 后端就绪 (${BACKEND_URL})`);
  } else {
    const backendBecameAlive = await waitForService(BACKEND_URL, '后端', 15_000);
    if (backendBecameAlive) {
      console.log(`  ✓ 后端就绪 (${BACKEND_URL})`);
    } else {
      console.warn(`  ⚠ 后端未就绪 (${BACKEND_URL})，继续执行测试并允许该场景自适应退化`);
    }
  }

  // 3. 检查 AI API 连通性（informational only）
  try {
    const aiCheckResp = await fetch(`${BACKEND_URL}/docs`, {
      signal: AbortSignal.timeout(5000),
    });
    if (aiCheckResp.ok) {
      console.log(`  ✓ 后端 API 文档可达`);
    }
  } catch {
    // 不阻塞
  }

  console.log('\n  健康检查完成，开始运行测试...\n');
}
