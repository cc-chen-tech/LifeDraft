# 09 - Feature Playbooks

## Playbook A: 新增一个 Gameplay API

1. 在 `src/api/schemas.py` 定义请求/响应模型。  
2. 在 `src/api/routers/gameplay/*` 添加路由并挂到 `__init__.py`。  
3. 如依赖会话，统一走 `session_service.get_or_restore()`。  
4. 更新 OpenAPI 与前端类型：
   `cd frontend && npm run sync:api-types`  
5. 补测试：contract + integration + 前端调用点。

## Playbook B: 新增一个叙事引擎能力

1. 能力实现放在 `src/ai` 或 `src/ai/narrative`。  
2. 通过 `config/feature_flags.py` 增加开关，默认关闭。  
3. 在 `StoryGenerator` 或 `GameLoop` 按开关接入。  
4. 补最小验证：
   - 关闭 flag 时行为不变
   - 打开 flag 时新能力生效
5. 更新 wiki 的架构页和升级页。

## Playbook C: 新增图片生成策略

1. 优先在 `src/services/image/*` 子服务层实现。  
2. 保持 `ImageService` 作为统一编排入口。  
3. 明确错误分类（服务错误 / 审核错误 / 存储错误）。  
4. 对应路由返回可诊断错误信息（HTTP 状态 + detail）。  
5. 加入 DB/contract 测试，覆盖生成与再生成路径。

## Playbook D: 新增前端页面状态

1. 区分“仅 UI 状态”与“需持久化状态”。  
2. store 变更先看是否会影响会话恢复与刷新后行为。  
3. 涉及 SSE 时，确认 `complete/error/status` 事件都被处理。  
4. 补 hooks + store 单测，必要时补 e2e。

## Playbook E: 新增数据库字段

1. 更新 SQLAlchemy 模型。  
2. 评估是否需要索引（查询路径驱动）。  
3. 保证旧数据可读（默认值/兜底逻辑）。  
4. 增加 repository 测试 + 实际加载测试。  
5. 在 PR 写清回滚策略（字段兼容 or 迁移逆操作）。
