# 人生草稿本 (Life Draft Book)

AI 叙事人生模拟游戏：通过多轮事件生成、选择推进、关系与世界状态演化，体验不同人生轨迹。

## 当前实现（以代码为准）

- 前端：Next.js 16 + React 19（`frontend/`）
- 后端：FastAPI（`src/api`）
- 游戏核心：`src/game`
- AI 生成与叙事系统：`src/ai`
- 数据层：SQLAlchemy + Repository/Facade（`src/database`）
- 图片与高质量故事朗读：`src/services/image*`、`src/services/story_voice_reading.py`

> 当前仓库是 **FastAPI + Next.js** 主体；不包含 `src/ui/streamlit_app.py`。

## 主要能力

- 多轮事件生成与选择推进（SSE 流式 + 同步回退 + 502/504 自动重试）
- 每日时间线 v2：首日与后续章节共用事实、一致性和选项等硬性验收；首日段落、关键词等写法提示不单独拒稿。首日生成失败时可交付明确标记的安全开场
- 会话恢复（内存 session + 数据库自动恢复）
- 时间回溯存档（save points + timeline）
- 叙事质量档位（`fast / expert / master`）
- 叙事风格系统（古风/现代/科幻等风格自动匹配）
- 场景插画与角色/物品/地标收集系统（批量生成、时代一致性约束、人物面部一致性）
- MiniMax 分段 TTS、段落起读与按日续播进度
- 好友系统、角色预设与开场生成功能
- 成就系统（AchievementEngine）与人生回顾（LifeReview）
- 4D 资源状态（energy / mood / knowledge / wealth）
- 选择影响可视化（资源变化反馈）
- 角色创建 AI 反馈与设置再生（SettingFeedbackCard）
- 输入消毒与 Prompt Injection 防护（`sanitize_player_name` 等）

## 快速开始

### 方式一：一键启动（推荐开发）

```bash
./start.sh
./start.sh status
./start.sh tail
./start.sh stop
```

默认端口：

- 前端：`3000`
- 后端：`8000`
- 音乐服务：`3001`

### 方式二：手动启动

1. 安装后端依赖

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. 安装前端依赖

```bash
cd frontend
npm install
cd ..
```

3. 配置环境变量

```bash
cp .env.example .env
```

4. 启动后端

```bash
python3 run_api.py
```

5. 启动前端（新终端）

```bash
cd frontend
npm run dev
```

访问：`http://localhost:3000`

### 方式三：生产部署（ECS）

生产环境只允许通过 GitHub Actions 部署到 `/opt/story2`。合并 PR 后，
主干的 9 项 CI 全部通过才会启动受保护的真实供应商 `Model Smoke`；
它通过后自动触发 `Deploy Production`，部署精确的当前 `main` 提交并检查
`/health`、`/api/health`。安全开场可验证可玩性，但若首日没有交付模型正文，
Model Smoke 会以 `daily_opening_used_safe_fallback` 拒绝自动发布。
人工例外发布的条件和操作见 [生产部署指南](DEPLOYMENT.md)。

## 环境变量（核心）

请以 [`.env.example`](.env.example) 为准。最常用字段：

- `OPENAI_API_KEY`（必填）
- `OPENAI_MODEL`（`.env.example` 使用 `deepseek-v4-flash`；未设置时代码默认 `gpt-4`）
- `DATABASE_URL`（可选，不填则使用本地 SQLite）
- `DEFAULT_LANGUAGE`（`zh` / `en`）
- `MINIMAX_API_KEY`（生产音频必填；不要提交真实 key）
- `MINIMAX_TIMEOUT_SECONDS`（建议 `180`；真实 TTS 生成可能需要较长时间）
- `STORY_TTS_AUTO_READ_DEFAULT_ENABLED`（默认 `true`，用户可在播放器中关闭）
- `ENABLE_*` 叙事与实验开关（feature flags：constraint_harness, narrative_style_engine, creative_enhancement, epic_narrative, model_fallback, truncation_recovery, reactive_compression, parallel_postprocessing, generation_state_tracking）

## 开发与测试

### 后端

```bash
source venv/bin/activate
pytest tests/ -v
```

### 前端

```bash
cd frontend
npm test
npm run test:e2e
```

### 本地测试入口（推荐）

```bash
./test.sh all
./test.sh quick
./test.sh contract
./test.sh db
./test.sh e2e-core
```

