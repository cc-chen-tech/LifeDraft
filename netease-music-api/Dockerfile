FROM node:18-alpine

WORKDIR /app

# 安装 git 并克隆网易云音乐 API 仓库
RUN apk add --no-cache git && \
    git clone --depth 1 https://github.com/Binaryify/NeteaseCloudMusicApi.git /tmp/netease && \
    cp -r /tmp/netease/* /app/ && \
    rm -rf /tmp/netease && \
    npm install && \
    apk del git

ENV PORT=3001

EXPOSE 3001

CMD ["node", "app.js"]
