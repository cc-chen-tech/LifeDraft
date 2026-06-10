# QA Fix Record - 主页「新游戏」按钮导航阻塞

## 问题来源
- 时间：2026-06-10
- 来源证据：`docs/qa-evidence/2026-06-10-heartbeat-1712/notes.md`
- 现象：主页中点击「新游戏」在已登录态会跳到 `/create`，但自动化点击动作可能不返回（agent-browser 侧表现为进程挂住），无法形成稳定的按钮交互闭环。

## 根因判断
- 欢迎页中「新游戏」按钮使用 `onClick` 内部直接调用 `router.push('/create')`，按钮没有 href 可直接命中，某些自动化栈会在导航动作上异常阻塞。

## 修复措施
1. `frontend/src/app/page.tsx`
   - 将已登录态的「新游戏」按钮改为基于 Next `Link` 的可导航目标。
   - 保留按钮样式：`<Button asChild>`。
   - 已登录态通过 `href="/create"` 命中目标，并在 `onClick` 中调用 `resetCreation()`。
   - 未登录态行为不变：继续打开注册弹层（保留原有 `setAuthMode("register")`）。
2. `frontend/src/__tests__/pages/WelcomePage.test.tsx`
   - 更新认证态用例为验证 `新游戏` 按钮存在 `href="/create"` 并触发 `resetCreation`，不再依赖 `router.push` mock。
3. `frontend/e2e/user-journey.spec.ts`
   - 在“新游戏点击跳转”用例中补充导航目标属性校验：`href == /create`。
   - 补充点击耗时断言（`< 5000ms`），用于持续检测“点击动作返回”风险。

## 验证结果
- `cd frontend && npm run test:unit -- WelcomePage.test.tsx`：通过
- `cd frontend && npm run test:types`：通过
- `cd frontend && CI=1 E2E_NO_SANDBOX=0/1 npx playwright test e2e/user-journey.spec.ts --project=core --grep "should navigate to create page on new game click" --workers=1`：在当前运行环境受限于 macOS Chromium 启动权限（`bootstrap_check_in ... Permission denied (1100)`），Playwright 无法稳定启动，未能获得浏览器层执行结论

## 后续建议
- 建议在允许 Playwright 启动的环境重跑该单条回归：
  - `CI=1 npx playwright test e2e/user-journey.spec.ts --project=core --grep "should navigate to create page on new game click" --workers=1`
- 上线后在 `story101.live` 手工复测一次：
  - 登录态首页点击「新游戏」应直接进入 `/create`，并且点击动作不会在自动化/脚本侧挂起。
