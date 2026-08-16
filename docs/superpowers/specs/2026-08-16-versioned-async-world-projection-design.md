# 版本化异步世界投影设计

**日期：** 2026-08-16
**状态：** 已确认
**适用范围：** 日历时间线 v2 的每日故事生成、重新生成、选择结算、世界状态提取与存档修复

## 1. 背景与目标

孙悟空游戏暴露出一条相互放大的故障链：玩家选择已经结算并进入下一天，但上一日世界状态提取为空；旧地点、旧承诺和旧因果继续作为硬约束参与校验；专家档三次候选生成因此耗尽；此后存档没有 `current_event`，而“再次生成”仍调用只支持替换现有事件的 `/regenerate-stream`，后端立即抛出 `No current daily event`。前端又在每日过渡层中屏蔽了生成提示，使操作看起来没有反应。

本设计同时达成以下目标：

1. 玩家选择始终立即结算，不等待世界状态提取。
2. 故事原子保存完成后立即开始世界状态提取，充分利用玩家阅读时间。
3. 已接受故事和玩家选择是规范事实；陈旧的地点、承诺和因果不能硬拒绝新故事。
4. 世界提取的解析失败或可疑全空必须可检测、可重试、可跨页面恢复。
5. 缺失故事与替换故事使用正确的生成语义，并由前后端共同防御误调用和重复点击。
6. 修复既有存档时只重建隐藏派生状态，不修改玩家已经读过的故事、选择或数值结算。

非目标：

- 不改变开篇故事和旧版周时间线的行为。
- 不让玩家看到世界投影、覆盖率或内部校验诊断。
- 不用确定性关键词规则直接写入世界事实；规则只判断提取结果是否可疑。
- 不在本次改造中合并 `/event` 与 `/regenerate-stream` 的公开 URL。

## 2. 核心不变量

### 2.1 规范事实层级

事实优先级从高到低为：

1. 已持久化的玩家选择及其确定性数值效果。
2. 玩家已经看到的已接受故事 revision。
3. 从这些故事和选择生成、且来源 revision 仍有效的世界投影。
4. 尚未追平水位的旧地点、旧承诺、旧因果和旧习惯记录。

生成提示可以引用所有层级，但只有前三层中的新鲜、高置信信息可以参与硬校验。第四层只能作为写作提示。

### 2.2 原子性与版本隔离

- 新故事只有在正文、选项、结构校验和持久化全部成功后，才成为当前接受 revision。
- 重新生成使用候选状态；失败候选不得改变人物关系、世界模型、待引入人物或配图归属。
- 世界投影以 `(game_id, event_id, revision)` 唯一标识。
- 旧 revision 被替换后立即标记为 `superseded`；旧 worker 即使晚返回，也不得写入状态。
- 世界补丁按 `game_id + day_index` 串行应用，不能跨天乱序提交。

### 2.3 可用性优先

- 世界投影的 pending、失败或积压不阻塞玩家选择、日期推进或下一篇生成。
- 下一篇必须直接携带水位之后的已接受故事与玩家选择，而不是只依赖尚未更新的世界模型。
- 只有确定性结构错误、明确违反规范事实或缺失本场必须角色等高置信问题可以消耗候选预算。

这里的“故事完成后立即运行世界约束”是指立即创建任务、提取、覆盖检查并形成当前 revision 的可用 overlay；正式的已结算世界快照仍在玩家选择时或选择后的串行 applier 中提交。这样既利用阅读时间，又允许重新生成通过 supersede 旧 revision 安全撤换 overlay。

## 3. 统一生成意图与 Single-flight

### 3.1 完整事件判定

后端提供唯一判定函数 `is_complete_daily_event(value) -> bool`。只有同时满足以下条件才视为可替换事件：

- `event_id` 非空；
- `revision` 为大于等于 1 的整数；
- 正文非空；
- 选项通过现有每日事件 schema 校验。

前端可据此选择入口，但后端判定是最终权威。不完整事件按缺失事件处理，并在日志中记录 `incomplete_current_event`，不能直接覆盖其原始存档快照。

### 3.2 生成意图

保留两个公开 SSE 入口：

- `/event` 表示 `ensure_current`：确保当前日期存在一个完整事件。
- `/regenerate-stream` 表示 `replace_current`：替换一个完整的当前事件。

后端在游戏状态锁内解析真实模式：

| 请求意图 | 当前状态 | 解析模式 |
| --- | --- | --- |
| `ensure_current` | 无完整事件 | `generate_missing` |
| `ensure_current` | 已有完整事件 | 直接返回现有事件 |
| `replace_current` | 已有完整事件 | `replace_current` |
| `replace_current` | 无完整事件 | 防御性降级为 `generate_missing` |

