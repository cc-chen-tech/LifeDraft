# 2026-06-09 记录面板互斥修复

## 问题复现

在 `/play` 页面，历史回顾和收集面板分别由独立 state 控制。若用户处于历史阅读模式，或代码路径在打开一个面板前未关闭另一个面板，会出现“历史状态仍保留 + 收集面板打开”的不一致状态。

实际影响：
- 页面仍按历史阅读模式隐藏当前轮次交互，但收集面板覆盖在其上。
- 从收集再进入历史回顾时，两个入口缺少统一互斥边界，后续关闭和返回当前轮次行为不一致。
- E2E 中不能直接点击 modal sheet 背后的顶栏按钮；该路径不符合 Radix Sheet 的可访问模型，因此回归测试改为覆盖真实用户可点击的切换路径，并用单测覆盖 handler 级互斥。

## 修复内容

- 在 `frontend/src/app/play/page.tsx` 新增互斥入口函数：
  - `handleOpenCollection`：先 `setShowCollection(true)`，再 `setShowHistory(false)`；如果当前处于历史阅读模式，则调用 `handleBackToCurrent()` 回到当前轮次。
  - `handleOpenHistoryPanel`：先 `setShowCollection(false)`，再触发 `handleOpenHistory()`。
- 将按钮回调分别绑定到上述函数，保证二者不能并存。

## 回归测试

### 单测（`frontend/src/__tests__/pages/PlayPage.test.tsx`）

- `Header actions > closes history mode before opening collection panel`
- `Header actions > opens history panel when history button clicked`
- 红绿验证：临时撤掉 `frontend/src/app/play/page.tsx` 的生产代码修复后，`closes history mode before opening collection panel` 失败；恢复修复后通过。

### E2E（`frontend/e2e/collection-panel-cache.spec.ts`）

- 新增用例：`历史回顾与收集面板不能同时打开`
- 该用例流程：
  1. 打开历史回顾
  2. 断言收集面板不可见
  3. 使用 Escape 关闭历史回顾
  4. 打开收集面板
  5. 断言历史回顾不可见
  6. 使用 Escape 关闭收集面板
  7. 再次打开历史回顾
  8. 断言收集面板不可见

## 验证结果

- `npx jest src/__tests__/pages/PlayPage.test.tsx --runInBand --testNamePattern='closes history mode before opening collection panel|opens history panel when history button clicked'`：通过，2 passed。
- `./test.sh frontend`：通过；TypeScript 通过，Jest 99 suites / 1722 passed / 4 skipped，integration 1 suite / 4 passed。
- `TEST_RUN_ROOT=/tmp/story2-codex-test-runs TEST_NAMESPACE=history_collection_1780968988 ./test.sh e2e`：通过。
  - core：302 passed。
  - member AI music queue：1 passed。
  - character settings persistence：1 passed。
  - story voice reading：8 passed。
  - MiniMax story audio generation：4 passed。
  - collection recognition/cache/entity：27 passed，其中新增 `历史回顾与收集面板不能同时打开` 通过。

## 验证过程中的环境问题

一次 repo-local `.test-runs` 根目录运行失败，首个共同错误为 SQLite `attempt to write a readonly database`，随后注册、收集、实体识别等用例级联失败。失败期间还出现 `tee: .../playwright/...log: No such file or directory`，说明运行目录在测试中途被移除或不可写。该失败与面板互斥逻辑无直接关联。改用 `/tmp/story2-codex-test-runs` 作为 `TEST_RUN_ROOT` 后，同一浏览器层完整通过。
