# 04 - Development And Testing

> 最后核对：2026-04-26

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
- `./scripts/test-run-isolated.sh`：测试隔离运行入口（测试产物默认写入 `/tmp/story2-test-runs`，避免污染仓库）

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

环境噪音治理（推荐）：

```bash
./scripts/test-run-isolated.sh all                 # 使用独立 TEST_RUN_ROOT 运行完整链路
./scripts/test-run-isolated.sh --namespace fix_20260610 preflight
./scripts/test-run-isolated.sh clean               # 清理 7 天前旧测试运行目录
TEST_RUN_ROOT=/tmp/story2-codex-test-runs ./scripts/test-run-isolated.sh e2e
```

如果你在一台机器跑多个 worktree，建议把生产验证放在固定测试运行目录（例如 `/tmp/story2-test-runs`）里，并给每次执行带上显式 `TEST_NAMESPACE`。

## 代码质量与规范

- Python：`black`、`isort`、`flake8`、`mypy`
- Frontend：`eslint`、TypeScript strict、Jest/Playwright
- 安全：`./test.sh security`（Bandit）+ 契约安全测试系列（C-01~C-07：JWT secret、硬编码密钥、SSE auth、图片 base64、SQLAlchemy raw SQL、pickle 禁用、prompt injection）
- 性能：`./test.sh perf`（Locust）

## 数据与配置注意点

- 默认 DB：`data/game.db`（SQLite）  
- 可切换云 DB：设置 `DATABASE_URL`  
- 实验能力通过 `.env` 中 feature flags 控制，不要硬编码启用  
- 新增环境变量时，必须同步更新 `.env.example` 与对应文档
