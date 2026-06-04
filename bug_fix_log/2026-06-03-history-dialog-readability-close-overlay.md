# 2026-06-03 History Dialog Readability And Close Overlay

## Problem

历史回顾抽屉关闭和阅读体验不稳定：

- Close click 关闭后，Sheet 的关闭态 overlay/content 仍可能在动画期间接收 pointer events，挡住页面后续控件。
- 选择历史轮次后，抽屉仍遮住主阅读区，用户不清楚是否已经进入完整正文阅读。
- 历史列表主要展示摘要，选中项没有在抽屉内展示完整 `event_description` 和 `story_continuation`。

## Root Cause

- `frontend/src/components/ui/sheet.tsx` 的 `SheetOverlay` 和 `SheetContent` 只有关闭动画类，没有 `data-[state=closed]:pointer-events-none`，关闭动画中的遮罩仍可拦截点击。
- `frontend/src/components/game/RoundHistoryDrawer.tsx` 的轮次按钮只调用 `onSelect`，不会关闭抽屉露出 play 页面上的历史正文阅读面板。
- 选中历史轮次时，drawer 仍只显示摘要和选择文本，没有把完整历史正文作为可读内容展示。
- `frontend/src/hooks/game/useHistoryViewer.ts` 进入历史模式已经不改变 live phase，但返回当前时仍恢复进入历史前备份的 phase。若用户阅读历史期间后台生成从 `loading` 进入 `options`，返回时可能被旧 `loading` 回滚。

## Tests

新增/加强定向测试：

- Close button calls `onOpenChange(false)`.
- Escape calls `onOpenChange(false)`.
- Sheet overlay has a closed-state non-interactive CSS contract.
- Selecting a history round closes the drawer to expose the readable story surface.
- Selected history round shows full event and post-choice continuation content.
- `useHistoryViewer` keeps selected history text pinned when current story text changes.
- Returning from history does not rewind the live phase.
- If the live phase advances from `loading` to `options` while reading history, returning does not restore stale `loading`.

Red run before fix:

```bash
cd frontend
npx jest --runInBand src/__tests__/components/RoundHistoryDrawer.test.tsx src/__tests__/hooks/useHistoryViewer.test.ts
```

Observed failures:

- Missing `data-[state=closed]:pointer-events-none` on overlay.
- Selecting a round did not call `onOpenChange(false)`.
- Selected item did not show full historical body.

## Fix

- Added `data-[state=closed]:pointer-events-none` to Sheet overlay and content.
- Changed history round selection to call `onSelect(index)` and then `onOpenChange(false)`.
- Kept the existing `已记录` badge, added an explicit `点击阅读正文` hint, and rendered the selected full history body inline with a separate `选择后的故事发展` section.
- Removed stale phase restoration on return from history. History mode keeps its own `historyDisplayText` and clears only history UI state on return; it does not overwrite the live game phase.

## Verification

Targeted frontend tests only:

```bash
cd frontend
npx jest --runInBand src/__tests__/pages/PlayPage.test.tsx src/__tests__/components/RoundHistoryDrawer.test.tsx src/__tests__/hooks/useHistoryViewer.test.ts
```

Result after review fix: 3 test suites passed, 89 tests passed.
