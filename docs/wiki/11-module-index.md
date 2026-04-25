# 11 - Module Index

> 最后核对：2026-04-26

## Backend

- `src/api/main.py`：FastAPI 应用入口、中间件、路由注册  
- `src/api/routers/`：按领域拆分 API（auth/games/gameplay/images/collection/music）  
- `src/api/services/session_service.py`：会话获取与 DB 自动恢复  
- `src/api/session_store.py`：内存会话、SSE cache、options cache

## Game Core

- `src/game/game_loop.py`：游戏主循环编排器  
- `src/game/round/`：回合生成、选择处理、收尾与插画流程  
- `src/game/state/`：玩家状态结构与相关逻辑（含 4D resources：energy / mood / knowledge / wealth）
- `src/game/achievements/`：成就系统（AchievementEngine）

## AI

- `src/ai/generator.py`：生成器聚合入口  
- `src/ai/story_generator.py`：故事文本生成、约束校验、叙事系统接入、风格自动匹配  
- `src/ai/harness/`：约束系统、验证管线、重试策略（含 era validator、中文规范化）  
- `src/ai/narrative/`：风格、角色弧线、世界呼吸等叙事子系统
- `src/ai/life_review.py`：人生回顾生成器（LifeReviewGenerator）
- `src/ai/ending_evaluator.py`：结局评估器（EndingEvaluator）

## Data Layer

- `src/database/models.py`：ORM 模型与索引  
- `src/database/db.py`：Facade（统一数据库入口）  
- `src/database/*_repository.py`：分职责仓储实现

## Frontend

- `frontend/src/app/`：页面与 API 代理  
- `frontend/src/lib/api.ts`：非流式 API 调用封装  
- `frontend/src/lib/sse.ts`：SSE 解析与流式调用封装  
- `frontend/src/hooks/usePlayGame.ts`：主玩法 hook  
- `frontend/src/hooks/useRegenerateSetting.ts`：角色设置 AI 反馈与再生 hook
- `frontend/src/stores/`：Zustand 状态管理
- `frontend/src/components/SettingFeedbackCard.tsx`：角色创建 AI 反馈卡片
- `frontend/src/components/CompletionScreen.tsx`：角色创建完成页

## Config / Ops

- `config/settings.py`：配置与环境变量读取  
- `config/feature_flags.py`：功能开关（10 个 flag）
- `config/character_prompts.py`：角色/时代生成提示（含姓名文化匹配）
- `start.sh`：本地一键启动  
- `test.sh`：五层测试入口（含 security 契约测试系列）
- `scripts/export_openapi.py`：导出 OpenAPI schema
