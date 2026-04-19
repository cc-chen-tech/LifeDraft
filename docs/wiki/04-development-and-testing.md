# 04 - Development And Testing

## 日常开发命令

后端：

```bash
source venv/bin/activate
python run_api.py
pytest tests/ -v
```

前端：

```bash
cd frontend
npm run dev
npm test
npm run test:e2e
```

脚本入口：

- `./start.sh`：一键启停前后端 + 音乐服务
- `./test.sh`：五层测试架构统一入口

## 五层测试架构（`test.sh`）

1. `mypy`：静态类型检查  
2. `imports`：延迟导入路径可达  
3. `contract`：API/模型契约一致性  
4. `db`：真实 DB 集成链路  
5. `e2e`：Playwright 浏览器端到端

常用：

```bash
./test.sh all
./test.sh contract
./test.sh db
./test.sh frontend
```

## 代码质量与规范

- Python：`black`、`isort`、`flake8`、`mypy`
- Frontend：`eslint`、TypeScript strict、Jest/Playwright
- 安全：`./test.sh security`（Bandit）
- 性能：`./test.sh perf`（Locust）

## 数据与配置注意点

- 默认 DB：`data/game.db`（SQLite）  
- 可切换云 DB：设置 `DATABASE_URL`  
- 实验能力通过 `.env` 中 feature flags 控制，不要硬编码启用  
- 新增环境变量时，必须同步更新 `.env.example` 与对应文档