因此，误调用 `/regenerate-stream` 不再产生 `No current daily event`。

### 3.3 前端 Single-flight

所有生成入口共享同一个命令状态：

`idle -> starting -> running -> succeeded | failed`

- 点击处理器在任何异步操作前同步设置 in-flight ref，防止同一事件循环中的双击。
- `starting` 或 `running` 时，过渡页、错误卡片、工具面板和聊天入口全部复用当前操作，不得再次发请求。
- 缺失事件调用 `/event`；完整事件调用 `/regenerate-stream`。
- 重新生成已有故事时保留旧正文和选项，直到替换原子提交成功。
- 页面刷新或 SSE 重连使用 `operation_id` 和事件游标重新订阅，不创建新 worker。

### 3.4 后端 Single-flight

复用现有 `EventGenerationCoordinator`，统一操作 key：

`(game_id, day_index, resolved_mode, base_event_id, base_revision)`

- `generate_missing` 的 `base_event_id` 为空、`base_revision` 为 0。
- `replace_current` 固定绑定开始时的事件 ID 和 revision。
- 相同 key 的并发请求订阅同一 operation。
- 同一游戏同一天存在不同 running key 时返回或订阅权威 operation，不能启动第二个写 worker。
- 最终持久化继续使用 revision/CAS 检查；进程内协调器不是数据正确性的唯一保障。

每次玩家主动终态重试都建立新的 `operation_id` 和新的质量档候选预算。上次 `RETRY_EXHAUSTED` 与 `resume_view.failed` 只用于展示，不能阻止新操作。`attempts_used` 必须来自实际候选调用计数器。

### 3.5 SSE 契约

现有事件类型保持兼容，status 和 terminal failure 增加可选字段：

```json
{
  "operation_id": "...",
  "requested_intent": "replace_current",
  "resolved_mode": "generate_missing",
  "phase": "generating_story",
  "attempt": 1,
  "max_attempts": 3
}
```

终态失败只向玩家展示简明、可行动原因；软质量发现、投影失败和内部状态不进入阅读界面。

## 4. 版本化世界投影

### 4.1 启动时机

每日事件原子持久化成功后，立即执行 `ensure_world_projection(game_id, event)`，不再等待玩家选择。该调用只创建或唤醒任务，不阻塞 SSE complete。

投影一次处理：

- `story_patch`：故事正文中已经发生的事实、地点、职业、习惯、伏笔、承诺和因果变化；
- `option_patches`：每个选项若被选择时才成立的世界变化。

这样玩家阅读期间即可完成大部分工作；选择时只需采用对应 `option_patch` 和已有确定性资源效果，不必再等待一次大模型调用。

### 4.2 持久化模型

新增 `daily_world_projections` 表，最少包含：

| 字段 | 含义 |
| --- | --- |
| `game_id`, `event_id`, `revision` | 唯一来源身份 |
| `day_index`, `story_date` | 串行应用顺序 |
| `source_hash` | 正文、选项、prompt/schema 版本的稳定哈希 |
| `status` | `pending/running/ready/ready_no_change/failed_retryable/applied/superseded` |
| `story_patch_json` | 故事已经发生的变化 |
| `option_patches_json` | 以选项索引为键的候选变化 |
| `coverage_json` | 确定性覆盖检查证据和结果 |
| `attempt_count`, `next_attempt_at` | 持久化重试状态 |
| `lease_owner`, `lease_expires_at` | worker 崩溃恢复与抢占保护 |
| `error_code` | 机器可读失败类别 |
| 时间戳字段 | 创建、更新和应用时间 |

唯一约束为 `(game_id, event_id, revision)`。worker 更新必须同时匹配 `source_hash` 和未 superseded 状态。

玩家状态新增 `world_projection_state` 派生层，保存按天物化后的七类世界信息、每条记录的来源事件/revision/day index，以及应用水位。现有来源不明的 world model 不原地删除或覆盖，只作为 legacy soft hints。提示构建器和校验器通过统一 resolver 读取“不可变基础事实 + 新投影层 + legacy soft hints”，不再直接把旧混合字段当作同等权威。

另建 `daily_world_projection_attempts` 调用账本，逐次记录 projection/game、开始与完成时间、结果和错误类别。每日调用上限、最近一小时异常率和维修审计只能由该账本计算，不能由累计 attempt count 或进程日志推断。`world_projection_state.applied_sources` 保存已经物化的 `(event_id, revision, day_index)`，保证崩溃重放幂等。

