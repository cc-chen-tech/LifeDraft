# 人生草稿本 (Life Draft Book)

A text-based life simulation game with AI-generated events, resource management, and decision-making gameplay.

人生草稿本 - 用 AI 生成事件，管理资源，做出选择，体验不同的人生轨迹。

## Features

- **AI-Generated Events**: Dynamic, personalized life events generated in real-time using GPT-4
- **Resource Management**: Balance energy, mood, knowledge, and wealth
- **Decision-Making**: Make choices that affect your life trajectory
- **Dual Interfaces**: Both Streamlit and Next.js web interfaces
- **Save System**: Save and load your game progress
- **Bilingual Support**: Play in Chinese (default) or English
- **Multiple Endings**: Experience different life outcomes based on your choices

## Tech Stack

- **Backend**: Python 3.9+, FastAPI, SQLAlchemy
- **Frontend**: Next.js 16, React 19, TypeScript, Tailwind CSS 4
- **AI**: OpenAI GPT-4 API
- **Database**: SQLite (default) / PostgreSQL (production)
- **Testing**: pytest, Jest, Playwright (E2E)
- **Deployment**: Docker, Docker Compose

## Quick Start

### Option 1: Using start.sh (Recommended for Development)

```bash
# Start both backend and frontend
./start.sh

# Other commands
./start.sh stop      # Stop all services
./start.sh restart   # Restart services
./start.sh status    # Check service status
./start.sh tail      # View real-time logs
```

### Option 2: Using Docker

```bash
# Build and start with Docker Compose
make deploy-dev

# Or manually:
docker-compose up -d
```

### Option 3: Manual Setup

1. **Clone and setup Python environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Setup environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your OpenAI API key
   ```

3. **Start backend**:
   ```bash
   python run_api.py
   ```

4. **Start frontend** (in another terminal):
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

5. **Open** http://localhost:3000

## Environment Variables

Create a `.env` file in the project root:

```bash
# Required
OPENAI_API_KEY=your-openai-api-key-here
OPENAI_MODEL=gpt-4

# Optional
DEFAULT_LANGUAGE=zh        # zh or en
CACHE_EVENTS=true          # Enable event caching
DATABASE_URL=              # PostgreSQL URL (optional, uses SQLite by default)
```

See `.env.example` for all available options.

## Development Commands

### Using Makefile

```bash
make test           # Run all tests
make test-cov       # Run tests with coverage report
make format         # Format code with black and isort
make lint           # Run flake8 linting
make type-check     # Run mypy type checking
make quality        # Run all quality checks

make docker-up      # Start Docker services
make docker-down    # Stop Docker services
make deploy-dev     # Deploy development environment
make deploy-prod    # Deploy production environment
```

### Testing

**Backend tests:**
```bash
pytest tests/ -v
pytest tests/ -v --cov=src --cov-report=html
```

**Frontend tests:**
```bash
cd frontend
npm test              # Unit tests with Jest
npm run test:e2e      # E2E tests with Playwright
```

## Project Structure

```
story2/
├── src/
│   ├── game/         # Core game logic and state management
│   ├── ai/           # AI event generation and LLM integration
│   ├── api/          # FastAPI backend
│   ├── ui/           # Streamlit interface
│   └── database/     # Database models and operations
├── frontend/         # Next.js frontend application
├── tests/            # Backend tests
├── config/           # Configuration and AI prompts
├── data/             # Game data, presets, and cache
├── docker-compose.yml
├── Dockerfile
├── Makefile          # Development commands
├── start.sh          # Quick start script
└── DEPLOYMENT.md     # Detailed deployment guide
```

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment options:

- **Streamlit Cloud** - Easiest, free tier available
- **Docker Deployment** - Recommended for VPS/cloud servers
- **Full Production Setup** - With Nginx, SSL, monitoring

Quick Docker deployment:
```bash
# Development
make deploy-dev

# Production
make deploy-prod
```

## Gameplay

- Start at age 22 and simulate until age 30 (96 weeks)
- Each week, face 2-3 AI-generated events based on your current situation
- Make decisions that affect your resources (energy, mood, knowledge, wealth)
- Build relationships with NPCs
- Experience different endings based on your life choices

## License

MIT
