# 18 - Wiki Changelog

## 2026-04-26

- 全量更新所有 wiki 页面”最后核对”日期至 2026-04-26。
- **架构页 (02)**：补充 feature flags（truncation_recovery、reactive_compression、generation_state_tracking）与叙事风格引擎说明。
- **API/Session 页 (03)**：补充 SSE scene events 认证要求、成就/人生回顾 API、`/api/games/{id}/ending`、音乐缓存池接口。
- **开发与测试页 (04)**：补充 security 契约测试系列（C-01~C-06）说明。
- **状态与数据页 (07)**：补充 `GamePlaylist`、`achievements`、`life_reviews`、4D resources、决策历史扩展。
- **排障页 (08)**：新增”SSE 场景图事件 401”、”JWT 签名失败”排障条目；更新音乐播放排障（混合缓存池）。
- **模块索引页 (11)**：补充 `AchievementEngine`、`LifeReviewGenerator`、`EndingEvaluator`、`SettingFeedbackCard`、音乐缓存池、姓名文化匹配等模块落点。
- **术语页 (12)**：补充 4D Resources、Era Validator、AchievementEngine、LifeReview、GamePlaylist、CachedMusicPool、Narrative Style、SettingFeedbackCard 等术语。
- **发布清单页 (10)**：补充 security 检查项（硬编码密钥、SSE auth、pickle/raw SQL）。
- **PR 模板 (14)**：补充 security 测试与验证检查项。
- **README.md**：补充成就/人生回顾/4D资源/叙事风格/音乐缓存池/角色AI反馈等功能列表；更新环境变量说明。
- 同步 `DEPLOYMENT.md`、`ONBOARDING.md`、设计文档日期标注。

## 2026-04-19

- 初始化 `docs/wiki` 主体结构（01-12），覆盖快速上手、架构、API/Session、测试、升级设计、排障、索引、术语。
- 增加执行模板与治理页（13-16）：文档治理、PR 模板、ADR 模板、事故复盘模板。
- 增加按角色阅读路径（17），提升新成员上手效率。
- 增加 ADR 示例：`ADR-20260419-sse-over-websocket`。
- 将 wiki 入口挂到根 `README.md`。
- 全量核对并更新所有 `.md` 文档，补齐”最后核对”标记与过时说明修正（部署、前端 README、会话测试计划等）。

## 维护规则

- 每次影响主链路的 PR，都在本页追加一行记录。  
- 记录格式：`日期 + 变更摘要 + 关联页面/模块`。  
- 不写“计划”，只写已落地变更。
