# Agent Collaboration Strategy

## 角色分工

- **Architect** (`superpowers:writing-plans`): 多步骤任务的方案设计, 输出到 plan 文件
- **Implementer** (`superpowers:executing-plans`, `superpowers:subagent-driven-development`): 按 plan 执行, 独立子任务并行派发
- **Reviewer** (`superpowers:requesting-code-review`): 功能完成后独立审查, 对照 plan 验证
- **Debugger** (`superpowers:systematic-debugging`): 遇到 bug/测试失败时触发, 先诊断再修复

## 工作流

### 新功能开发

1. `superpowers:brainstorming` — 明确需求与设计方向
2. `superpowers:writing-plans` — 输出实现方案 (plan.md)
3. `superpowers:test-driven-development` — 先写测试, 再写实现
4. `superpowers:executing-plans` — 按 plan 逐步实现, 独立任务用 `superpowers:subagent-driven-development` 并行
5. `superpowers:requesting-code-review` — 审查实现是否符合 plan 和规范
6. `superpowers:finishing-a-development-branch` — 合并/PR/清理

### Bug 修复

1. `superpowers:systematic-debugging` — 系统性诊断, 不猜测
2. `superpowers:test-driven-development` — 先写复现测试
3. 修复 → 验证 → 提交

### 代码审查

1. `superpowers:receiving-code-review` — 收到 review 反馈后, 先验证再实现, 不做表面迎合

## 测试原则

- **禁止 Mock**: 测试必须使用真实 DB 或契约测试 (见用户偏好 memory)
- 每个功能/bug fix 必须先写测试 (TDD)
- 修改涉及跨层时, 运行所有 5 层测试 (`./test.sh`)
- `superpowers:verification-before-completion`: 声称完成前必须运行验证命令并确认通过

## 分支与提交

- 使用 `git worktree` 隔离功能开发
- 提交信息: 简洁描述 "why" (英文), 格式 `type: description`
- 不要 amend 已发布的提交
- Pre-commit hooks 必须通过, 不可跳过

## 关键约束

- 不引入安全漏洞 (OWASP top 10)
- 不过度抽象: 三个相似的代码块好过一个过早的抽象
- 不添加不存在的场景的错误处理
- 不写注释解释 "what", 只写注释解释 "why" (当原因不明显时)
- 后端 API 变更必须同步更新前端类型 (`npm run sync:api-types`)
