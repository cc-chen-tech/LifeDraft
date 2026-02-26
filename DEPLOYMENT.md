# 生产部署指南

本指南将帮助你将"人生草稿本"项目部署到生产环境。我们提供了三种部署方案，从简单到复杂，你可以根据自己的需求选择。

## 📋 目录

1. [方案一：Streamlit Cloud（最简单）](#方案一streamlit-cloud最简单)
2. [方案二：Docker部署（推荐）](#方案二docker部署推荐)
3. [方案三：完整生产环境（高级）](#方案三完整生产环境高级)
4. [常见问题](#常见问题)

---

## 方案一：Streamlit Cloud（最简单）

**适合场景**：快速上线、个人项目、小规模使用

**优点**：
- ✅ 完全免费（个人使用）
- ✅ 零配置，5分钟上线
- ✅ 自动HTTPS
- ✅ 自动更新（Git推送即部署）

**缺点**：
- ❌ 有资源限制
- ❌ 不支持自定义域名（免费版）
- ❌ 数据库需要外部服务

### 步骤：

1. **准备代码**
   ```bash
   # 确保代码已推送到GitHub
   git add .
   git commit -m "准备部署"
   git push origin main
   ```

2. **部署到Streamlit Cloud**
   - 访问 https://share.streamlit.io/
   - 使用GitHub账号登录
   - 点击"New app"
   - 选择你的仓库和分支
   - 设置主文件路径：`src/ui/streamlit_app.py`
   - 点击"Deploy"

3. **配置环境变量**
   - 在Streamlit Cloud界面，点击"Settings" → "Secrets"
   - 添加以下配置：
   ```toml
   [secrets]
   OPENAI_API_KEY = "your-api-key-here"
   OPENAI_MODEL = "gpt-4"
   DATABASE_URL = "postgresql://user:pass@host:5432/dbname"  # 可选，使用云数据库
   DEFAULT_LANGUAGE = "zh"
   CACHE_EVENTS = "true"
   ```

4. **完成！**
   - 应用会自动部署
   - 访问提供的URL即可使用

---

## 方案二：Docker部署（推荐）

**适合场景**：VPS服务器、云服务器、需要更多控制

**优点**：
- ✅ 环境一致性好
- ✅ 易于迁移和扩展
- ✅ 支持自定义配置
- ✅ 可以部署到任何支持Docker的平台

**缺点**：
- ⚠️ 需要学习Docker基础
- ⚠️ 需要服务器资源

### 前置要求：

- 安装Docker和Docker Compose
  ```bash
  # Ubuntu/Debian
  curl -fsSL https://get.docker.com -o get-docker.sh
  sh get-docker.sh
  
  # 安装Docker Compose
  sudo apt-get install docker-compose-plugin
  ```

### 步骤：

1. **准备环境变量文件**
   ```bash
   # 复制.env.example（如果存在）或创建新文件
   cp .env.example .env
   
   # 编辑.env文件，填入你的配置
   nano .env
   ```
   
   `.env`文件内容示例：
   ```bash
   OPENAI_API_KEY=sk-your-key-here
   OPENAI_MODEL=gpt-4
   OPENAI_BASE_URL=
   DATABASE_URL=postgresql://user:pass@host:5432/dbname  # 可选
   DEFAULT_LANGUAGE=zh
   CACHE_EVENTS=true
   ```

2. **构建和启动**
   ```bash
   # 构建Docker镜像
   docker-compose build
   
   # 启动服务（后台运行）
   docker-compose up -d
   
   # 查看日志
   docker-compose logs -f app
   ```

3. **访问应用**
   - 打开浏览器访问：`http://your-server-ip:8501`

4. **常用命令**
   ```bash
   # 停止服务
   docker-compose down
   
   # 重启服务
   docker-compose restart
   
   # 查看运行状态
   docker-compose ps
   
   # 更新代码后重新部署
   git pull
   docker-compose build
   docker-compose up -d
   ```

### 部署到云平台：

#### 阿里云/腾讯云/华为云
1. 购买ECS服务器（建议2核4G以上）
2. 安装Docker和Docker Compose
3. 按照上述步骤部署

#### Railway / Render / Fly.io
这些平台支持直接部署Docker：
1. 连接GitHub仓库
2. 选择Dockerfile
3. 配置环境变量
4. 自动部署

---

## 方案三：完整生产环境（高级）

**适合场景**：正式生产环境、需要高可用、需要监控

**特点**：
- ✅ Nginx反向代理
- ✅ HTTPS/SSL支持
- ✅ 日志管理
- ✅ 健康检查
- ✅ 资源限制

### 步骤：

1. **使用生产配置**
   ```bash
   # 使用生产环境配置
   docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
   ```

2. **配置Nginx和SSL**
   
   **选项A：使用Let's Encrypt（免费SSL）**
   ```bash
   # 安装certbot
   sudo apt-get install certbot python3-certbot-nginx
   
   # 获取SSL证书
   sudo certbot --nginx -d your-domain.com
   ```
   
   **选项B：手动配置SSL**
   - 将SSL证书放到 `nginx/ssl/` 目录
   - 取消注释 `nginx.conf` 中的HTTPS配置
   - 修改域名

3. **配置域名DNS**
   - A记录指向服务器IP
   - 等待DNS生效（通常几分钟到几小时）

4. **访问应用**
   - HTTP: `http://your-domain.com`
   - HTTPS: `https://your-domain.com`

### 监控和维护：

1. **查看日志**
   ```bash
   # 应用日志
   docker-compose logs -f app
   
   # Nginx日志
   docker-compose logs -f nginx
   
   # 系统日志（在容器内）
   docker exec story2-app tail -f /app/logs/app.log
   ```

2. **健康检查**
   ```bash
   # 检查应用健康状态
   curl http://localhost:8501/_stcore/health
   
   # 检查Nginx
   curl http://localhost/health
   ```

3. **备份数据**
   ```bash
   # 备份数据库（如果使用PostgreSQL）
   docker exec story2-db pg_dump -U story2 story2 > backup.sql
   
   # 备份数据目录
   tar -czf data-backup.tar.gz data/
   ```

---

## 常见问题

### Q1: 如何更新应用？

```bash
# 拉取最新代码
git pull

# 重新构建镜像
docker-compose build

# 重启服务
docker-compose up -d
```

### Q2: 如何查看应用日志？

```bash
# 实时查看日志
docker-compose logs -f app

# 查看最近100行
docker-compose logs --tail=100 app
```

### Q3: 如何配置数据库？

**使用SQLite（默认，简单）**：
- 不需要额外配置，数据保存在 `data/game.db`

**使用PostgreSQL（推荐生产环境）**：
1. 在 `docker-compose.yml` 中取消注释PostgreSQL服务
2. 设置 `DATABASE_URL` 环境变量
3. 重启服务

### Q4: 如何设置HTTPS？

**最简单方法**：使用Let's Encrypt
```bash
sudo certbot --nginx -d your-domain.com
```

### Q5: 如何限制资源使用？

在 `docker-compose.yml` 中已经配置了资源限制，可以根据需要调整：
```yaml
deploy:
  resources:
    limits:
      cpus: '2'      # 最大CPU核心数
      memory: 2G     # 最大内存
```

### Q6: 如何备份和恢复？

**备份**：
```bash
# 备份数据目录
tar -czf backup-$(date +%Y%m%d).tar.gz data/

# 备份数据库（PostgreSQL）
docker exec story2-db pg_dump -U story2 story2 > backup.sql
```

**恢复**：
```bash
# 恢复数据目录
tar -xzf backup-20240101.tar.gz

# 恢复数据库
docker exec -i story2-db psql -U story2 story2 < backup.sql
```

### Q7: 性能优化建议

1. **使用PostgreSQL替代SQLite**（生产环境）
2. **启用缓存**（`CACHE_EVENTS=true`）
3. **使用CDN**（静态资源）
4. **配置Nginx缓存**（可选）
5. **使用Redis缓存**（高级，可选）

---

## 安全建议

1. ✅ **永远不要**将 `.env` 文件提交到Git
2. ✅ 使用强密码和API密钥
3. ✅ 定期更新依赖：`pip install --upgrade -r requirements.txt`
4. ✅ 使用HTTPS（生产环境）
5. ✅ 限制服务器访问（防火墙规则）
6. ✅ 定期备份数据
7. ✅ 监控日志，及时发现异常

---

## 下一步

部署成功后，你可以：

1. **监控应用**：设置日志监控和告警
2. **优化性能**：根据使用情况调整资源配置
3. **扩展功能**：添加更多游戏特性
4. **用户反馈**：收集用户反馈，持续改进

---

## 需要帮助？

如果遇到问题：
1. 查看日志：`docker-compose logs -f`
2. 检查环境变量配置
3. 确认端口没有被占用
4. 查看本文档的常见问题部分

祝你部署顺利！🎉
