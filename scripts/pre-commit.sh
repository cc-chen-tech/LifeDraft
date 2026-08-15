#!/bin/bash
# Pre-commit hook for Story2 project
# Runs code quality checks before allowing commits
#
# Setup: ln -s ../../scripts/pre-commit.sh .git/hooks/pre-commit
# Or copy: cp scripts/pre-commit.sh .git/hooks/pre-commit

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PROJECT_DIR="$(git rev-parse --show-toplevel)"
cd "$PROJECT_DIR"

# ========================================
# Virtual Environment Detection
# ========================================
# Try to find a Python interpreter from a virtual environment.
# Priority: $VIRTUAL_ENV > .venv > venv > .env
PYTHON3="python3"
if [[ -n "$VIRTUAL_ENV" && -x "$VIRTUAL_ENV/bin/python3" ]]; then
    PYTHON3="$VIRTUAL_ENV/bin/python3"
elif [[ -x "$PROJECT_DIR/.venv/bin/python3" ]]; then
    PYTHON3="$PROJECT_DIR/.venv/bin/python3"
elif [[ -x "$PROJECT_DIR/venv/bin/python3" ]]; then
    PYTHON3="$PROJECT_DIR/venv/bin/python3"
elif [[ -x "$PROJECT_DIR/.env/bin/python3" ]]; then
    PYTHON3="$PROJECT_DIR/.env/bin/python3"
fi

PRECOMMIT_TEST_RUN_DIR="${TEST_RUN_DIR:-${TMPDIR:-/tmp}/story2-test-runs/pre-commit}"

run_isolated_pytest() {
    "$PROJECT_DIR/scripts/run-with-isolated-test-database.sh" \
        "$PRECOMMIT_TEST_RUN_DIR/data/pytest" \
        "$PYTHON3" \
        "$PYTHON3" -m pytest "$@"
}

echo -e "${BLUE}========================================${NC}"
echo -e "${YELLOW}Running pre-commit checks...${NC}"
echo -e "${BLUE}========================================${NC}"

# Get list of staged Python files
STAGED_PY_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$' || true)
STAGED_JS_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\.(js|jsx|ts|tsx)$' || true)

# Skip checks if only non-code files changed
if [[ -z "$STAGED_PY_FILES" && -z "$STAGED_JS_FILES" ]]; then
    echo -e "${GREEN}✓ No code files to check${NC}"
    exit 0
fi

ERRORS=0

# ========================================
# Python Checks
# ========================================
if [[ -n "$STAGED_PY_FILES" ]]; then
    echo ""
    echo -e "${YELLOW}--- Python Code Quality ---${NC}"

    # Format check with black (check only, don't modify)
    echo -e "${BLUE}Checking code formatting (black)...${NC}"
    if $PYTHON3 -m black --check --line-length 100 $STAGED_PY_FILES 2>/dev/null; then
        echo -e "${GREEN}✓ Code formatting OK${NC}"
    else
        echo -e "${YELLOW}⚠ Code formatting issues found. Run 'make format' to fix.${NC}"
        # Don't fail on format issues, just warn
    fi

    # Import sorting check with isort
    echo -e "${BLUE}Checking import order (isort)...${NC}"
    if $PYTHON3 -m isort --check-only $STAGED_PY_FILES 2>/dev/null; then
        echo -e "${GREEN}✓ Import order OK${NC}"
    else
        echo -e "${YELLOW}⚠ Import order issues found. Run 'make format' to fix.${NC}"
    fi

    # Lint with flake8
    echo -e "${BLUE}Running linter (flake8)...${NC}"
    if $PYTHON3 -m flake8 $STAGED_PY_FILES --max-line-length=100 --ignore=E501,W503,E203,E402,E712,E741,W293,F541,F841; then
        echo -e "${GREEN}✓ Linting passed${NC}"
    else
        echo -e "${RED}✗ Linting failed${NC}"
        ERRORS=$((ERRORS + 1))
    fi

    # Check for common security issues (quick check)
    echo -e "${BLUE}Quick security scan...${NC}"
    if command -v bandit &> /dev/null; then
        if bandit -r $STAGED_PY_FILES -q --skip B101,B601 2>/dev/null; then
            echo -e "${GREEN}✓ No obvious security issues${NC}"
        else
            echo -e "${YELLOW}⚠ Some security warnings (check details with 'make security')${NC}"
        fi
    fi
fi

# ========================================
# JavaScript/TypeScript Checks
# ========================================
if [[ -n "$STAGED_JS_FILES" ]]; then
    echo ""
    echo -e "${YELLOW}--- JavaScript/TypeScript Code Quality ---${NC}"

    cd "$PROJECT_DIR/frontend"

    # Check if node_modules exists
    if [[ -d "node_modules" ]]; then
        # ESLint check
        echo -e "${BLUE}Running ESLint...${NC}"
        if npx eslint $STAGED_JS_FILES --quiet 2>/dev/null; then
            echo -e "${GREEN}✓ ESLint passed${NC}"
        else
            echo -e "${YELLOW}⚠ ESLint warnings found${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ node_modules not found, skipping JS checks${NC}"
    fi

    cd "$PROJECT_DIR"
fi

