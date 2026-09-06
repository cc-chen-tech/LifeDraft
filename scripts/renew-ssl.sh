#!/bin/bash
# SSL 证书自动续期脚本

set -euo pipefail

CANONICAL_DEPLOY_PATH="/opt/story2"
COMPOSE_PROJECT="story2"

if [ "$(pwd -P)" != "${CANONICAL_DEPLOY_PATH}" ]; then
    echo "Error: production SSL operations must run from ${CANONICAL_DEPLOY_PATH}." >&2
    exit 1
fi

echo "Renewing SSL certificates..."

# 使用 Certbot Docker 续期证书
docker run --rm \
    -v "$(pwd)/nginx/ssl:/etc/letsencrypt" \
    -v "$(pwd)/data/certbot-www:/var/www/certbot" \
    -p 80:80 \
    certbot/certbot renew \
    --quiet \
    --no-random-sleep-on-renew

# 检查证书是否更新，如果是则重载 Nginx
if [ $? -eq 0 ]; then
    echo "Certificate renewed successfully. Reloading nginx..."
    docker compose -p "${COMPOSE_PROJECT}" -f docker-compose.ecs.yml exec nginx nginx -s reload
else
    echo "Certificate renewal failed or not needed."
fi
