#!/bin/bash
# Story2 ECS 部署脚本

set -euo pipefail

CANONICAL_DEPLOY_PATH="/opt/story2"
COMPOSE_PROJECT="story2"
LEGACY_COMPOSE_PROJECT="story2-main"

if [ "$(pwd -P)" != "${CANONICAL_DEPLOY_PATH}" ]; then
    echo "Error: production deployment must run from ${CANONICAL_DEPLOY_PATH}." >&2
    exit 1
fi

if [ "${GITHUB_ACTIONS:-}" != "true" ]; then
    echo "Error: production deployment is owned by GitHub Actions; merge a PR instead." >&2
    exit 1
fi

if docker ps --filter "label=com.docker.compose.project=${LEGACY_COMPOSE_PROJECT}" --quiet | grep -q .; then
    echo "Error: legacy Compose project ${LEGACY_COMPOSE_PROJECT} is still running." >&2
    echo "Stop the legacy deployment through the approved operations process before deploying." >&2
    exit 1
fi

echo "====================================="
echo "Story2 ECS Deployment Script"
echo "====================================="

# 检查是否在正确的目录
if [ ! -f "docker-compose.ecs.yml" ]; then
    echo "Error: docker-compose.ecs.yml not found!"
    echo "Please run this script from the project root directory."
    exit 1
fi

# 创建必要目录
echo "Creating necessary directories..."
mkdir -p nginx/ssl data/images data/cache logs/nginx data/certbot-www

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "Warning: .env file not found!"
    echo "Please copy .env.example to .env and configure your API keys."
    exit 1
fi

# 构建镜像
echo "Building Docker images..."
docker compose -p "${COMPOSE_PROJECT}" -f docker-compose.ecs.yml build

# 启动服务
echo "Starting services..."
docker compose -p "${COMPOSE_PROJECT}" -f docker-compose.ecs.yml up -d

# 等待 backend 容器健康
echo "Waiting for backend container health..."
backend_healthy=false
for attempt in $(seq 1 36); do
    backend_container_id="$(docker compose -p "${COMPOSE_PROJECT}" -f docker-compose.ecs.yml ps -q backend)"
    backend_status=""
    if [ -n "${backend_container_id}" ]; then
        backend_status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${backend_container_id}" 2>/dev/null || true)"
    fi
    if [ "${backend_status}" = "healthy" ]; then
        echo "Backend container is healthy."
        backend_healthy=true
        break
    fi
    echo "Waiting for backend health (${attempt}/36): ${backend_status:-unknown}"
    sleep 5
done

if [ "${backend_healthy}" != "true" ]; then
    docker compose -p "${COMPOSE_PROJECT}" -f docker-compose.ecs.yml logs --tail=120 backend
    echo "Backend container did not become healthy in time." >&2
    exit 1
fi

# 检查服务状态
echo "Checking service status..."
docker compose -p "${COMPOSE_PROJECT}" -f docker-compose.ecs.yml ps

# 检查本机 API，公开地址由 GitHub Actions 的后续 Smoke test 验证
echo "Performing local API health check..."
curl -fsS http://localhost/api/health > /dev/null
echo "Backend API: OK"

echo ""
echo "====================================="
echo "Deployment completed!"
echo "====================================="
echo ""
echo "Next steps:"
echo "1. Configure your domain DNS to point to this server (47.250.162.194)"
echo "2. Run: ./scripts/init-ssl.sh yourdomain.com"
echo "3. Access your application at https://yourdomain.com"
