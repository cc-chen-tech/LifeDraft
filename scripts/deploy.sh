#!/bin/bash
# Story2 ECS 部署脚本

set -e

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
mkdir -p nginx/ssl data/images data/cache data/vector_store logs/nginx data/certbot-www

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "Warning: .env file not found!"
    echo "Please copy .env.example to .env and configure your API keys."
    exit 1
fi

# 构建镜像
echo "Building Docker images..."
docker compose -f docker-compose.ecs.yml build

# 启动服务
echo "Starting services..."
docker compose -f docker-compose.ecs.yml up -d

# 等待服务启动
echo "Waiting for services to start..."
sleep 10

# 检查服务状态
echo "Checking service status..."
docker compose -f docker-compose.ecs.yml ps

# 健康检查
echo "Performing health checks..."
if curl -f http://localhost/api/health > /dev/null 2>&1; then
    echo "Backend: OK"
else
    echo "Backend: FAILED"
fi

echo ""
echo "====================================="
echo "Deployment completed!"
echo "====================================="
echo ""
echo "Next steps:"
echo "1. Configure your domain DNS to point to this server (47.250.162.194)"
echo "2. Run: ./scripts/init-ssl.sh yourdomain.com"
echo "3. Access your application at https://yourdomain.com"
