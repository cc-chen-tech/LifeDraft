.PHONY: check test flow-check state-test all-checks
.PHONY: docker-build docker-up docker-down docker-logs docker-restart
.PHONY: deploy-dev deploy-prod
.PHONY: git-status git-tree git-stats git-clean git-hooks-install

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
	@./scripts/run-with-isolated-test-database.sh "$${TEST_RUN_DIR:-$${TMPDIR:-/tmp}/story2-test-runs/make}/data/pytest" python3 python3 -m pytest tests/ -v

test-cov:
	@echo "Running tests with coverage..."
	@./scripts/run-with-isolated-test-database.sh "$${TEST_RUN_DIR:-$${TMPDIR:-/tmp}/story2-test-runs/make}/data/pytest" python3 python3 -m pytest tests/ -v --cov=src --cov-report=html --cov-report=term
	@echo "Coverage report generated in htmlcov/"

test-fast:
	@echo "Running tests (fail fast)..."
	@./scripts/run-with-isolated-test-database.sh "$${TEST_RUN_DIR:-$${TMPDIR:-/tmp}/story2-test-runs/make}/data/pytest" python3 python3 -m pytest tests/ -v -x

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

# ========== Git 帮助命令 ==========
git-status:
	@echo "Enhanced git status..."
	@./scripts/git_helpers.sh status

git-tree:
	@./scripts/git_helpers.sh tree

git-stats:
	@./scripts/git_helpers.sh stats

git-clean:
	@./scripts/git_helpers.sh clean

# Install git hooks
git-hooks-install:
	@echo "Installing git hooks..."
	@chmod +x .git/hooks/pre-commit .git/hooks/commit-msg
	@echo "✓ Git hooks installed!"

# Create feature branch
git-feature:
	@if [ -z "$(name)" ]; then \
		echo "Usage: make git-feature name=<feature-name>"; \
		exit 1; \
	fi
	@./scripts/git_helpers.sh feature $(name)

# Create fix branch
git-fix:
	@if [ -z "$(name)" ]; then \
		echo "Usage: make git-fix name=<fix-name>"; \
		exit 1; \
	fi
	@./scripts/git_helpers.sh fix $(name)

# Quick commit with conventional format
git-qc:
	@if [ -z "$(type)" ] || [ -z "$(msg)" ]; then \
		echo "Usage: make git-qc type=<type> msg='<message>'"; \
		echo "Types: feat, fix, docs, style, refactor, test, build, ci, chore, perf"; \
		exit 1; \
	fi
	@git commit -m "$(type): $(msg)"
