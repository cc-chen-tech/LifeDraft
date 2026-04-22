# 02 - System Architecture

> 最后核对：2026-04-19

## 分层结构

- `frontend/`：Next.js 前端 UI、状态管理（Zustand）、SSE 消费
- `src/api/`：FastAPI 路由层、会话恢复、鉴权、SSE 输出
- `src/game/`：游戏回合推进、状态机、叙事/世界模型编排
- `src/ai/`：LLM 客户端、故事生成、选项生成、约束校验、叙事增强
- `src/services/`：图片、音乐、实体识别等领域服务
- `src/database/`：SQLAlchemy 模型 + Repository + Facade
- `config/`：运行时配置、Prompt、Feature Flags

## 主请求链路（核心）

1. 前端页面（`frontend/src/app/play/page.tsx`）通过 `usePlayGame` 驱动回合流程。  
2. 前端请求统一走 `frontend/src/app/api/[...path]/route.ts` 代理，转发 Cookie 到后端。  
3. 后端 `src/api/main.py` 注册各路由（`/api/games`、`/api/images`、`/api/music` 等）。  
4. 路由通过 `session_service.get_or_restore()` 获取内存会话；缺失时从 DB 自动恢复 `GameLoop`。  
5. `GameLoop` 调用 `RoundEventGenerator` + `EventGenerator/StoryGenerator` 生成故事与选项。  
6. 结果写入 `PlayerState`，必要时持久化到 `GameState`（JSON 快照）和其他表。  
7. 前端通过 SSE 增量渲染故事文本与状态。

## 关键对象

- `GameLoop`：游戏核心协调器，维护 `player_state` / `current_event` / 回合推进。  
- `GameLoopSession`：内存会话包装器，包含 SSE 缓存和 options cache。  
- `PlayerState`：游戏真实状态（资源、剧情历史、角色/物品/地标等）。  
- `GameState`：数据库中的状态快照（支持普通进度 + 手动存档点）。

## 并发与恢复策略

- 路由层使用 `asyncio.Lock` 避免同一游戏并发生成事件。  
- 会话层有 `_generating` 和超时重置，避免生成“卡死”。  
- SSE 支持 `Last-Event-ID` 断线重连，结合服务端 chunk 缓存回放。  
- `SessionService` 支持内存过期后 DB 恢复，并在恢复后补齐缺失插画。

## Feature Flag 体系

开关在 `config/feature_flags.py` 统一定义，默认关闭。典型开关：

- `constraint_harness`
- `narrative_style_engine`
- `creative_enhancement`
- `epic_narrative`
- `vector_search`
- `model_fallback`
- `parallel_postprocessing`

设计新能力时，优先通过 flag 做灰度，不直接全量放开。
