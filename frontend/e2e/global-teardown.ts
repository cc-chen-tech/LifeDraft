/**
 * Playwright Global Teardown - 仅保留清理钩子入口
 */

export default async function globalTeardown() {
  // test.sh 和执行脚本负责启动/关闭后端与前端进程
  return;
}
