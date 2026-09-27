# 10 - Release And Change Checklist

> 最后核对：2026-09-28

## PR 级检查

- [ ] 需求范围与非目标写清楚  
- [ ] 影响模块标注（frontend/api/game/ai/db）  
- [ ] feature flag 策略明确（默认开/关）  
- [ ] 回滚步骤可执行  
- [ ] wiki 已同步更新

## 代码级检查

- [ ] API schema 与实现一致  
- [ ] 前后端路径一致（重点检查 SSE 路径）  
- [ ] 错误码和错误信息可被前端识别  
- [ ] 关键日志保留，避免静默失败  
- [ ] 兼容旧状态快照
- [ ] 无硬编码密钥或 secret fallback（security 契约测试 C-01~C-07）
- [ ] SSE 端点已检查认证要求（如场景图事件）
- [ ] 图片/文件处理无 pickle、无 raw SQL 拼接
- [ ] 用户输入已消毒（prompt injection 防护，如 `sanitize_player_name`）

## 测试级检查

- [ ] `./test.sh contract`
- [ ] `./test.sh db`
- [ ] `./test.sh e2e`（至少关键链路）
- [ ] 受影响模块单测已更新

## 发布门禁与执行

- [ ] PR 当前提交的检查通过，评审问题已处理；合并后确认当前 `main` 的 9 项 CI 全绿
- [ ] 正常发布：受保护 `Model Smoke` 在同一提交上通过，首日 `delivery_mode=model`，图片、TTS、保存及授权读回通过
- [ ] 例外发布（仅适用时）：若 `Model Smoke` 仅因 `daily_opening_used_safe_fallback` 标红，记录模型正文未通过质量验收；只有明确决定提前发布且其他主干检查全绿时，才在 `Deploy Production` 手动工作流使用 `allow_without_model_smoke=true`
- [ ] 部署输入 `candidate_sha` 与当前 `main` 的完整 40 位 SHA 一致；不要直接在 ECS 上运行 Compose
- [ ] `Deploy Production` 的 ECS 作业及 `/health`、`/api/health` 公开检查通过，并核对部署日志中的精确 SHA

正常链路是主干 E2E 完成后触发 Model Smoke，Model Smoke 成功后自动请求生产部署。
入口及例外条件见 [生产部署指南](../../DEPLOYMENT.md)。

## 配置级检查

- [ ] `.env.example` 已同步  
- [ ] 新增环境变量有默认值或兜底  
- [ ] 生产配置（Cookie/CORS/URL）与部署环境一致  
- [ ] 外部依赖（音乐/图像）降级路径可用

## 上线后观察

重点监控 24 小时：

- SSE 连接失败率（含场景图事件 401）  
- 401/403 比例（JWT、SSE auth）  
- 事件生成平均耗时  
- 图片生成失败率（时代一致性约束触发率）  
- 音乐流代理 4xx 比例（缓存池命中率）  
- 成就/结局 API 响应时间
- 首日模型正文交付与安全开场比例（分别看功能可用性和模型质量）
