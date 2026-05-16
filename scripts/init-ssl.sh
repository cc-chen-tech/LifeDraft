#!/bin/bash
# SSL 证书初始化脚本

DOMAIN=$1

if [ -z "$DOMAIN" ]; then
    echo "Usage: $0 <domain>"
    echo "Example: $0 story2.example.com"
    exit 1
fi

echo "Initializing SSL certificate for $DOMAIN..."

# 创建证书目录
mkdir -p nginx/ssl
mkdir -p data/certbot-www

# 使用 Certbot Docker 申请证书
docker run -it --rm \
    -v "$(pwd)/nginx/ssl:/etc/letsencrypt" \
    -v "$(pwd)/data/certbot-www:/var/www/certbot" \
    -p 80:80 \
    certbot/certbot certonly \
    --standalone \
    --preferred-challenges http \
    -d "$DOMAIN" \
    --agree-tos \
    --non-interactive \
    --email your-email@example.com

# 创建符号链接供 Nginx 使用
ln -sf /etc/letsencrypt/live/$DOMAIN/fullchain.pem nginx/ssl/fullchain.pem
ln -sf /etc/letsencrypt/live/$DOMAIN/privkey.pem nginx/ssl/privkey.pem

echo "SSL certificate initialized successfully!"
echo "Please restart nginx container to apply the certificate:"
echo "  docker compose -f docker-compose.ecs.yml restart nginx"
