# 15 - ADR Template

> 最后核对：2026-04-26

ADR（Architecture Decision Record）模板：

```md
# ADR-YYYYMMDD-<short-title>

## 状态
- Proposed | Accepted | Deprecated | Superseded

## 背景
- 当前现状：
- 约束条件：
- 触发问题：

## 决策
- 决策内容：
- 适用范围：
- 不适用范围：

## 备选方案
1. 方案A：优缺点
2. 方案B：优缺点
3. 方案C：优缺点

## 影响
- 正向影响：
- 负向影响：
- 运行成本：
- 维护成本：

## 迁移与回滚
- 迁移步骤：
- 回滚步骤：

## 验证
- 成功标准：
- 测试计划：
- 观察指标：

## 关联
- 相关 PR：
- 相关文档：
```

建议存放位置：

- 架构级 ADR：`docs/wiki/adr/`（建议新增目录）  
- feature 级决策：`docs/superpowers/specs/` 内补“决策记录”节

示例：

- `docs/wiki/adr/ADR-20260419-sse-over-websocket.md`