# ========================================
# Frontend Unit Tests (Jest)
# ========================================
if [[ -n "$STAGED_JS_FILES" ]]; then
    echo ""
    echo -e "${YELLOW}--- Frontend Unit Tests ---${NC}"

    cd "$PROJECT_DIR/frontend"

    # Check if node_modules exists
    if [[ -d "node_modules" ]]; then
        # Run Jest tests
        echo -e "${BLUE}Running Jest unit tests...${NC}"
        if npm test -- --watchAll=false --passWithNoTests 2>/dev/null; then
            echo -e "${GREEN}✓ Unit tests passed${NC}"
        else
            echo -e "${RED}✗ Unit tests failed${NC}"
            ERRORS=$((ERRORS + 1))
        fi
    else
        echo -e "${YELLOW}⚠ node_modules not found, skipping unit tests${NC}"
    fi

    cd "$PROJECT_DIR"
fi

# ========================================
# Coverage Check (opt-in — full suite is slow)
# ========================================
if [[ -n "$STAGED_PY_FILES" ]] && [[ "$RUN_COVERAGE_ON_COMMIT" == "true" ]]; then
    echo ""
    echo -e "${YELLOW}--- Coverage Check ---${NC}"

    # Read threshold from config file or use default (70%)
    COVERAGE_THRESHOLD=70
    if [[ -f "$PROJECT_DIR/.coverage-threshold" ]]; then
        COVERAGE_THRESHOLD=$(cat "$PROJECT_DIR/.coverage-threshold" | tr -d '[:space:]')
        if ! [[ "$COVERAGE_THRESHOLD" =~ ^[0-9]+$ ]]; then
            COVERAGE_THRESHOLD=70
        fi
    fi

    if $PYTHON3 -m pytest --version 2>/dev/null | grep -q "pytest"; then
        if $PYTHON3 -c "import pytest_cov" 2>/dev/null; then
            echo -e "${BLUE}Running coverage check (threshold: ${COVERAGE_THRESHOLD}%)...${NC}"

            # Run pytest with coverage on ALL tests to get project-wide coverage.
            # Note: this runs the full test suite and can take 2+ minutes.
            COVERAGE_OUTPUT=$(run_isolated_pytest --cov=src --cov-report=term-missing -q 2>&1)
            PYTEST_EXIT=$?

            # Extract TOTAL coverage percentage (works even if tests fail)
            COVERAGE_PERCENT=$(echo "$COVERAGE_OUTPUT" | grep -E '^TOTAL\s+' | grep -oE '[0-9]+%' | head -1 | tr -d '%')

            # Fallbacks
            if [[ -z "$COVERAGE_PERCENT" ]]; then
                COVERAGE_PERCENT=$(echo "$COVERAGE_OUTPUT" | grep -oE '[0-9]+%' | tail -1 | tr -d '%')
            fi
            if [[ -z "$COVERAGE_PERCENT" ]]; then
                COVERAGE_PERCENT=$(echo "$COVERAGE_OUTPUT" | grep -oE 'Total coverage: [0-9]+\.[0-9]+%' | grep -oE '[0-9]+' | head -1 | tr -d '%')
            fi

            if [[ -n "$COVERAGE_PERCENT" ]]; then
                if [[ "$COVERAGE_PERCENT" -lt "$COVERAGE_THRESHOLD" ]]; then
                    echo -e "${YELLOW}⚠ Coverage is ${COVERAGE_PERCENT}% (below threshold of ${COVERAGE_THRESHOLD}%)${NC}"
                else
                    echo -e "${GREEN}✓ Coverage is ${COVERAGE_PERCENT}% (meets threshold of ${COVERAGE_THRESHOLD}%)${NC}"
                fi
            else
                echo -e "${YELLOW}⚠ Could not determine coverage percentage${NC}"
            fi

            # Also report test failures if any (separate from coverage)
            if [[ $PYTEST_EXIT -ne 0 ]]; then
                echo -e "${YELLOW}⚠ Tests had failures (exit $PYTEST_EXIT); coverage data may be partial${NC}"
            fi
        else
            echo -e "${YELLOW}⚠ pytest-cov not installed, skipping coverage check${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ pytest not available, skipping coverage check${NC}"
    fi
fi

# ========================================
# Tests for staged files
# ========================================
if [[ -n "$STAGED_PY_FILES" ]] && [[ "$RUN_TESTS_ON_COMMIT" == "true" ]]; then
    echo ""
    echo -e "${YELLOW}--- Running Quick Tests ---${NC}"
    if run_isolated_pytest tests/ -v -x --tb=short -q 2>/dev/null; then
        echo -e "${GREEN}✓ Tests passed${NC}"
    else
        echo -e "${RED}✗ Tests failed${NC}"
        ERRORS=$((ERRORS + 1))
    fi
fi

# ========================================
# Summary
# ========================================
echo ""
echo -e "${BLUE}========================================${NC}"
if [[ $ERRORS -eq 0 ]]; then
    echo -e "${GREEN}✓ Pre-commit checks passed!${NC}"
    echo -e "${BLUE}========================================${NC}"
    exit 0
else
    echo -e "${RED}✗ Pre-commit checks failed with $ERRORS error(s)${NC}"
    echo -e "${YELLOW}Fix the issues above and try again.${NC}"
    echo -e "${BLUE}========================================${NC}"
    exit 1
fi
