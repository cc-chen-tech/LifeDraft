# 05 - Upgrade And Feature Design

> 最后核对：2026-04-19

## 目标

把“想法”变成“可落地、可回滚、可验证”的变更，避免只改功能不改系统。

## Feature 设计模板（建议复制到 PR 描述）

```md
## 背景
- 业务问题：
- 当前行为：
- 目标行为：

## 影响范围
- 前端：
- API：
- Game/AI：
- DB（模型/索引/迁移）：
- 配置/Feature Flag：

## 兼容与回滚
- 向后兼容策略：
- 灰度开关：
- 回滚步骤：

## 测试计划
- 单元：
- 契约：
- DB集成：
- E2E：
```

## 升级改动分层原则

1. 先改契约，再改实现，再改 UI。  
2. 新能力默认挂 feature flag。  
3. 任何会影响状态机的改动，都要补“中途断线/恢复”测试。  
4. 任何会影响生成链路的改动，都要补“并发 + 超时 + 重试”测试。  
5. 任何 DB 结构变化，都要写迁移脚本与回滚路径。

## 高风险区域（改动前必看）

- SSE 断线恢复与 `Last-Event-ID` 回放逻辑  
- `session_store` 与 `session_service` 的协同  
- `GameLoop.current_event` 与 `player_state.current_event_data` 一致性  
- 选择提交后的自动保存与历史回放  
- 场景插图异步补全流程

## 设计新 Feature 的推荐路径

1. 在 `docs/superpowers/plans/` 写短计划（背景、范围、验收标准）。  
2. 如涉及架构变化，在 `docs/superpowers/specs/` 落详细设计。  
3. 用 feature flag 上线第一版。  
4. 最小闭环验证：`contract + db + e2e` 至少各一条关键路径。  
5. 稳定后再考虑默认开启或移除旧路径。

## PR 合并前检查清单

- [ ] Wiki 对应页面已更新  
- [ ] `.env.example` 与配置说明同步  
- [ ] OpenAPI 与前端类型同步（若涉及 API）  
- [ ] `./test.sh` 相关层级已通过  
- [ ] 回滚方案写明并可执行
