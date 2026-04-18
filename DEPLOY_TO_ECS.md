# Story2 ECS 部署执行指南

## 步骤 1：连接到服务器

通过阿里云控制台 Workbench 或本地终端连接：
```bash
ssh root@47.250.162.194
```

## 步骤 2：安装 Docker（复制以下全部命令执行）

```bash
yum update -y
yum install -y yum-utils
yum-config-manager --add-repo https://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo
yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
systemctl enable --now docker
docker --version
docker compose version
```

## 步骤 3：配置环境变量

```bash
cd /opt/story2
cp .env.ecs.example .env
```

编辑 `.env` 文件，填入你的 API 密钥：
```bash
vim .env
```

需要修改的字段：
- `OPENAI_API_KEY` - 你的 DeepSeek API 密钥
- `IMAGE_API_KEY` - 你的阿里云 DashScope API 密钥
- `CORS_ORIGINS` - 改为你的域名，如 `https://yourdomain.com`

保存退出：按 `Esc`，输入 `:wq`，回车

## 步骤 4：执行部署

```bash
./scripts/deploy.sh
```

等待构建完成，看到 "Deployment completed!" 即表示成功。

## 步骤 5：验证部署

```bash
# 查看服务状态
docker compose -f docker-compose.ecs.yml ps

# 测试 API
curl http://localhost/api/health
```

## 步骤 6：配置域名（可选）

1. 在阿里云购买域名
2. 添加 A 记录指向 `47.250.162.194`
3. 申请 SSL 证书：
```bash
./scripts/init-ssl.sh yourdomain.com
```

## 访问应用

- 临时访问：http://47.250.162.194
- 域名访问：https://yourdomain.com（配置域名后）

## 常用命令

```bash
# 查看日志
docker compose -f docker-compose.ecs.yml logs -f

# 重启服务
docker compose -f docker-compose.ecs.yml restart

# 停止服务
docker compose -f docker-compose.ecs.yml down

# 备份数据
./scripts/backup.sh
```
