# 生产模型发布前验收

`model-smoke` 是真实 provider 的发布前门禁，不属于普通 PR 的确定性测试。

## GitHub 配置

在仓库中创建受保护的 GitHub Environment：`model-smoke`，并配置：

- required reviewers（至少一名发布审核人）；
- `OPENAI_API_KEY`；
- `MINIMAX_API_KEY`。

两个 key 只能放在这个 Environment 的 Secrets 中。不要写入仓库、`.env`、普通 CI 变量或 Playwright fixture。

手动执行 `Model Smoke` workflow 时，可以通过 `ref` 指定 branch、tag 或 commit；发布事件会自动使用 release tag。workflow 会显式关闭确定性故事、local image 和 local audio，并使用独立数据库、独立端口和固定合成 fixture。

## 发布流程

1. 在候选 commit 上手动运行 `Model Smoke`，或发布候选 release 触发它。
2. 检查 workflow 产物 `smoke-summary.json`、`model-events.jsonl`、后端 JSONL 日志、Playwright trace 和 screenshot。
3. 确认四个检查均通过：文本生成与约束、图片落库与资源访问、TTS 落库与可播放、Daily World Projection 落库与 attempt 终态。
4. 让生产部署 workflow 使用同一个 commit。部署门禁会按 `head_sha` 查找成功的 `Model Smoke`；没有同 SHA 的成功 smoke，部署会等待并最终失败。

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
