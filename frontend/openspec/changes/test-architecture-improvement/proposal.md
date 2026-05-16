# Proposal: Test Architecture Improvement

## Summary

系统性提升前端测试架构的三个维度：消除 SSE mock 盲区、补齐测试金字塔缺口、清理 replaceMethods 样板代码。

## Motivation

上一轮工作消除了 20 个文件中的 `jest.mock('@/lib/api')`，将 API 层的 mock 降到了 `global.fetch` 级别。但测试架构仍有三个结构性问题：

### Problem 1: SSE mock 盲区（9 files）

`@/lib/sse.ts` 仍被 `jest.mock` 完全替换。真实 SSE 代码（流解析、重连、错误处理）在单元测试中从未运行。原因是 Jest/jsdom 环境不支持 `ReadableStream` + `getReader()`。

```
当前：jest.mock('@/lib/sse') → 所有 SSE 函数都是假的
目标：global.fetch mock + ReadableStream polyfill → parseSSEStream 真实运行
```

### Problem 2: 测试金字塔缺口

前端 805 个测试 mock 的数据格式（`player_state`、`game_id` 等字段名）与后端实际返回之间没有自动化验证。后端 Python 合同测试和前端 Jest mock 数据各自独立，存在"格式不同步"的风险。

```
当前：后端合同测试 ←→ 间隙 ←→ 前端 mock 数据
目标：后端合同测试作为前端 mock 数据的"格式来源"
```

### Problem 3: replaceMethods 样板代码（25 files）

25 个测试文件各自手写 `replaceMethods`/`restoreMethods`/`getMethod` 样板函数，总计约 375 行重复代码。方法名用字符串硬编码，没有类型安全保障。

```
当前：每个文件手写 15 行样板 + 字符串方法名
目标：一个共享工具函数 + 类型安全的方法 spy
```

## Scope

| Workstream | Files Touched | Effort |
|------------|--------------|--------|
| SSE mock utility | 1 new + 9 test files | Medium |
| Contract test alignment | ~5 Python test files | Small |
| replaceMethods refactor | 1 new helper + 25 test files | Medium |

## Non-goals

- 不迁移测试框架（Vitest 迁移延后到下一阶段）
- 不改动 E2E 测试（32 个 Playwright spec 保持不变）
- 不改变测试覆盖率阈值

## Success Criteria

1. `jest.mock('@/lib/sse')` 从 9 个文件中移除，替换为 `createSSEMock` 工具
2. 后端至少 5 个关键 API 端点有响应格式合同测试
3. `replaceMethods`/`restoreMethods` 样板从 25 个文件中移除，替换为统一工具
4. 全部 805 个测试保持通过
