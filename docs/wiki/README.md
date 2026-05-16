# Repo Wiki（story2）

> 最后核对：2026-04-26

这个 wiki 的目标是两件事：

1. 让新同学 10 分钟内看懂仓库主链路。  
2. 让后续升级和新 feature 设计有统一落点，不靠口口相传。

## 推荐阅读顺序

1. [01-Quick Start](./01-quick-start.md)
2. [02-System Architecture](./02-system-architecture.md)
3. [03-API And Session](./03-api-and-session.md)
4. [04-Development And Testing](./04-development-and-testing.md)
5. [05-Upgrade And Feature Design](./05-upgrade-and-feature-design.md)
6. [06-API Call Matrix](./06-api-call-matrix.md)
7. [07-State And Data Ownership](./07-state-and-data-ownership.md)
8. [08-Troubleshooting](./08-troubleshooting.md)
9. [09-Feature Playbooks](./09-feature-playbooks.md)
10. [10-Release And Change Checklist](./10-release-and-change-checklist.md)
11. [11-Module Index](./11-module-index.md)
12. [12-Glossary](./12-glossary.md)
13. [13-Documentation Governance](./13-documentation-governance.md)
14. [14-PR Template](./14-pr-template.md)
15. [15-ADR Template](./15-adr-template.md)
16. [16-Incident Retro Template](./16-incident-retro-template.md)
17. [17-Role-Based Reading Paths](./17-role-based-reading-paths.md)
18. [18-Wiki Changelog](./18-wiki-changelog.md)

## ADR 示例

- [ADR-20260419-sse-over-websocket](./adr/ADR-20260419-sse-over-websocket.md)

## 维护约定

- 改动主链路（前端请求路径、核心路由、状态模型）时，同步更新对应 wiki 页面。  
- 每个新 feature PR，至少在 `05-Upgrade And Feature Design` 里补一条“设计决策”或“风险清单”。
- 文档以“当前代码现状”为准，若与旧 README/历史设计稿冲突，以代码实现为准并在 wiki 标注。
