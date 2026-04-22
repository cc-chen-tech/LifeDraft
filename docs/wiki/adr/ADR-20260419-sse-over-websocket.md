# ADR-20260419-sse-over-websocket

> 最后核对：2026-04-19

## 状态

Accepted

## 背景

当前系统核心需求是“服务端向前端单向持续推送生成文本和状态事件”，典型场景包括：

- 事件生成流（`/api/games/{id}/event`）
- 选择后续写流（`/api/games/{id}/choice`）
- 改写/重生成流（`rewrite-stream` / `regenerate-stream`）

现有前端已基于 `fetch + ReadableStream` 消费 `text/event-stream`，并结合 `Last-Event-ID` 实现断线恢复。

## 决策

选择 **SSE（Server-Sent Events）作为默认流式协议**，不引入 WebSocket 作为主链路。

## 备选方案

1. WebSocket  
优点：双向通信、低延迟。  
缺点：需要额外连接状态管理、负载均衡与重连语义更复杂；当前业务主要是单向流，不占优势。

2. 纯轮询  
优点：实现简单。  
缺点：体验差、延迟高、浪费请求，难以做自然流式文本。

## 影响

- 正向影响：
  - 与当前后端路由和前端消费逻辑完全一致，改造成本低
  - 天然适配“服务端单向推送文本”场景
  - 支持 `Last-Event-ID` 断线回放
- 负向影响：
  - 不适合高频双向交互
  - 需要仔细处理代理超时与缓冲行为

## 迁移与回滚

- 迁移：无（本决策确认当前路线）。  
- 回滚：若未来出现高频双向需求，可在新域能力单独引入 WebSocket，不替换现有 SSE 主链路。

## 验证

- 断线重连场景可复现并恢复（含 `Last-Event-ID`）  
- SSE 流中 `status/story/complete/error` 事件按预期解析  
- 代理层可透传流式响应（`text/event-stream`）

## 关联

- 相关页面：`docs/wiki/03-api-and-session.md`、`docs/wiki/06-api-call-matrix.md`
- 相关模块：`frontend/src/lib/sse.ts`、`src/api/routers/gameplay/events.py`
