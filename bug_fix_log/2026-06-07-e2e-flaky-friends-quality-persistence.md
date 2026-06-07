# E2E flaky：好友列表与叙事质量持久化修复记录

## 问题
本地运行 `./test.sh e2e` 时，core E2E 最终通过但出现两个 flaky：

1. `friends-system.spec.ts` 的双用户好友流程在接受好友请求后读取 B 用户好友列表时偶发 `read ECONNRESET`。
2. `quality-level-persistence.spec.ts` 在点击“大师”后立即刷新，偶发刷新后菜单仍显示 `unchecked`。

## 复现
- 运行 `./test.sh e2e`。
- Playwright 首次尝试中出现：
  - `apiRequestContext.get: read ECONNRESET` for `GET /api/friends`
  - `expect(...).toHaveAttribute("data-state", "checked")` 收到 `unchecked`
- 重试后通过，说明问题是 E2E 等待/瞬时连接稳定性，而不是稳定业务断言失败。

## 根因
1. 好友列表校验对同一后端连接的短暂 socket reset 没有有限重试。
2. 叙事质量菜单点击后，前端会先异步 PATCH `/api/games/{id}/settings`，测试在等待写入完成前 reload，导致 reload 读到旧的 `constraint_level`。

## 修复
1. 给好友流程的最终 `GET /api/friends` 增加只针对 `ECONNRESET` / `ECONNREFUSED` / `socket hang up` 的小范围重试；HTTP 非成功响应仍由原断言处理。
2. 叙事质量持久化测试在 reload 前等待 `/api/games/{id}/settings` 的 PATCH 响应成功。

## 验证
- 运行 focused E2E：
  - `npx playwright test e2e/friends-system.spec.ts e2e/quality-level-persistence.spec.ts --project=core --workers=1 --reporter=list --no-deps`
- 再运行 `./test.sh e2e` 或至少下一轮完整 E2E，确认不再出现 flaky。
