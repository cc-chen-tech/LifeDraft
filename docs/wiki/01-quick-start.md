# 01 - Quick Start

> 最后核对：2026-04-26

## 项目是什么

`story2` 是一个 AI 驱动的人生叙事游戏：

- 后端：FastAPI（`src/api`）+ 游戏核心（`src/game`）+ AI 生成（`src/ai`）+ 数据持久化（`src/database`）
- 前端：Next.js App Router（`frontend/src/app`），通过同域 API 代理访问后端
- 额外服务：网易云音乐 API（`netease-music-api`，可选）

## 本地启动（推荐）

在仓库根目录执行：

```bash
./start.sh
```

常用命令：

```bash
./start.sh stop
./start.sh status
./start.sh tail
```

默认端口：

- 前端：`3000`
- 后端：`8000`
- 音乐服务：`3001`

## 手动启动

后端：

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run_api.py
```

前端：

```bash
cd frontend
npm install
npm run dev
```

## 最小环境变量

复制并编辑：

```bash
cp .env.example .env
```

最小可运行项：

- `OPENAI_API_KEY`
- `OPENAI_MODEL`（默认 `gpt-4`）
- `DEFAULT_LANGUAGE`（默认 `zh`）

## MiniMax 音频功能

如需启用故事朗读后端音频和 AI 音乐生成，至少配置：

- `MINIMAX_API_KEY`
- `STORY_TTS_PROVIDER=minimax`
- `STORY_MUSIC_AI_GENERATION_ENABLED=true`

如果只配置 `MINIMAX_API_KEY` 但没有设置 `STORY_TTS_PROVIDER=minimax`，故事朗读仍会按默认配置走浏览器语音。测试环境可使用 `STORY_TTS_PROVIDER=local` 和 `MINIMAX_E2E_LOCAL_AUDIO=1`，避免调用付费接口。

自动朗读默认关闭。需要让新用户默认在故事完成后自动朗读时，可显式设置 `STORY_TTS_AUTO_READ_DEFAULT_ENABLED=true`；用户在界面里切换后，以用户自己的设置为准。

## 当前代码现状提示

- 根目录存在 `docker-compose.ecs.yml`，但未看到通用 `docker-compose.yml`。  
- 旧文档里提到的 Streamlit 路径（如 `src/ui/streamlit_app.py`）在当前仓库中不存在。  
- 因此建议优先使用 `./start.sh` 作为开发启动入口。
