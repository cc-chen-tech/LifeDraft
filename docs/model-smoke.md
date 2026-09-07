# 生产模型发布前验收

`model-smoke` 是真实 provider 的发布前门禁，不属于普通 PR 的确定性测试。

## GitHub 配置

在仓库中创建受保护的 GitHub Environment：`model-smoke`，并配置：

- required reviewers（至少一名发布审核人）；
- `OPENAI_API_KEY`；
- `MINIMAX_API_KEY`。
- 可选独立图片凭证 `IMAGE_API_KEY`，未配置时使用 `MINIMAX_API_KEY`。

两个 key 只能放在这个 Environment 的 Secrets 中。不要写入仓库、`.env`、普通 CI 变量或 Playwright fixture。

Environment Variables 可配置 `OPENAI_BASE_URL`、`OPENAI_MODEL`、`IMAGE_API_BASE_URL`、`IMAGE_MODEL` 和 `MINIMAX_TTS_MODEL`。默认分别使用 DeepSeek API 的 `deepseek-v4-flash`、MiniMax API 的 `image-01` 和 `speech-2.8-hd`。

手动执行 `Model Smoke` 时，workflow 的运行分支/tag 必须是候选版本。可选 `ref` 输入用于校验候选 branch、tag 或 commit 与本次运行的 `head_sha` 一致，不能用于替换实际 checkout。发布事件使用 release 对应的 SHA。workflow 会显式关闭确定性故事、local image 和 local audio，并使用独立数据库、独立端口和固定合成 fixture。

## 发布流程

1. main 的 E2E 成功后，发布 workflow 先确认全部普通 CI 通过，再手动触发受保护的 `Model Smoke`。候选版本已被新 main 替代时不再触发；触发期间发生更新会被 SHA 校验拒绝。也可在候选版本上手动运行 smoke，或发布候选 release 触发它。
2. 检查 workflow 产物 `smoke-summary.json`、`model-events.jsonl`、后端 JSONL 日志、Playwright trace 和 screenshot。
3. 确认四个检查均通过：文本生成与约束、图片落库与资源访问、TTS 落库与可播放、Daily World Projection 落库与 attempt 终态。
4. `Model Smoke` 成功后自动触发生产部署 workflow，重新核验同一 commit 的所有门禁。部署门禁会按 `head_sha` 查找成功的 smoke；即使手动强制部署，也必须通过同 SHA 的 smoke。部署会从 `.env.example` 同步 `MINIMAX_TTS_MODEL=speech-2.8-hd` 到生产环境。

普通 provider 重试会在报告中标记 `provider_retry_observed`。任何 fallback 都会产生 `fallback_requires_manual_confirmation`，即使最终输出成功也不能直接发布。未分类异常、空结果、非法结构、无法读取的资源、不可播放音频、超时或最终失败都会阻止发布。

## 本地命令

本地不会读取或猜测 provider secret。只有显式提供真实 key 和开关时才允许执行：

```bash
MODEL_SMOKE_ENABLED=1 \
OPENAI_API_KEY="$OPENAI_API_KEY" \
MINIMAX_API_KEY="$MINIMAX_API_KEY" \
./test.sh model-smoke
```

缺少开关、缺少真实 key 或启用了确定性/local provider 时，命令会在启动服务前失败。普通确定性验收仍使用：

```bash
./test.sh all
```

## JSONL 排查

模型事件只包含关联 ID、provider、model、阶段、重试/fallback、耗时、token usage 和低基数错误类型，不包含 prompt、response、API key 或用户故事原文。`model-events.jsonl` 是 smoke runner 的 provider 事件证据；生产 API 的同类事件位于后端 stdout JSONL 中。

```bash
# 失败、超时、限流
jq 'select(.event == "model_call" and (.outcome == "failure" or .error_kind == "timeout" or .error_kind == "rate_limit"))' backend.log

# 查找一次请求的完整 provider 链路
jq 'select(.event == "model_call" and .request_id == "REQUEST_ID")' backend.log

# 查找 fallback
jq 'select(.event == "model_call" and .fallback_from != null)' backend.log
```

`request_id` 由 API middleware 生成或透传，响应会返回 `X-Request-ID` 和 `X-Operation-ID`。SSE 与后台任务会继续携带 `operation_id`，Daily World Projection 的数据库 attempt ledger 与结构化 provider 事件可以用它们交叉核对。
