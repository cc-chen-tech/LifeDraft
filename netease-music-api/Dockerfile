FROM node:18-alpine

WORKDIR /app

# 安装 pnpm
RUN npm install -g pnpm

# 复制所有文件
COPY . .

# 安装依赖（忽略 prepare 脚本）
RUN pnpm install --ignore-scripts

ENV PORT=3001

EXPOSE 3001

CMD ["node", "app.js"]
