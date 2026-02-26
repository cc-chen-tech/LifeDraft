.PHONY: check test flow-check state-test all-checks
.PHONY: docker-build docker-up docker-down docker-logs docker-restart
.PHONY: deploy-dev deploy-prod

# ========== 代码质量检查 ==========
flow-check:
	@echo "Running flow checker..."
	@python3 check_flow.py

state-test:
	@echo "Running state machine tests..."
	@python3 test_state_machine.py

all-checks: flow-check state-test
	@echo "\n✓ All checks completed!"

check: all-checks

test:
	@echo "Running tests..."
	@python3 -m pytest tests/ -v

test-cov:
	@echo "Running tests with coverage..."
	@python3 -m pytest tests/ -v --cov=src --cov-report=html --cov-report=term
	@echo "Coverage report generated in htmlcov/"

test-fast:
	@echo "Running tests (fail fast)..."
	@python3 -m pytest tests/ -v -x

format:
	@echo "Formatting code..."
	@python3 -m black src/ --line-length 100
	@python3 -m isort src/

lint:
	@echo "Linting code..."
	@python3 -m flake8 src/ --max-line-length=100 --ignore=E501,W503

type-check:
	@echo "Type checking..."
	@python3 -m mypy src/ --ignore-missing-imports

quality: format lint type-check check
	@echo "\n✓ All quality checks completed!"

# ========== Docker操作 ==========
docker-build:
	@echo "Building Docker image..."
	docker-compose build

docker-up:
	@echo "Starting services..."
	docker-compose up -d

docker-down:
	@echo "Stopping services..."
	docker-compose down

docker-logs:
	@echo "Showing logs..."
	docker-compose logs -f app

docker-restart:
	@echo "Restarting services..."
	docker-compose restart

docker-ps:
	@echo "Service status:"
	docker-compose ps

# ========== 部署操作 ==========
deploy-dev: docker-build docker-up
	@echo "✅ Development environment deployed!"
	@echo "🌐 Access at: http://localhost:8501"

deploy-prod: docker-build
	@echo "Deploying production environment..."
	docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
	@echo "✅ Production environment deployed!"

# ========== 快速命令 ==========
start: docker-up
	@echo "✅ Services started!"

stop: docker-down
	@echo "✅ Services stopped!"

logs: docker-logs

status: docker-ps
