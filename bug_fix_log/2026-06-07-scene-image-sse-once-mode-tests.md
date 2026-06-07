# Scene Image SSE 测试卡死修复记录

## 问题
- `tests/test_scene_image_sse_contract.py` 与 `tests/test_scene_image_sse_integration.py` 中直接访问
  `/api/images/scene/events/{game_id}` 时，SSE 路由在本地测试环境会进入长连接等待，导致测试用例挂起。
- 根因是端点默认采用持续推送逻辑（`while True + sleep(15)`），而契约/集成测试只需要“拿到一次事件”即可。

## 复现
1. 本地执行：
   - `pytest -q tests/test_scene_image_sse_contract.py`
   - `pytest -q tests/test_scene_image_sse_integration.py`
2. 两组测试在未改造时容易停在 `client.get("/api/images/scene/events/{game_id}")` 阶段。

## 修复方案
1. 在后端路由 `scene_image_events` 增加可选参数：
   - `once: bool = Query(default=False, description="测试或一次性读取时返回首批事件后直接关闭连接")`
2. 在 SSE 流生成器中，当 `once=true` 时：
   - 发送当前这一轮可见事件；
   - 若有事件则立即结束连接；
   - 若无事件则先发 1 条 heartbeat 后结束连接（避免阻塞）。
3. 将相关测试改为调用一次性读取参数：
   - `...?once=true`
   - 修改文件：
     - `tests/test_scene_image_sse_contract.py`
     - `tests/test_scene_image_sse_integration.py`

## 结果
- 验证命令与结果：
  - `pytest -q tests/test_scene_image_sse_contract.py tests/test_scene_image_sse_integration.py`
    - 结果：`10 passed`
  - `pytest -q tests/test_scene_image_sse_contract.py tests/test_scene_image_sse_integration.py tests/test_security_sse_auth_contract.py`
    - 结果：`10 passed, 2 xpassed`

## 备注
- 默认行为保持不变（`once` 默认为 `False`，不影响前端实时 SSE 场景）。
- 仅针对本地一次性验证与 CI/CI-like 长连接测试环境的可控退出路径做兼容。
