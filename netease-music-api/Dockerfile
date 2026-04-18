FROM node:18-alpine

# 先安装 git，然后克隆到 /app
RUN apk add --no-cache git && \
    git clone --depth 1 https://github.com/Binaryify/NeteaseCloudMusicApi.git /app

WORKDIR /app

# 安装依赖
RUN npm install && \
    apk del git

ENV PORT=3001

EXPOSE 3001

CMD ["node", "app.js"]
