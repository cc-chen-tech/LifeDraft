/**
 * Playwright Global Teardown - 清理由 globalSetup 启动的服务
 */

export default async function globalTeardown() {
  const backendProcess = (globalThis as any).__e2e_backend_process;
  if (backendProcess && !backendProcess.killed) {
    console.log('\n  → 关闭由测试启动的后端进程...');
    backendProcess.kill('SIGTERM');

    // 等待进程退出
    await new Promise<void>((resolve) => {
      const timeout = setTimeout(() => {
        backendProcess.kill('SIGKILL');
        resolve();
      }, 5000);

      backendProcess.on('exit', () => {
        clearTimeout(timeout);
        resolve();
      });
    });

    console.log('  ✓ 后端进程已关闭\n');
  }
}
