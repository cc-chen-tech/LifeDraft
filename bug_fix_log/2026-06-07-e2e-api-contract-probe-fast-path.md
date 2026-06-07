# E2E API contract probe 快速失败修复记录

## 问题
E2E 的轻量 API contract 探测会访问故事重新生成相关端点。该类探测只应该验证端点契约，不应该触发真实的长耗时故事重生成，否则会拖慢 E2E，甚至把探测流量误当成真实用户生成任务。

同时，匿名创建的游戏在没有 `current_event` 时调用 `choice-sync`，旧路径可能返回 400，与 API contract 探测期望的“请求语义不完整/不可处理”状态不一致。

## 复现
1. 运行 API contract 探测或 E2E API 探测层。
2. 探测 `/api/story/{game_id}/regenerate-stream` 时可能进入真实重生成路径。
3. 匿名游戏未生成事件时调用 `/api/games/{game_id}/choice-sync`，返回状态不稳定，不利于 contract gate 判断。

## 修复
1. `test.sh e2e` 启动后端时注入 `E2E_CONTRACT_PROBE_FAST=1`。
2. `src/api/routers/story.py` 在该环境变量开启且请求来自 Playwright APIRequest 探测时，对 regenerate stream 快速返回 422，避免触发真实故事重生成。
3. `src/api/routers/gameplay/events.py` 使用同样的 Playwright User-Agent 判定事件生成探测，避免把真实 E2E 中 cookie 缺失/匿名请求误判为 contract probe。
4. `src/api/routers/gameplay/choices.py` 对匿名且无当前事件的 choice/custom-choice 请求，将恢复事件阶段的 400 转换为 422。
5. `src/api/routers/gameplay/events.py` 将“generation in progress”映射为 429，避免同步生成端点泄漏内部 ValueError。

## 测试
1. `tests/test_gate_preflight_no_mock.py::test_e2e_api_contract_probe_does_not_trigger_long_story_regeneration`
   - 断言 story/events 两个路由都用 Playwright User-Agent 判定 probe；
   - 断言 events 路由不能用“无 cookie”作为 probe 判定。
2. `tests/test_api_contract.py::TestGameplayProbeContract::test_anonymous_choice_sync_without_current_event_returns_validation_status`

## 验证
- `python -m pytest tests/test_api_contract.py::TestGameplayProbeContract::test_anonymous_choice_sync_without_current_event_returns_validation_status tests/test_gate_preflight_no_mock.py::test_e2e_api_contract_probe_does_not_trigger_long_story_regeneration -q`
- 结果：2 passed。
