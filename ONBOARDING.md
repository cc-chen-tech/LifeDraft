# LifeDraft 开发入门

> 最后核对：2026-09-28。项目入口以 [README](README.md) 和 [Repo Wiki](docs/wiki/README.md) 为准。

LifeDraft 是 FastAPI + Next.js 的 AI 人生叙事游戏。代码主路径在 `src/api`、`src/game`、`src/ai`、`src/database` 和 `frontend/`；长期维护的架构、测试与发布说明集中在 `docs/wiki/`。

## 开始开发

1. 按 [README 快速开始](README.md#快速开始) 配置 `.env` 并运行 `./start.sh`。
2. 阅读 [系统架构](docs/wiki/02-system-architecture.md)、[API 与会话](docs/wiki/03-api-and-session.md) 和 [开发测试](docs/wiki/04-development-and-testing.md)。
3. 在独立分支或 worktree 修改代码。提交前运行受影响模块的测试和 `./test.sh quick`；需要端到端验收时使用 `./test.sh e2e-core` 或隔离测试入口。
4. PR 中分别记录本地验证、远端 CI、真实供应商验收、合并和部署状态。PR 的检查通过不等于代码已上线。

## 首日故事与发布

每日时间线 v2 的首日与后续章节使用相同的事实、一致性和选项等硬性验收。首日段落、姓名/愿景位置和叙事关键词等写法提示不会单独拒稿。首日生成失败时，系统可以交付安全开场；它保障可玩性，但不代表真实模型正文通过质量验收。详见 [首日验收核对](docs/daily-opening-validation-audit-2026-09-28.md) 和 [生成诊断手册](docs/generation-diagnostics-runbook.md)。

生产环境由 GitHub Actions 发布到 ECS 的 `/opt/story2`：合并后等待当前 `main` 的九项 CI 和受保护的 Model Smoke，通过后自动部署并检查线上健康接口。直接在服务器执行 `git pull` 或 Docker Compose 不属于当前发布流程。操作和例外条件见 [生产部署指南](DEPLOYMENT.md)。

## 文档维护

修改 API、状态恢复、测试门禁或发布流程时，同步更新相关 wiki 与入口文档。历史设计稿保留原始背景；当前行为以代码、工作流和明确标为“最后核对”的运行文档为准。
