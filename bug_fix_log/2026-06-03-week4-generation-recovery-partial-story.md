# 2026-06-03 第四周生成恢复卡死修复

## 问题

线上 `story101.live` 深度体验到第 4 周时，页面长时间停在 `故事生成中...`。刷新 `/play` 后只显示 `恢复当前进度`，点击恢复仍不能展示正文或选项；但点击 `总结` 后又能恢复出故事和选项，说明后端或本地状态里已经存在可恢复内容，前端恢复路径没有正确展示。

## 复现证据

- 第 4 周生成 75 秒后仍停留在生成态：`/tmp/story101-0603-week4-state-after-75s.png`
- 继续等待约 90 秒后仍停留在生成态：`/tmp/story101-0603-week4-still-after-extra-90s.png`
- 刷新后只有恢复入口：`/tmp/story101-0603-week4-after-refresh.png`
- 点击恢复后仍没有正文或选项：`/tmp/story101-0603-week4-restore-current.png`
- 点击总结后意外恢复出选项，证明存在可恢复状态：`/tmp/story101-0603-week4-summary-blocked-state.png`

## 根因

`useEventGenerator` 在 SSE 报错后会轮询 `syncState()`，但原逻辑只把 `currentEvent.options.length > 0` 视为恢复成功。如果后端已经保存了正文，但选项仍为空或还在生成，前端会忽略这段正文，最终进入错误态或继续停在恢复入口。

同时 `parseSSEStream` 收到 `event: error` 后，流结束时仍会补发一次空 `onComplete({})`。如果后端先发 error 再发 `[DONE]`，原 `[DONE]` 分支也会补发空 complete。这会让上层同时经历错误和空完成事件，容易覆盖真正的错误恢复路径。

## 测试

先新增失败用例：

- `frontend/src/__tests__/hooks/useEventGenerator.test.ts`
  - `surfaces recovered partial story instead of staying in generation recovery forever`
  - 模拟 SSE timeout error。
  - 模拟 `syncState()` 恢复到只有正文、没有选项的 `currentEvent`。
  - 断言前端会展示正文，并进入带恢复控件的错误态，而不是继续空白生成。

补充 SSE 合同测试：

- `frontend/src/__tests__/lib/sse.test.ts`
  - `does not emit empty complete after an error event`
  - 断言收到 error event 后不会再触发空 `onComplete({})`。
  - `does not emit empty complete when an error event is followed by DONE`
  - 断言 error 后即使收到 `[DONE]` 也不会触发空 `onComplete({})`。

## 修复

- `frontend/src/hooks/game/useEventGenerator.ts`
  - SSE 错误轮询期间，如果发现 `currentEvent.story` 或 `storyText` 已恢复，即使没有选项，也立即写回 `storyText/currentEvent`。
  - 轮询超时后保留这段部分正文，并进入 `error` phase，让页面已有的正文加恢复控件可见。
  - 修正文案日志，从 5 分钟改为实际配置的 3 分钟。

- `frontend/src/lib/sse.ts`
  - 增加 `isErrorReceived` 标记。
  - 流结束时如果已经收到 error event，不再补发空 complete。
  - `[DONE]` 分支同样检查 `isErrorReceived`，避免 error 后的 DONE 覆盖错误恢复。

## 验证

- `npx jest src/__tests__/lib/sse.test.ts --runInBand`
  - SSE error/DONE 边界用例先失败，修复后 27 个 SSE 测试通过。

- `npx jest src/__tests__/hooks/useEventGenerator.test.ts --runInBand`
  - 新增恢复用例先失败，修复后通过。

后续集成前仍需要在本地浏览器完整走一轮 `/play` 生成恢复路径，并在 PR 前跑更大范围测试。
