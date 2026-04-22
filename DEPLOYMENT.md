# 生产部署指南（当前代码版本）

> 最后更新：2026-04-19  
> 说明：本文件以当前仓库实现为准（FastAPI + Next.js + 可选 music-api）。

## 架构概览

- `backend`：FastAPI（端口 8000）
- `frontend`：Next.js（端口 3000）
- `music-api`：网易云 API（端口 3001，可选但推荐）
- `nginx`：反向代理 + TLS（80/443）

当前仓库提供的 Compose 文件为：

- `docker-compose.ecs.yml`

## 1. 部署前准备

### 1.1 基础环境

- Docker Engine 24+
- Docker Compose v2（`docker compose`）
- Linux 服务器（建议 2C4G 起步）

### 1.2 环境变量

```bash
cp .env.example .env
```

至少确认这些变量：

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `DATABASE_URL`（可选，不填使用本地 SQLite）
- `COOKIE_SECURE=true`（生产环境建议）
- `COOKIE_SAMESITE=lax`（按域名策略调整）

如使用图像与 OSS，补齐 `IMAGE_*` 与 `OSS_*` 配置。

## 2. 使用 Docker Compose（推荐）

### 2.1 启动

```bash
docker compose -f docker-compose.ecs.yml up -d --build
```

### 2.2 查看状态与日志

```bash
docker compose -f docker-compose.ecs.yml ps
docker compose -f docker-compose.ecs.yml logs -f backend
docker compose -f docker-compose.ecs.yml logs -f frontend
docker compose -f docker-compose.ecs.yml logs -f nginx
```

### 2.3 停止

```bash
docker compose -f docker-compose.ecs.yml down
```

## 3. 健康检查

- 后端健康检查：`GET /api/health`
- 前端首页：`/`
- 音乐服务：`music-api` 容器健康状态

示例：

```bash
curl http://127.0.0.1:8000/api/health
```

## 4. HTTPS 与 Nginx

`docker-compose.ecs.yml` 默认挂载：

- `nginx/ecs-nginx.conf`
- `nginx/ssl/`

请将证书放入 `nginx/ssl/` 并按配置文件约定命名。  
若使用 ACME/Certbot，建议将证书续期脚本和 reload 流程加入 crontab 或 CI/CD。

## 5. 升级流程（无停机最小化）

1. 拉取代码
2. 更新 `.env`（如有新增变量）
3. 重新构建并滚动重启

```bash
git pull
docker compose -f docker-compose.ecs.yml up -d --build
```

4. 验证：

- `/api/health` 返回 `ok`
- 前端可正常加载
- 关键玩法链路（事件生成 + 选择 + 保存）可用

## 6. 回滚流程

1. 切回上一版本代码（tag/commit）
2. 重启同一套 compose

```bash
git checkout <previous_tag_or_commit>
docker compose -f docker-compose.ecs.yml up -d --build
```

## 7. 常见问题

### 7.1 前端 401 或登录态丢失

- 检查 Nginx 是否透传 Cookie
- 检查 `COOKIE_SECURE`/`COOKIE_SAMESITE` 与协议/域名是否匹配
- 检查前端是否走同域代理路径 `/api/*`

### 7.2 SSE 长连接经常断开

- 检查 Nginx 对 `text/event-stream` 的超时与缓冲设置
- 确认代理没有提前切断长连接

### 7.3 音乐播放 403

- 这是 CDN URL 过期常见现象，优先走后端代理流接口
- 检查 `music-api` 容器与网络连通性

## 8. 文档入口

- 项目总览：`README.md`
- 详细 wiki：`docs/wiki/README.md`
- 发布检查清单：`docs/wiki/10-release-and-change-checklist.md`
