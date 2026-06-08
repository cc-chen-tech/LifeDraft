# 匿名创建游戏被 AI Key 阻断

- 日期：2026-06-07
- 影响：本地/CI contract 环境没有 `OPENAI_API_KEY` 时，`POST /api/games` 会在 game 已写入数据库后返回 400，导致后续 `choice-sync` 轻量合同无法验证。

## 复现

运行：

```bash
python -m pytest tests/test_api_contract.py::TestGameplayProbeContract::test_anonymous_choice_sync_without_current_event_returns_validation_status -q
```

修复前结果：创建 game 的响应为 400，响应体为 `{"detail":"OpenAI API key is required"}`。

## 原因

`GameInitializer` 会先创建数据库 game，然后构造 `GameLoop`。`GameLoop.__init__` 会立即构造 `EventGenerator`，再立即构造 `AIClient`。`AIClient.__init__` 在没有 `OPENAI_API_KEY` 时直接抛 `ValueError`，让一个只需要创建/恢复状态的 API 路径错误依赖了实时 AI 凭证。

## 修复

- `AIClient` 无 key 时允许构造，但记录为不可用。
- 真正发起模型调用时通过 `require_openai_client()` 抛出清晰的 `OpenAI API key is required`。
- `EventGenerator` 的直接流式入口也改为通过同一个 guard 获取 OpenAI client。
- 增加低层合同测试，防止以后再次把状态路径绑死到 AI 凭证。

## 验证

```bash
python -m pytest tests/test_ai_client_missing_key_contract.py -q
python -m pytest tests/test_api_contract.py::TestGameplayProbeContract::test_anonymous_choice_sync_without_current_event_returns_validation_status -q
./test.sh contract
```

结果：低层测试 1/1，通过；原复现合同 1/1，通过；contract 68/68，通过。
