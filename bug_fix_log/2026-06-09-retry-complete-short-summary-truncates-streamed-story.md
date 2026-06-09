# Retry 完成事件短摘要截断长正文

日期：2026-06-09

## 问题

生产环境 `https://story101.live/play` 中，新游戏进入第 1 周后：

1. SSE 已经流式生成长正文，控制台显示故事长度曾到 2484 字。
2. 完成事件返回 `event_description` 和 3 个选项。
3. 前端日志显示 `Retry detected, forcing backend story (358 chars)`。
4. 页面最终正文被截断成约 358 字，并出现“在……的背景下”“你把……”这类拼接痕迹。

这是 P1 叙事展示质量问题。它不会阻断继续游戏，但会把已生成的完整正文替换成短摘要，直接损害故事质量和上下文连续性。

## 根因

`frontend/src/hooks/game/eventUtils.ts` 在收到 retry 标记后，只要 complete payload 有 `event_description`，就强制使用后端文本覆盖前端流式正文。

生产中 complete payload 的 `event_description` 可能只是事件摘要，而不是完整正文。当前端已经拿到完整流式正文时，强制覆盖会造成正文截断。

## 复现证据

- browser-agent session：`prod-create-a0411532`
- 角色：`许知夏`
- 游戏：`108`
- 控制台关键日志：
  - `[STORY] append ... total: 2484`
  - `[SSE] Complete event received, data keys: [event_description, options]`
  - `[onComplete] Retry detected, forcing backend story (358 chars)`
  - `[STORY] TRUNCATE: 2484 -> 358 chars`
- 页面正文出现短摘要拼接痕迹。

## 回归测试

- `frontend/src/__tests__/hooks/eventUtils.test.ts`
  - `keeps long retry stream when backend complete only returns a short event summary`
  - 覆盖 retry 场景下，前端已有长流式正文而 backend complete 只有短摘要时，不应覆盖长正文。

## 修复

1. 新增 `shouldKeepRetryStream()` 判断。
2. retry 场景下，如果前端正文足够长、backend 文本明显短很多、且两者不是前缀关系，则保留前端流式正文，仅使用 complete payload 的 options。
3. 保留原有行为：前端文本很短时仍用 backend story；backend 只有极短 fallback 时仍保留前端故事。

## 验证

- `npx jest src/__tests__/hooks/eventUtils.test.ts --runInBand --testNamePattern='handleEventComplete with retry|replaces raw streamed frontend text'`：4 passed
- `npx jest src/__tests__/hooks/eventUtils.test.ts --runInBand`：48 passed
- `npx jest src/__tests__/preflight/storyContinuityPreflight.test.tsx --runInBand`：3 passed
- `npx tsc --noEmit`：passed
- `./test.sh preflight`：passed
- 生产验证：部署 `2fca433a` 后，在 game `108` 刷新新 bundle，选择“细读合作条款”生成后续故事；控制台未再出现短 `event_description` 覆盖长 stream 的 `TRUNCATE`，页面保留长正文和轮次小结。

## 状态

已提交、推送、部署并通过生产后续选择验证。部署前已保存的截断正文不会被前端自动回溯修复，后续新生成轮次不再触发该覆盖问题。
