/**
 * Playwright Global Setup - 服务器健康检查与自动启动
 *
 * 在所有测试开始前执行：
 * 1. 检查前端 (port 3000) 是否可达
 * 2. 检查后端 (port 8000) 是否可达
 * 3. 后端不可达时自动启动
 * 4. 验证 AI API 连通性（可选，不阻塞非 AI 测试）
 */

import { execSync, spawn, ChildProcess } from 'child_process';
import * as path from 'path';
import { existsSync } from 'fs';

const FRONTEND_URL = 'http://localhost:3000';
const BACKEND_URL = 'http://localhost:8000';
const BACKEND_HEALTH_ENDPOINT = `${BACKEND_URL}/api/games`;
const PROJECT_ROOT = path.resolve(__dirname, '..', '..');

/** 存储后端进程引用，供 teardown 使用 */
let backendProcess: ChildProcess | null = null;

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

function startBackend(): ChildProcess {
  const venvPythonPath = path.join(PROJECT_ROOT, 'venv', 'bin', 'python3');
  const pythonPath = existsSync(venvPythonPath)
    ? venvPythonPath
    : (process.env.PYTHON || process.env.PYTHON_BIN || 'python3');
  const apiScript = path.join(PROJECT_ROOT, 'run_api.py');

  console.log(`  → 启动后端: ${pythonPath} ${apiScript}`);
  const proc = spawn(pythonPath, [apiScript], {
    cwd: PROJECT_ROOT,
    stdio: ['ignore', 'pipe', 'pipe'],
    detached: false,
    env: { ...process.env },
  });

  proc.stdout?.on('data', (data: Buffer) => {
    const msg = data.toString().trim();
    if (msg) console.log(`  [backend] ${msg}`);
  });

  proc.stderr?.on('data', (data: Buffer) => {
    const msg = data.toString().trim();
    if (msg && !msg.includes('WARNING')) console.error(`  [backend] ${msg}`);
  });

  proc.on('error', (err) => {
    console.error(`  [backend] 启动失败: ${err.message}`);
  });

  return proc;
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
    console.log(`  ⚠ 后端未运行，尝试自动启动...`);

    backendProcess = startBackend();
    (globalThis as any).__e2e_backend_process = backendProcess;

    const started = await waitForService(BACKEND_HEALTH_ENDPOINT, '后端', 30_000);
    if (!started) {
      console.error('\n  ✗ 后端启动失败！E2E 测试需要后端运行在 port 8000');
      console.error(`    请手动启动: cd ${PROJECT_ROOT} && python3 run_api.py\n`);
      // 不抛异常 - 让测试自行处理后端不可用的情况
      // 非 AI 测试可能不依赖后端某些功能
    }
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
