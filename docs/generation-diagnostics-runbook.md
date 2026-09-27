# 故事、图片、语音失败排查与回归门禁

这次修复的目标是让每次失败都有可追溯的记录，同时保证未保存的故事不会被当作成功交付。模型、网络和磁盘仍可能失败；测试验证的是这些失败的处理、归属和恢复路径，不能保证供应商永远成功。

## 如何找到某位用户的问题

生产日志位于挂载目录 `logs/app.log*` 和 `logs/model.jsonl*`。每份最大 10 MiB、保留 5 份备份；Docker 标准输出也按 10 MiB × 5 轮转。容量轮转不是永久存档，历史超出容量后会被删除；需要长期审计时应把两个文件流接入集中存储。

按 `user_id` 找到用户记录，再按 `game_id`、`operation_id`、`job_id` 聚合。浏览器请求有 `request_id`；异步任务的入队事件连接该请求与持久化任务。重启后的 worker 从数据库重建任务身份，不依赖旧 HTTP 请求仍然存在。画像任务、语音任务分别保留自己的 `job_type`，避免相同数字 ID 混淆。

示例（在项目目录执行，只输出元数据）：

```sh
jq -c 'select(.user_id == 123)' logs/app.log logs/app.log.1 logs/model.jsonl
jq -c 'select(.operation_id == "voice:456" or (.job_type == "voice" and .job_id == 456))' logs/app.log logs/model.jsonl
```

客户端记录的 actor 身份由登录凭据验证，不能由上传 JSON 的 `user_id` 指定。客户端提供的 game/job/asset 字段是诊断线索，不能用来授予访问权限；音频资源另行检查用户所有权。

## 关键节点及证据

| 链路 | 保留的关键结果 | 主要回归文件 |
| --- | --- | --- |
| 故事草稿 | 每稿 provider、shape、quick、一致性初稿/修订稿、Harness 检查、finding code、重试/熔断/兜底 | `test_story_delivery_diagnostics.py`, `test_daily_opening_delivery.py` |
| 故事交付 | 保存成功后才发送正文/complete；保存失败还原旧状态；失败记录再次保存失败也单独留痕 | `test_story_delivery_diagnostics.py`, `test_round_event_sse_terminal_contracts.py` |
| 故事起点 | 截断、超时、调用上限、重复点击与明确重试 | `test_story_origin_generation.py`, 前端 `api.test.ts`, `CreatePage.test.tsx` |
| 推荐预取 | 入队、运行、校验、持久化、恢复与二次数据库异常 | `test_daily_recommended_prefetch.py`, `test_story_delivery_diagnostics.py` |
| 图片 | job/slot/batch 结果、被新版本替代、provider→磁盘→DB、参考图降级、Future 崩溃 | `test_image_diagnostics.py` 和 portrait/image 历史回归 |
| 语音 | 入队、重启、每段合成、旁白方案、拼接、资产入库、关停、重试历史 | `test_voice_diagnostics.py` 和 voice/TTS 历史回归 |
| 语音资源 | 匿名拒绝、其他用户拒绝、所有者 Range 播放、预览所有权 | `test_voice_audio_ownership.py`, `test_tts_audio_transport.py` |
| 浏览器 | SSE 失败/中断、API 错误、媒体失败与恢复、轮询重试与恢复 | `remote-diagnostic.test.ts`, `sse.test.ts`, `StoryListeningExperience.test.tsx` |
| 用户关联 | 并发用户、嵌套上下文、worker 重启、生成器入口不丢身份 | `test_diagnostic_lifecycle.py`, `test_request_observability.py`, image/voice/story diagnostics |
| 日志保留 | JSON 格式、源码位置、异常类型/安全调用栈、供应商业务码/trace、独立轮转文件 | `test_diagnostic_lifecycle.py`, `test_model_telemetry.py` |

不记录故事正文、prompt、音频内容、密钥、原始供应商错误消息。校验日志保留规则码和稿次，因此能回答“第几稿被哪条规则拒绝”；不能借这些日志重建原始草稿。错误发生位置保留文件名、函数和行号，不保留栈局部变量或代码行。

一致性检查使用 `story_consistency_check`，`phase=initial/repair` 和 `attempt_id` 区分初稿与修订稿。`finding_codes` 保留权威账本的 `age_mismatch`、`date_mismatch`、`identity_role_conflict` 等规则码；模型判断保留允许列表内的 `consistency_identity` 等类别，未知类别写为 `consistency_unknown`，不记录原始描述或证据文本。重复硬冲突停止修订时记录 `reason=consistency_circuit_break`；符合首日条件才进入安全开场选择，校验服务异常仍直接失败。

## 测试与发布边界

- `./test.sh quick`：静态检查、维护中的回归清单、前端类型及快速用例。清单在 `scripts/run-maintained-backend-tests.sh`，新增本次及历史故障回归；治理测试防止关键文件被漏注册。
- `./test.sh full-backend`：自动发现 `tests/` 下的全部 Python 测试。普通 PR 的 Backend Tests 工作流执行此命令，新增测试无需手动进入 40 文件白名单。
- `./test.sh acceptance`（兼容别名 `all`）：分层验收组合，**不是全部 pytest**。
- 前端 CI 运行全部 Jest；E2E core 使用确定性模型检查真实 UI/保存/恢复链路。它不能证明线上供应商会按预期输出。
- 受保护的 Model Smoke 另行调用真实供应商，新增历史人物 MASTER 首章：真实 GameLoop、校验、选项、SQLite 保存、权限读回、`/play` 正文/选项和刷新。安全开场也执行保存、授权读取、浏览器刷新和选项结算至第二天，并以 `delivery_mode=safe_first_day` 明确标记。可玩性与模型质量分别验收：只要用了安全开场，报告仍以 `daily_opening_used_safe_fallback` 阻止自动发布，不能冒充模型正文通过；有调用/时间上限。开关与本次生产核对值一致：Harness 与软篇幅开启，统一预算关闭。
- Model Smoke 浏览器登录使用隔离测试账户；临时会话文件权限为 0600，不上传。该流程禁用 Playwright trace，避免其网络记录包含认证 cookie。

本地通过、远端 CI 通过、真实模型验收、合并、上线是不同状态。PR 中分别记录本次证据；此文档不宣称改动已经部署。
