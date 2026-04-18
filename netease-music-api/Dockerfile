FROM node:18-alpine

WORKDIR /app

# 复制所有文件并安装依赖
COPY . .
RUN npm install

ENV PORT=3001

EXPOSE 3001

CMD ["node", "app.js"]
