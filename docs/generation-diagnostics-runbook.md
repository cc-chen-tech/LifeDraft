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

普通日志不记录明文故事、prompt、音频、密钥、原始供应商错误消息。校验元数据保留规则码和稿次；需要具体拒稿原因时使用下述加密证据。错误发生位置保留文件名、函数和行号，不保留栈局部变量或代码行。

一致性检查使用 `story_consistency_check`，`phase=initial/repair` 和 `attempt_id` 区分初稿与修订稿。`finding_codes` 保留权威账本的 `age_mismatch`、`date_mismatch`、`identity_role_conflict` 等规则码；模型判断保留允许列表内的 `consistency_identity` 等类别，未知类别写为 `consistency_unknown`，不记录原始描述或证据文本。重复硬冲突停止修订时记录 `reason=consistency_circuit_break`；符合首日条件才进入安全开场选择，校验服务异常仍直接失败。

## 加密拒稿证据

`story_validation_evidence` 与上述元数据日志并存，使用同一文件轮转。`phase=consistency_initial/consistency_repair` 分别记录初稿和修订稿；`phase=finding` 记录 quick/Harness 硬拒绝。通过 `user_id`、`game_id`、`operation_id`、`attempt_id` 关联。

`encrypted_evidence` 使用 Fernet 认证加密，包含最多 4 个问题的具体描述、证据、证据附近短片段、修订建议、候选 hash 和开头/结尾各 160 字符。字段和密文大小均有上限，密钥先脱敏再加密；不保存完整草稿、prompt 或音频。超出的条数记录为 `truncated_issue_count`。这个证据能判断例如“明年二月”是否被误当成当天月份，但不能完整重建故事。

默认从运行环境的 `JWT_SECRET` 派生独立用途密钥；可用 `DIAGNOSTIC_EVIDENCE_KEY` 单独配置。`evidence_key_id` 用于识别应使用哪份密钥。轮换密钥后，历史证据需要旧密钥才能解密；旧日志原先未记录的内容不能恢复。不要将密钥放在命令参数、PR 或 CI 产物中。

具有后端环境访问权限的运维人员，在同一环境下显式指定用户与请求：

```sh
python -m scripts.read_validation_evidence \
  --user-id 123 --operation-id 'operation-id-from-log' logs/app.log logs/app.log.1
```

命令逐行读取、过滤其他用户与请求，并验证加密记录中的身份与外层日志一致；输出包含私密诊断片段，只用于授权排查，不作为公共 CI 产物上传。损坏密文、错误密钥、读取失败返回非零状态；无记录也明确返回非零状态。缺少密钥或加密失败时，生成流程继续，但写入 `error_code=validation_evidence_unavailable`，不会无声丢弃，也不会降级输出明文。

## 测试与发布边界

- `./test.sh quick`：静态检查、维护中的回归清单、前端类型及快速用例。清单在 `scripts/run-maintained-backend-tests.sh`，新增本次及历史故障回归；治理测试防止关键文件被漏注册。
- `./test.sh full-backend`：自动发现 `tests/` 下的全部 Python 测试。普通 PR 的 Backend Tests 工作流执行此命令，新增测试无需手动进入 40 文件白名单。
- `./test.sh acceptance`（兼容别名 `all`）：分层验收组合，**不是全部 pytest**。
- 前端 CI 运行全部 Jest；E2E core 使用确定性模型检查真实 UI/保存/恢复链路。它不能证明线上供应商会按预期输出。
- 受保护的 Model Smoke 另行调用真实供应商，新增历史人物 MASTER 首章：真实 GameLoop、校验、选项、SQLite 保存、权限读回、`/play` 正文/选项和刷新。安全开场也执行保存、授权读取、浏览器刷新和选项结算至第二天，并以 `delivery_mode=safe_first_day` 明确标记。可玩性与模型质量分别验收：只要用了安全开场，报告仍以 `daily_opening_used_safe_fallback` 阻止自动发布，不能冒充模型正文通过；有调用/时间上限。开关与本次生产核对值一致：Harness 与软篇幅开启，统一预算关闭。
- Model Smoke 浏览器登录使用隔离测试账户；临时会话文件权限为 0600，不上传。该流程禁用 Playwright trace，避免其网络记录包含认证 cookie。
- Model Smoke 的选择结算若已提交、但随后读回短暂失败，Playwright 重试通过已保存的 `day_history` 验证原事件、首日日期、所选选项和第二天时间线；不会再次假设 `current_event` 仍存在。该恢复分支仅用于重试，首次执行仍须完成正文/选项/刷新验收。

日志证据回归覆盖加解密往返、两用户并发归属、篡改身份、错误密钥、缺失密钥、凭据脱敏、大小上限、轮转文件重复读取，以及真实生成流程中初稿/修订稿的独立证据。CI maintained coverage 注册 `test_validation_evidence.py`。

本地通过、远端 CI 通过、真实模型验收、合并、上线是不同状态。PR 中分别记录本次证据；此文档不宣称改动已经部署。

## 叙事关键词提示

首段“核心冲突”与结尾“决策点”的关键词未命中不再作为拒稿证据：首段产生 warning，结尾产生 LOW 诊断且不扣分，均不能单独触发重写、熔断或安全开场。提示词仍要求呈现冲突与可供选择的局面；选项生成、事实一致性和持久化检查继续执行。日志保留 `daily_opening_missing_core_conflict` 与 `decision_point_ending`，后者以 `outcome=warning` 标明未拒稿。

`test_narrative_keyword_advisories.py` 覆盖中英文隐含冲突、隐含决策、三个质量档位和零扣分/零重试；`test_story_delivery_diagnostics.py` 的 `keyword_variance` 用例执行真实生成编排、文件 SQLite、授权接口读取与选择结算，验证原文交付且仅一次正文调用。供应商回复由固定夹具提供，这不等同于真实模型验收。

年龄一致性按陈述区分回忆与当前：例如“那时十九岁……此刻二十八岁”不以回忆年龄触发当前年龄拒稿。扫描不会在首个正确年龄或回忆年龄处终止；后面的错误当前年龄仍会被拒。相关回归在 `test_continuity_ledger.py`，实际调用证据在首日真实模型复现报告的 2026-09-28 追加部分。
