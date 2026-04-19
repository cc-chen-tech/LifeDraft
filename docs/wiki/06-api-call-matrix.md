# 06 - API Call Matrix (Frontend -> Backend)

## 为什么要有这页

同一个仓库里同时存在：

- 页面真实在跑的调用路径（尤其 SSE）
- 历史保留/测试使用的调用方法

如果不区分，升级接口时很容易“改对了测试，改坏了线上路径”。

## 主流程真实调用（当前）

事件与选择主链路由 `frontend/src/lib/sse.ts` 驱动：

- `GET /api/games/{gameId}/event` -> 后端 `GET /api/games/{game_id}/event`
- `POST /api/games/{gameId}/choice` -> 后端 `POST /api/games/{game_id}/choice`
- `POST /api/games/{gameId}/custom-choice` -> 后端 `POST /api/games/{game_id}/custom-choice`
- `GET /api/games/{gameId}/regenerate-stream` -> 后端同名
- `POST /api/games/{gameId}/rewrite-stream` -> 后端同名

非流式回退：

- `POST /api/games/{gameId}/choice-sync`
- `POST /api/games/{gameId}/custom-choice-sync`
- `POST /api/games/{gameId}/event-sync`

## 常见模块映射

- `api.games.*` -> `/api/games/*`（创建/加载/保存/设置/结局）
- `api.character.*` -> `/api/character/*`
- `api.story.*` -> `/api/games/{id}/rewrite|regenerate|chat`
- `api.images.*` -> `/api/images/*`
- `api.collection.*` -> `/api/collection/*`
- `api.auth.*` -> `/api/auth/*`
- `api.music.*`（如果直接使用）-> `/api/music/*`

## 需要特别注意的“历史/兼容”路径

`frontend/src/lib/api.ts` 中存在以下历史风格方法（当前主要见于测试）：

- `api.gameplay.generateEvent()` 使用 `/games/{id}/events`
- `api.gameplay.submitChoice()` 使用 `/games/{id}/choices`

而后端当前主路由是单数形式：

- `/api/games/{id}/event`
- `/api/games/{id}/choice`

结论：设计新功能时优先以 `lib/sse.ts` + OpenAPI 导出结果为准，不要只看 `api.ts` 某个历史方法名。

## 接口变更安全流程（推荐）

1. 先改 FastAPI 路由与 schema。  
2. 运行 `npm run sync:api-types` 同步前端类型。  
3. 对照本页检查 SSE 主链路是否受影响。  
4. 补充/更新 `frontend/src/__tests__/lib/sse.test.ts` 与契约测试。  
5. 在 PR 描述里明确“受影响调用点清单”。
