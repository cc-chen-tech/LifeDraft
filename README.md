# 人生草稿本 (Life Draft Book)

A text-based life simulation game with AI-generated events, resource management, and decision-making gameplay. 人生草稿本 - 用AI生成事件，管理资源，做出选择，体验不同的人生轨迹。

## Features

- **AI-Generated Events**: Dynamic, personalized life events generated in real-time
- **Resource Management**: Balance energy, mood, knowledge, and wealth
- **Decision-Making**: Make choices that affect your life trajectory
- **Bilingual Support**: Play in Chinese or English
- **Multiple Endings**: Experience different life outcomes based on your choices

## Installation

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set up environment variables:
   Create a `.env` file in the project root with:
   ```bash
   OPENAI_API_KEY=your_openai_api_key_here
   OPENAI_MODEL=gpt-4
   DEFAULT_LANGUAGE=en
   CACHE_EVENTS=true
   ```

## Usage

### Command-Line Interface (Phase 1)
```bash
python run_cli.py
# Or with options:
python run_cli.py --language zh  # Chinese
python run_cli.py --load savegame.json  # Load saved game
```

### Next.js Web Interface

启动后端 API 服务:
```bash
python run_api.py
```

启动前端服务:
```bash
cd frontend
npm install  # 首次运行
npm run dev
```

前端界面将在浏览器中打开 `http://localhost:3000`

或使用一键启动脚本:
```bash
./start.sh  # 启动前后端服务
./start_lan_nextjs.sh  # 局域网访问模式
```

## Gameplay

- Start at age 22 and simulate 8 years (96 weeks) until age 30
- Each week, you'll face 2-3 AI-generated events
- Make decisions that affect your resources (energy, mood, knowledge, wealth)
- Manage relationships with key NPCs
- Experience different endings based on your choices

## Project Structure

```
story2/
├── config/          # Configuration and prompts
├── src/
│   ├── game/       # Core game logic
│   ├── ai/         # AI event generation
│   ├── api/        # FastAPI backend
│   └── database/   # Database models and operations
├── frontend/       # Next.js frontend
├── tests/          # Unit and integration tests
└── data/           # Preset events and cache
```

## Development Phases

- **Phase 1**: Core prototype with CLI
- **Phase 2**: FastAPI backend with database
- **Phase 3**: Next.js frontend with full features

## License

MIT
