FROM node:18-alpine

WORKDIR /app

# 复制 package.json 并安装依赖
COPY package*.json ./
RUN npm install

# 复制应用代码
COPY . .

ENV PORT=3001

EXPOSE 3001

CMD ["node", "app.js"]
