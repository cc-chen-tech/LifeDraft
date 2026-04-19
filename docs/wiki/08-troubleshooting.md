# 08 - Troubleshooting

## 1) 前端一直转圈，事件不出来

先检查：

1. 前端是否请求了 `GET /api/games/{id}/event`（不是 `/events`）。  
2. 后端日志是否出现 `Event generation already in progress`。  
3. 是否存在旧的 `gameId`（本地存储）但服务端已无该会话。

快速处理：

- 调用 `GET /api/games/active` 验证当前活跃游戏是否存在。  
- 若会话状态异常，可调用 `POST /api/games/{id}/clear-cache`。  
- 必要时保存后重开页面，触发 `session_service` 从 DB 自动恢复。

## 2) SSE 断流或重连后内容丢失

先检查：

- 请求头是否带 `Last-Event-ID`。  
- 服务端是否在事件生成前误清理了 `sse_cache`。  
- 前端是否把 `complete` 事件当成普通 chunk 处理。

定位入口：

- 前端：`frontend/src/lib/sse.ts`  
- 后端：`src/api/routers/gameplay/events.py`、`src/api/routers/gameplay/sse_helpers.py`

## 3) 登录后仍 401（尤其 iPad / Safari）

先检查：

- `auth_token` Cookie 是否被代理层转发。  
- `COOKIE_SECURE` / `COOKIE_SAMESITE` 与实际部署域名是否匹配。  
- 前端请求是否 `credentials: 'include'`。

定位入口：

- 代理：`frontend/src/app/api/[...path]/route.ts`  
- 鉴权：`src/api/deps.py`  
- Cookie 设置：`src/api/routers/auth.py`

## 4) 场景图/角色图生成失败或返回慢

先检查：

- `IMAGE_API_KEY` / `IMAGE_API_BASE_URL` / `IMAGE_MODEL` 是否配置。  
- 是否触发内容审核（`ImageContentError`）。  
- 图片存储是否可写（本地路径或 OSS 凭证）。

定位入口：

- 路由：`src/api/routers/images.py`  
- 服务：`src/services/image_service.py`  
- 存储：`src/services/image_storage.py`

## 5) 音乐播放 403 或 URL 很快失效

这是高频现象，优先排查 URL 过期：

- 播放 URL 不是长期链接，服务端会刷新。  
- 建议走 `/api/music/stream/{song_id}` 代理播放，不直接打 CDN。

定位入口：

- 路由：`src/api/routers/music.py`  
- 服务：`src/services/music_service.py`

## 6) 升级后旧存档加载异常

先检查：

- `PlayerState` 字段变更是否兼容旧 `state_json`。  
- 是否有默认值兜底。  
- 是否补了 DB 集成测试（历史快照读取）。

最小回归集合：

- `./test.sh contract`
- `./test.sh db`
- `./test.sh e2e`
