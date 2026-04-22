# 03 - API And Session

> 最后核对：2026-04-19

## 路由总览（按域）

认证与用户：

- `/api/auth/*`：注册、登录、当前用户、登出
- `/api/friends/*`：好友请求、好友列表

游戏生命周期：

- `/api/games`：创建、列表、加载、保存、删除
- `/api/games/active`：服务端“活跃游戏”恢复
- `/api/games/{id}/save-point`、`/timeline`：时间回溯存档

玩法回合：

- `/api/games/{id}/event`（SSE）/`event-sync`
- `/api/games/{id}/choice`（SSE）/`choice-sync`
- `/api/games/{id}/summary`、`/ending`

剧情改写：

- `/api/games/{id}/rewrite`、`/rewrite-stream`
- `/api/games/{id}/regenerate`、`/regenerate-stream`
- `/api/games/{id}/chat`

资产与扩展：

- `/api/images/*`：角色/物品/场景图生成、历史图、SSE 场景图事件
- `/api/collection/*`：角色/物品/地标收集与补图
- `/api/music/*`：剧情音乐推荐、歌曲搜索、音频流代理
- `/api/presets/*`：角色预设保存/加载

## Session 设计（必须理解）

内存层：

- `session_store` 以 `user_{user_id}_game_{game_id}` 作为 key。  
- 默认 4 小时过期（`SESSION_TIMEOUT`）。  
- 每个会话带 `sse_cache`（断线回放）和 `options_cache`（快速恢复）。

恢复层：

- 路由统一调用 `session_service.get_or_restore()`。
- 内存缺失时，从 DB `load_saved_game` 恢复 `GameLoop`。
- 恢复后异步检查并补齐缺失场景插画/角色图，不阻塞主请求。

## SSE 约定

- 事件生成与选项提交均支持 SSE。  
- 客户端断线后应携带 `Last-Event-ID`，服务端可重放缓存 chunk。  
- 同一游戏并发生成受锁保护；重复请求优先返回已有 event，避免重复生成。

## 前后端 API 契约同步

前端类型生成链路：

```bash
cd frontend
npm run sync:api-types
```

底层实际执行：

1. `python3 scripts/export_openapi.py` 生成 `frontend/src/types/openapi-schema.json`
2. `openapi-typescript` 生成 `frontend/src/types/api-generated.d.ts`

新增/修改后端接口后，建议在同一个 PR 内同步更新类型并补契约测试。

补充阅读：

- [06-API Call Matrix](./06-api-call-matrix.md)：前端真实调用路径与历史兼容路径对照。
