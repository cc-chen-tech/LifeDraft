# 生产部署指南

> 最后核对：2026-09-28。以 `.github/workflows/deploy-production.yml`、`.github/workflows/model-smoke.yml` 和 `scripts/deploy.sh` 的当前实现为准。

## 当前部署方式

生产站点为 [story101.live](https://story101.live)，唯一部署目录为 ECS 上的 `/opt/story2`。生产发布由 GitHub Actions 的 `Deploy Production` 工作流执行；不要直接登录服务器拉代码、运行 Compose 或建立第二套部署目录。

工作流在 ECS 上把代码切到待发布的精确提交，配置 MiniMax 音频和图片相关环境变量，再调用 `scripts/deploy.sh`。部署后检查公开的 `/health`、`/api/health` 及后端能力标记。生产运行 FastAPI、Next.js 和 Nginx；当前发布检查要求 `music_runtime_enabled=false`，MiniMax TTS 可用。

## 正常发布链

1. PR 的检查与评审通过后合并到 `main`。
2. 当前 `main` 提交的九项工作流全部通过：Backend Tests、Python Code Quality、Frontend Build、Frontend Code Quality、Frontend Tests、Coverage Report、CI、Wiki Check、E2E Tests。
3. 主干 E2E 完成后，发布链在受保护环境运行真实供应商 `Model Smoke`。它检查模型正文和选项、首日交付与授权读回、故事起源、图片、TTS、世界投影。首日交付必须是 `delivery_mode=model`；安全开场可玩，但会以 `daily_opening_used_safe_fallback` 阻止自动发布。
4. Model Smoke 成功后自动请求 `Deploy Production`。工作流只接受当时仍是 `main` 顶端的精确 SHA，并在 ECS 部署后执行公开健康检查。

主干 CI 通过、Model Smoke 通过、部署作业通过和线上功能可用是不同状态。不要把触发 Model Smoke 的 `Deploy Production` 准备作业当成已经部署；以带有 `Deploy to ECS host` 成功作业的运行记录为准。

## 需要的配置

- GitHub `model-smoke` 受保护环境：真实 `OPENAI_API_KEY`、`MINIMAX_API_KEY`；图片密钥可用 `IMAGE_API_KEY` 或 MiniMax 密钥。模型、图片与 TTS 地址/型号由工作流变量或默认值指定。
- GitHub `production` 环境：`ECS_HOST`、`ECS_SSH_KEY`、`MINIMAX_API_KEY`；`ECS_USER` 可选。生产 URL 可由 `PRODUCTION_URL` 指定，默认 `https://story101.live`。
- ECS 唯一部署目录 `/opt/story2` 中保留服务所需的 `.env`。`JWT_SECRET_KEY` 等生产密钥使用独立值，不能提交到仓库。工作流会更新受管的 MiniMax、图片和每日时间线变量。

本地开发的变量示例见 [`.env.example`](.env.example)；不要把本地 `.env` 当作生产密钥来源。

## 手动重试和例外发布

正常链路会自动部署，无需手动触发。若自动部署步骤因临时问题失败，先核对当前 `main` SHA 与全部门禁，再从 GitHub Actions 的 `Deploy Production` 手动重试，填写完整的 40 位 `candidate_sha`。提交已被新合并覆盖时，旧 SHA 不会被部署。

`allow_without_model_smoke=true` 是明确的人工例外：其余九项主干工作流必须在同一提交上全部通过。使用前查看 Model Smoke 的 `smoke-summary.json`，记录失败原因；例如只有 `daily_opening_used_safe_fallback` 时，功能可用但模型正文质量门禁未通过。此开关不会让 Model Smoke 变绿，也不会替代对真实失败的修复。

`force_after_local_preflight=true` 仅供 GitHub CI 不可用且已经完成本地预检的特殊情况；它与 `allow_without_model_smoke` 不能同时使用。两种例外都必须通过受保护工作流执行，不能绕过它直接操作 ECS。

## 验证与回滚

部署完成后，在运行日志中核对 `DEPLOY_SHA`、ECS 的 `HEAD is now at ...`、后端健康状态，以及 `/health`、`/api/health` 的 smoke 结果。线上健康接口正常只证明服务可达；首日模型正文质量仍以对应 SHA 的 Model Smoke 报告为准。

发布版本只能是当前 `main` 顶端。需要回滚时，在仓库中撤销有问题的变更并形成新的 `main` 提交，让同一套 CI、Model Smoke 和部署门禁验证该提交；不要直接在 ECS 上 `git checkout` 旧版本。

相关入口：[README](README.md)、[发布检查清单](docs/wiki/10-release-and-change-checklist.md)、[生成诊断手册](docs/generation-diagnostics-runbook.md)。