`all` 是 preflight + 五层验收的兼容入口；真实供应商 `Model Smoke` 是单独的受保护发布门禁，
不会由普通本地 `all` 或 PR CI 代替。它检查模型正文、图片、TTS、保存与授权读回。
诊断细节见 [生成诊断手册](docs/generation-diagnostics-runbook.md)。

多 worktree/并行验证建议使用隔离入口（默认写入 `/tmp/story2-test-runs`）：

```bash
./scripts/test-run-isolated.sh all
./scripts/test-run-isolated.sh clean
```

### API 类型同步（前后端契约）

```bash
cd frontend
npm run sync:api-types
```

## 仓库结构（简版）

```text
story2/
├── src/
│   ├── api/          # FastAPI 路由、依赖、会话服务
│   ├── game/         # 游戏循环与状态推进
│   ├── ai/           # LLM 生成、叙事系统、约束校验
│   ├── services/     # 图片/音乐/实体识别等服务
│   └── database/     # ORM、Repository、Facade
├── frontend/         # Next.js 前端
├── config/           # 配置、Prompt、Feature Flags
├── tests/            # 后端测试
├── docs/wiki/        # 项目知识库（持续维护）
├── docker-compose.ecs.yml
├── run_api.py
├── start.sh
└── test.sh
```

## Repo Wiki

项目维护、升级设计与新功能规划请看：

- [docs/wiki/README.md](docs/wiki/README.md)
- 含架构、API/Session、排障、发布清单、模板（PR/ADR/事故复盘）
- 含 ADR 示例与按角色阅读路径
- CI 校验：`.github/workflows/wiki-check.yml`

## 文档索引（按角色）

| 角色 | 推荐入口 |
|---|---|
| 后端开发 | [02-system-architecture](docs/wiki/02-system-architecture.md), [03-api-and-session](docs/wiki/03-api-and-session.md), [11-module-index](docs/wiki/11-module-index.md) |
| 前端开发 | [01-quick-start](docs/wiki/01-quick-start.md), [06-api-call-matrix](docs/wiki/06-api-call-matrix.md), [08-troubleshooting](docs/wiki/08-troubleshooting.md) |
| 测试工程 | [04-development-and-testing](docs/wiki/04-development-and-testing.md), [10-release-and-change-checklist](docs/wiki/10-release-and-change-checklist.md) |
| 运维/发布 | [DEPLOYMENT.md](DEPLOYMENT.md), [10-release-and-change-checklist](docs/wiki/10-release-and-change-checklist.md), [08-troubleshooting](docs/wiki/08-troubleshooting.md) |
| 架构评审 | [15-adr-template](docs/wiki/15-adr-template.md), [ADR 示例](docs/wiki/adr/ADR-20260419-sse-over-websocket.md), [13-documentation-governance](docs/wiki/13-documentation-governance.md) |

完整角色路径见：[17-role-based-reading-paths](docs/wiki/17-role-based-reading-paths.md)

## 文档索引（按任务）

| 任务 | 文档 |
|---|---|
| 快速本地启动 | [01-quick-start](docs/wiki/01-quick-start.md) |
| 理解系统架构 | [02-system-architecture](docs/wiki/02-system-architecture.md) |
| 查 API 与会话机制 | [03-api-and-session](docs/wiki/03-api-and-session.md) |
| 前后端接口对齐 | [06-api-call-matrix](docs/wiki/06-api-call-matrix.md) |
| 新功能设计与落地 | [05-upgrade-and-feature-design](docs/wiki/05-upgrade-and-feature-design.md), [09-feature-playbooks](docs/wiki/09-feature-playbooks.md) |
| 上线前检查 | [10-release-and-change-checklist](docs/wiki/10-release-and-change-checklist.md), [生产部署指南](DEPLOYMENT.md) |
| 首日生成误判与安全开场 | [首日验收核对](docs/daily-opening-validation-audit-2026-09-28.md), [生成诊断手册](docs/generation-diagnostics-runbook.md) |
| 故障排查 | [08-troubleshooting](docs/wiki/08-troubleshooting.md) |
| PR/ADR/复盘模板 | [14-pr-template](docs/wiki/14-pr-template.md), [15-adr-template](docs/wiki/15-adr-template.md), [16-incident-retro-template](docs/wiki/16-incident-retro-template.md) |

## 说明

- 部署以 `DEPLOYMENT.md`（当前版本）为准；历史方案请以文档内状态说明识别。  
- 如 README 与代码不一致，以代码实现为准，并欢迎直接提交文档修复。

## 最近更新

- **2026-09-28**：同步每日首日/后续章节验收、Model Smoke 质量门禁及 GitHub Actions 生产发布流程。

## License

MIT