任务执行使用应用进程内的常驻 projection service，每 15 秒扫描并领取到期记录，不引入 Redis/Celery 等新外部依赖。数据库 lease 负责多实例互斥；worker 每 15 秒续租，lease 时长为当前 provider 单次超时加 60 秒。进程重启后，其他实例可以领取租约已过期的任务。

### 4.3 选择结算与补丁应用

选择事务不等待任何新的模型调用。它在一个 staged candidate 中完成确定性结算、写入 day history、推进日期并清空当前事件，然后一次持久化：

- 投影已 ready：在同一候选状态中合并 `story_patch`、被选中的 `option_patch` 和确定性选择效果，再提交选择事务。
- 投影未 ready：选择照常提交；day history 记录投影身份和 pending 状态，由串行 applier 稍后补齐。
- 投影在选择之后完成：applier 根据 day history 中实际选项索引采用唯一对应补丁。
- 后续天的投影可以先计算完成，但 `applied_through_day_index` 不能跨过任何 pending 或 failed 天；缺口之后的 ready patch 保持等待。玩家流程和下一篇生成通过规范故事 ledger 继续，不通过跳过缺口伪造已追平水位。

### 4.4 重新生成

开始重新生成不会撤销当前 revision，也不会清除其投影。只有新 revision 原子提交后才：

1. 标记旧 revision 投影为 `superseded`；
2. 建立新 revision 投影；
3. 失效旧 revision 配图和预取结果；
4. 更新前端为新故事。

替换失败时四步均不发生，旧故事、选项、投影和配图继续有效。

## 5. 空结果检测与持久化恢复

### 5.1 失败不再伪装为成功

世界提取层不得在两次异常后返回七个空数组。以下情况抛出可分类错误并把任务设为 `failed_retryable`：

- provider、网络或超时错误；
- 不是 JSON object；
- 字段类型或 patch schema 不正确；
- source hash/revision 已变化；
- 覆盖检查判断全空结果与故事不相容。

### 5.2 合法全空

提取结果全空时运行确定性覆盖检查。检查只识别是否存在需要进一步解释的信号，包括：

- 已跟踪角色与明确移动、到达、离开或所在地表达同时出现；
- 承诺、约定、任务的建立、履行、取消或失败；
- 明确的事实状态变化、职业变化或长期习惯变化；
- 已记录因果链的原因或结果被正文明确触发。

不存在信号时记录 `ready_no_change`；存在信号时视为提取不完整并重试。该检查绝不直接创建事实，也绝不拒绝玩家已经看到的故事。

### 5.3 重试策略

事件接受后的快速重试窗口为：立即、5 秒、30 秒、2 分钟、5 分钟。该计划由服务端持久化任务驱动，因此即使浏览器一直停留在阅读页、关闭工具面板或 SSE 已结束，重试仍会继续。

五次仍失败时保持 `failed_retryable`：

- 持久化 sweeper 在 30 分钟和 2 小时后再次尝试；
- 两次维护重试仍失败后，按 oldest-first 每个自然日最多再尝试一次，直至成功或来源 revision 被 supersede；
- 游戏加载和下一篇生成会唤醒已到期任务；
- worker lease 到期后其他 worker 可以安全接管；
- 每个游戏每天最多执行 8 次投影模型调用，超限只推迟任务，不改变规范事实或玩家流程。

## 6. 世界水位与校验降级

`world_projection_state` 提供以下摘要：

- `projected_through_day_index`
- `applied_through_day_index`
- `pending_from_day_index`
- `oldest_pending_at`

提示构建器在水位落后时附带从 `applied_through_day_index + 1` 起的已接受故事摘要、必要原文片段和玩家选择。这些内容优先于旧世界模型。

校验器按来源和新鲜度定级：

- 已接受故事/选择之间的明确冲突：可 hard。
- 身份、不可变背景、必须角色和确定性结构错误：可 hard。
- 水位之后的地点、承诺、因果、职业和习惯：只能 soft。
- 来源不明的旧派生状态：只能 soft。
- soft finding 不触发候选重写，不消耗 fast/expert/master 候选次数。

因此，世界投影失败会降低隐藏状态精度，但不能再把玩家锁死。

## 7. 阅读界面行为

### 7.1 缺失故事过渡页

每日过渡层本身承载完整状态，不依赖可能被屏蔽的 toast：

- idle failed：显示“下一日故事暂未生成”和重试按钮；
- starting/running：按钮立即禁用，显示持久生成状态和自动尝试进度；
- terminal failed：显示简明原因和可用的再次重试；
- completed：切换到新故事。

### 7.2 替换已有故事

