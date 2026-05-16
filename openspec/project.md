# LifeDraft（人生草稿本）

AI 驱动的叙事人生模拟游戏。多轮事件生成、选择驱动的剧情推进、关系与世界演化，体验不同的人生轨迹。

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.9+, FastAPI, SQLAlchemy 2.0, Pydantic 2.0 |
| Frontend | Next.js 16 (App Router), React 19, Zustand 5, Tailwind CSS 4, Radix UI |
| AI/LLM | OpenAI SDK (兼容 DeepSeek 等), 图像生成 API |
| Database | SQLite (本地) / PostgreSQL (生产) |
| Auth | JWT (Cookie + Bearer fallback) |
| Testing | pytest, Jest, Playwright, mypy, tsc |
| Infra | Docker Compose, Nginx, ECS |

## Architecture

```
frontend (Next.js) → /api/[...path] proxy → FastAPI routers
  → GameLoop (session + state) → AI generators → LLM API
  → Services (image, music, collection) → DB repositories
```

- **API Layer** (`src/api/`): FastAPI app, JWT auth, SSE streaming, session management
- **Game Core** (`src/game/`): GameLoop 中央协调器, PlayerState 子模块, 回合处理, 成就/结局系统
- **AI Layer** (`src/ai/`): LLM 客户端, 事件/故事/选项生成器, 约束验证流水线, 叙事风格引擎
- **Services** (`src/services/`): 图像生成/存储, 音乐推荐/流代理, 实体提取, 收藏管理
- **Database** (`src/database/`): SQLAlchemy ORM (10 张表), Repository 模式, 自动索引

## Key Patterns

- **SSE Streaming**: 游戏事件通过 Server-Sent Events 流式推送, Last-Event-ID 重连
- **Session Auto-Recovery**: 内存会话过期后从 DB 自动恢复
- **State as JSON Snapshots**: GameState 以 JSON 存储完整玩家状态
- **Save Point System**: 手动存档 + 自动快照, 支持时间线回溯
- **No Mocks**: 测试优先使用真实 DB/契约测试
- **Feature Flags**: 实验性功能通过 `ENABLE_*` 环境变量控制 (`config/feature_flags.py`)
- **Quality Levels**: 三级生成质量 (fast/expert/master)
- **API Type Contract**: 后端 OpenAPI schema → 前端 openapi-typescript 自动生成类型

## Testing (5 层)

1. Static Analysis — mypy (Python) / tsc --noEmit (TypeScript)
2. Import Verification — pytest 懒加载路径可达性
3. Contract Tests — producer/consumer 字段名一致性
4. DB Integration — pytest + 真实 DB 读写流水线
5. E2E Browser — Playwright 全浏览器交互

全部通过 `./test.sh` 编排。

## Development Workflow

- Git worktrees 隔离功能开发
- Pre-commit hooks: Black, isort, flake8, ESLint, Jest
- TDD 优先 (先写测试再写实现)
- Claude Code + superpowers 技能链
