FROM node:18-alpine

WORKDIR /app

# 安装 git 并克隆代码
RUN apk add --no-cache git && \
    git clone --depth 1 https://github.com/Binaryify/NeteaseCloudMusicApi.git /tmp/netease && \
    cp -r /tmp/netease/* /app/ && \
    cp -r /tmp/netease/.[!.]* /app/ 2>/dev/null || true && \
    rm -rf /tmp/netease && \
    npm install && \
    apk del git

ENV PORT=3001

EXPOSE 3001

CMD ["node", "app.js"]
