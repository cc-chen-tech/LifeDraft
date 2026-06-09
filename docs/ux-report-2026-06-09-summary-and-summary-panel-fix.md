# 2026-06-09 人生总结与面板互斥修复记录

## 已复现问题

1. 人生总结面板在单周区间时会显示 `第1-1周` 这类冗余文案。
2. 历史回顾与收集在边缘交互中未形成完整回归测试，点击历史入口后未验证会回归到当前模式。

## 代码修复

- `frontend/src/components/game/ChatBar.tsx`
  - 新增 `getSummaryWeekLabel`：当 `startWeek === endWeek` 时显示 `第N周`，否则保留 `第M-N周`。
  - `handleGenerateSummary` 中将 `endWeek` 回退到 `startWeek`，避免出现 `第1-0周`。
  - 渲染时使用 `getSummaryWeekLabel` 替换固定 `第{startWeek}-{endWeek}周`。

- `frontend/src/__tests__/pages/PlayPage.test.tsx`
  - 覆盖历史→收集切换链路的状态回归，验证「先关闭历史再打开收集」与「收集打开后返回当前模式再可切换」行为。

## 测试与文档

- 单元测试：
  - `frontend/src/__tests__/components/ChatBar.test.tsx`
    - `renders a single-week summary title as 第N周`
    - `normalizes invalid end week to start week before rendering`
    - `normalizes end week smaller than start week to start week`
    - `normalizes invalid start week to 1 and keeps label readable`
  - `frontend/src/__tests__/pages/PlayPage.test.tsx`
    - `returns to current mode when opening collection before switching to history`
    - `closes history mode before opening collection panel`

- 现有面板互斥 e2e 回归保留：
  - `frontend/e2e/collection-panel-cache.spec.ts`
    - `历史回顾与收集面板不能同时打开`

- 执行命令：
  - `cd frontend && npx jest src/__tests__/components/ChatBar.test.tsx src/__tests__/pages/PlayPage.test.tsx --runInBand`
  - `cd /Users/luicy/story2 && ./test.sh all`

## 结论

问题已按单测+功能修复闭环。`人生总结` 在单周场景下的标题会显示为 `第1周`，不再出现 `第1-1周`。

并行覆盖结论：

- 全链路验证覆盖了静态层（preflight）、mypy、imports、contract、real-db、E2E 浏览器层。
- 当前工作区 `frontend/src/components/game/ChatBar.tsx` 与 `frontend/src/__tests__/pages/PlayPage.test.tsx` 对应的回归行为在单测中通过，且无额外功能回归信号。
- 未发现新增的高优先级回归；其余历史问题可继续通过 `./test.sh all` 持续监控。