- 旧故事保持可读，替换期间只禁用冲突操作。
- 成功后一次性切换正文、选项、revision 和配图身份。
- 失败后在旧故事附近显示终态失败原因；不显示内部 validator 或世界投影诊断。
- 所有按钮共享相同 operation state，不能因工具抽屉关闭或组件卸载丢失状态。

## 8. 既有存档修复

修复工具按以下顺序运行：

1. dry-run 扫描；
2. 输出命中游戏、原因、预计重建天数和状态校验和；
3. 对每个命中游戏备份完整状态；
4. 从已接受 day history 和选择按天建立投影；
5. 只重建新的 narrative-derived 隐藏层；旧混合世界模型保留为 soft hint；
6. 按 revision/CAS 写入并记录修复审计；
7. 重新读取验证玩家可见字段完全未变。

命中条件至少包括：

- `postprocessing_status=complete`，但 world 七类更新全空且覆盖检查发现变化信号；
- pending/failed 后处理长期未恢复；
- 世界应用水位落后 day history；
- 已结算进入下一天、没有 current event、且 resume view 为可重试生成失败。

游戏 156 应由规则自然命中，工具不得硬编码游戏 ID。修复不修改故事正文、选项、选择、资源、关系结算、日期或 day index。

## 9. 上线与回滚

### PR 1：解除卡死并建立安全边界

- 前后端生成意图分流；
- 前后端 single-flight；
- 过渡页持久状态与终态原因；
- 玩家重试获得新 operation 和预算；
- 水位不新鲜时，地点、承诺和因果立即降为 soft；
- 修正 `attempts_used`。

PR 1 尚无新投影表时，以现有 day history 推导临时水位：从第一个 `postprocessing_status` 为 pending/failed，或“complete 但七类世界更新全空且覆盖检查命中”的日期开始，所有既有地点、承诺和因果都按 stale 处理。PR 2 上线后改由持久化投影水位提供同一接口。

该 PR 上线后，游戏 156 即使尚未完成隐藏状态重建，也应能重新生成下一日故事。

### PR 2：版本化异步世界投影

- 投影表、worker lease、revision fencing；
- 故事接受后立即提取；
- story/option patch；
- 合法全空判定、持久化重试、串行应用和水位推进。

### PR 3：存档修复与生产观测

- dry-run、备份、重建和审计工具；
- 仅修复扫描命中的存档；
- 投影积压、可疑全空、重试、superseded late write 和陈旧约束降级指标。

回滚 PR 2/3 时停止新投影 worker，并让提示构建器继续直接使用已接受故事与选择；投影表是派生数据，可保留但不读取。任何回滚都不得回滚玩家故事或选择。

## 10. 测试与验收

### 10.1 生成和 UI

- 无 current event 的所有重试入口只产生一个 `generate_missing` operation。
- 有完整 current event 时重新生成走 `replace_current`。
- 直接误调用 regenerate 且无 current event 时后端防御性分流。
- 双击、多入口并发和 SSE 重连只运行一个 worker。
- 快速失败时过渡页仍显示可见终态原因。
- 替换失败后旧正文、选项、revision 和配图保持不变。
- 自动三次失败后，玩家再次点击得到新 operation 和完整新预算。

### 10.2 投影

- 事件持久化完成后、玩家选择前已经创建投影任务。
- 重新生成成功后旧 revision late result 被拒绝。
- 明确移动或承诺变化却返回全空时进入重试。
- 无变化故事可以进入 `ready_no_change`。
- provider/JSON/schema 失败不能标记 complete。
- 页面停留期间会按计划重试；刷新后从持久状态继续。
- 选择时投影 pending 仍立即推进日期。
- 多日投影完成顺序混乱时，应用顺序仍按 day index。

### 10.3 校验和修复

- 水位落后时旧地点、承诺和因果只能产生 soft finding。
- soft finding 不触发重写、不增加 `attempts_used`。
- 明确违反已接受故事的候选仍可 hard reject。
- 游戏 156 形态的 fixture 能被 dry-run 命中。
- 修复前后玩家可见故事、选项、选择、日期、资源和关系结算逐字段相等。
- 修复失败可以从备份恢复，并留下审计记录。

## 11. 生产观测

日志统一携带 `game_id`、`day_index`、`event_id`、`revision`、`operation_id` 或 projection ID。至少记录：

- requested intent 与 resolved mode；
- operation coalesced 次数；
- 候选次数和终态原因；
- projection 状态迁移、重试原因与积压时长；
- 可疑全空与合法 no-change 计数；
- stale hard finding 被降级的计数；
- superseded worker 的 late write 拒绝。

发布验收分别检查当前 `origin/main`、本地门禁、CI、实际部署 revision、健康检查和游戏 156 的真实恢复结果，不能用历史快照代替当前证据。
