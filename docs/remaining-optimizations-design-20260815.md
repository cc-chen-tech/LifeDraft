# 剩余优化设计文档（前端渲染 + to_dict 瘦身）

> 创建日期：2026-08-15
> 状态：设计评审中（对应审查报告剩余 2 项大工程，未提交 PR）

## 背景

整体审查的 22 项修复已全部交付（PR #280~#300，含合并顺序模拟验证）。
剩余 2 项属于**深度重构**，风险显著高于此前所有修复，故先固化设计、评审后再实施。

## 1. 前端渲染：组合 store 全量订阅

### 现状（同步后代码）

- `usePlayGame` 无 selector 订阅整个 `useGameStore`（`frontend/src/hooks/usePlayGame.ts`）；
- `useGameStore` 把 5 个子 store 的全部字段复制一份（`_syncFromSubStores`，`useGameStore.ts:204`），
  任一子 store 任意变化（含 `isLoadingRoundSceneImage` 轮询翻转）都触发全量 `set` → 所有无 selector 消费者重渲染；
- `StreamingText` 已是打字机渲染（30ms/帧、+2 字符），markdown 全量重解析问题已被上游大幅缓解——
  原审查中的 O(n²) 解析结论不再成立，剩余成本主要是**每 chunk 的父级重渲染**（约 100+ 次/轮）。

### 目标

每个 SSE chunk 只重渲染"故事文本"相关的组件子树，而不是整个 PlayPage。

### 方案（分 3 步，每步独立可测）

**Step 1：PlayPage 改 selector 订阅（低风险）**
- `usePlayGame` 内部按需拆订阅：`useGameStore(s => s.storyText)`、`useGameStore(s => s.options)` 等；
- 保持返回对象形状不变（`usePlayGameReturn` 已有 grouped API），组件层零改动；
- 验证：`frontend/src/__tests__/hooks/usePlayGame*.test.ts` 全绿 + 渲染计数测试（jest 断言 chunk 时 PlayPage 渲染次数下降）。

**Step 2：删除组合 store 冗余态（中风险）**
- 删除 `useGameStore` 里与子 store 重复的字段与 `_syncFromSubStores`/`subscribe` 链；
- `usePlayGame` 直接从 5 个子 store 取数；`useGameStore` 只保留编排 action；
- 存量测试中经 `useGameStore` 读写这些字段的调用点，逐处改为对应子 store（预估 30-50 处）。

**Step 3：StreamingText 增量渲染（低风险，可选）**
- 打字机 + `React.memo` + 文本缓存（当前每 30ms 仍会重解析整段 markdown，长故事后期为 O(n) 解析/帧）；
- 可改为"按段落 memo 渲染"：仅最后一个未闭合段落重解析。

### 风险与回滚

- 每步独立提交；Step 2 若测试面过大，可保留 `_syncFromSubStores` 但改为浅比较后仅更新变化字段的过渡方案。

## 2. `to_dict()` 序列化瘦身

### 现状

`PlayerState.to_dict()` = `model_dump()` 全量序列化（含 `story_history`/`round_history`/
`decision_history`/`world_model_data`/`continuity_ledger` 等无界增长结构），全库 17 处调用：
生成 prompt、持久化快照、HTTP 响应各用各的。

### 方案

1. **新增 `to_prompt_context()`**：只为 AI 生成 prompt 提供字段投影——
   近期 N 轮故事（如最近 3 轮）+ 世界模型约束 + 必要设定，排除完整历史；
   替换生成链路中的 `to_dict()`（`event_generator`/`choice_processor`/`story_service` 等处，约 8 处）。
2. **持久化与响应保持 `to_dict()`**（快照/存档/前端状态需要完整数据；PR #283 的 prune 已控制存量膨胀）。
3. **校验侧避免二次重建**：`consistency_validator`/`story_service` 里 `from_dict` + `WorldModel.from_player_state`
   改为直接复用已构建的 `world_model`（与 #290 的合并调用同批优化）。

### 风险

- 叙事质量依赖 prompt 中的历史上下文——投影范围需对比生成效果（建议先做 A/B：近期 3 轮 vs 6 轮）；
- 契约测试若断言 prompt 含完整历史，需同步更新（估计 3-5 个测试文件）。

## 实施建议

| 项 | 建议时机 | 前置条件 |
|---|---|---|
| Step 1 | 第一批合并后即可 | 无 |
| `to_prompt_context` | 与 Step 1 并行 | 生成效果 A/B |
| Step 2 / Step 3 | Step 1 稳定一周后 | e2e 全绿 |

## 验收标准

- 流式期间 PlayPage 每 chunk 渲染次数从 ~100 降至 ~10 以内（用 React DevTools/jest 计数验证）；
- 生成 prompt 大小下降 ≥ 50%（日志对比），生成质量契约测试全绿。
