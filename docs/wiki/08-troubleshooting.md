# 08 - Troubleshooting

> 最后核对：2026-09-28

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

## 5) 故事朗读生成失败或不可播放

先检查 MiniMax TTS 配置和章节任务状态：

- `MINIMAX_API_KEY` 是否配置且凭据有效。
- `GET /api/voice-reading/jobs/{job_id}` 的章节或段落是否为 `failed`。
- 音频 URL 是否仍通过同域 `/api/voice-reading/audio/*` 访问。

定位入口：

- 路由：`src/api/routers/voice_reading.py`
- 服务：`src/services/story_voice_reading.py`

## 6) SSE 场景图事件 401

自安全加固后，`/api/games/{id}/scene-events` 要求认证：

- 检查 `auth_token` Cookie 是否有效且未过期。  
- 检查前端请求是否携带 `credentials: 'include'`。
- 检查 Nginx 代理是否正确透传 Cookie 头。

## 7) JWT 签名失败或登录态异常

- 确认 `.env` 中 `JWT_SECRET_KEY` 已设置且不是默认值。
- 生产环境必须配置独立的密钥，已移除硬编码 fallback。
- 密钥变更后所有已签发 token 失效，用户需重新登录。

## 8) SSE 502/504 网关错误与断流

前端 SSE 连接遇到 502/504 时自动重试（指数退避，最多 3 次）：

- 检查 Nginx 网关超时设置（`proxy_read_timeout`、`proxy_connect_timeout`）。
- 检查后端服务是否健康（`/api/health`）。
- 检查 ECS 服务器资源是否耗尽（CPU/内存）。

定位入口：
- 前端：`frontend/src/lib/sse.ts`（`fetchSSEWithRetry`）
- Nginx：`nginx/ecs-nginx.conf`

## 9) 升级后旧存档加载异常

先检查：

- `PlayerState` 字段变更是否兼容旧 `state_json`。  
- 是否有默认值兜底。  
- 是否补了 DB 集成测试（历史快照读取）。

最小回归集合：

- `./test.sh contract`
- `./test.sh db`
- `./test.sh e2e`

## 10) Model Smoke 红色，但六项功能检查通过

查看 `smoke-summary.json` 的 `errors`、首日 `delivery_mode` 与工作流失败步骤。
若只有 `daily_opening_used_safe_fallback`，说明首日安全开场已交付、保存并可玩，
但模型正文没有通过质量验收，自动发布会停止；它不表示图片、TTS 或数据库都失败。
检查 [生成诊断手册](../generation-diagnostics-runbook.md) 中的初稿、修订稿与一致性记录，
确认拒稿原因。需要提前发布时遵循 [生产部署指南](../../DEPLOYMENT.md) 的例外流程。
