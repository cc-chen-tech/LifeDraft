#!/bin/bash
# Story2 测试运行脚本
# 用法: ./test.sh [命令]
#   无参数/backend - 运行后端测试
#   frontend       - 运行前端单元测试
#   e2e            - 运行 E2E 测试
#   coverage       - 运行测试并生成覆盖率报告
#   perf           - 运行性能测试
#   security       - 运行安全扫描
#   all            - 运行所有测试

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 后端测试
run_backend_tests() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${YELLOW}运行后端 Python 测试...${NC}"
    echo -e "${BLUE}========================================${NC}"
    cd "$PROJECT_DIR"
    source venv/bin/activate
    pytest tests/ -v --tb=short
    local result=$?
    if [ $result -eq 0 ]; then
        echo -e "${GREEN}✓ 后端测试通过${NC}"
    else
        echo -e "${RED}✗ 后端测试失败${NC}"
    fi
    return $result
}

# 前端单元测试
run_frontend_tests() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${YELLOW}运行前端 Jest 单元测试...${NC}"
    echo -e "${BLUE}========================================${NC}"
    cd "$PROJECT_DIR/frontend"
    npm test -- --passWithNoTests
    local result=$?
    if [ $result -eq 0 ]; then
        echo -e "${GREEN}✓ 前端测试通过${NC}"
    else
        echo -e "${RED}✗ 前端测试失败${NC}"
    fi
    return $result
}

# E2E 测试
run_e2e_tests() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${YELLOW}运行 E2E Playwright 测试...${NC}"
    echo -e "${BLUE}========================================${NC}"

    # 检查后端是否运行，如果没有则启动
    local backend_started=false
    if ! lsof -ti:8000 > /dev/null 2>&1; then
        echo -e "${YELLOW}后端未运行，正在启动...${NC}"
        cd "$PROJECT_DIR"
        source venv/bin/activate
        python -m src.main > /tmp/backend_e2e.log 2>&1 &
        local backend_pid=$!
        backend_started=true

        # 等待后端启动
        echo -e "${YELLOW}等待后端启动...${NC}"
        for i in {1..30}; do
            if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
                echo -e "${GREEN}后端已启动${NC}"
                # 额外等待确保所有路由完全初始化
                sleep 2
                break
            fi
            sleep 1
        done
    fi

    cd "$PROJECT_DIR/frontend"

    # 检查是否需要安装浏览器
    if [ ! -d "$HOME/Library/Caches/ms-playwright/chromium-"* ]; then
        echo -e "${YELLOW}首次运行，安装 Playwright 浏览器...${NC}"
        npx playwright install chromium
    fi

    npx playwright test --project=chromium
    local result=$?
    if [ $result -eq 0 ]; then
        echo -e "${GREEN}✓ E2E 测试通过${NC}"
    else
        echo -e "${RED}✗ E2E 测试失败${NC}"
    fi

    # 如果测试期间启动了后端，则关闭它
    if [ "$backend_started" = true ]; then
        echo -e "${YELLOW}关闭测试期间启动的后端...${NC}"
        kill $backend_pid 2>/dev/null || true
    fi

    return $result
}

# 覆盖率测试
run_coverage_tests() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${YELLOW}运行测试并生成覆盖率报告...${NC}"
    echo -e "${BLUE}========================================${NC}"
    
    # 后端覆盖率
    echo -e "${YELLOW}--- 后端覆盖率 ---${NC}"
    cd "$PROJECT_DIR"
    source venv/bin/activate
    pytest tests/ --cov=src --cov-report=term-missing --cov-report=html:htmlcov/backend
    
    # 前端覆盖率
    echo ""
    echo -e "${YELLOW}--- 前端覆盖率 ---${NC}"
    cd "$PROJECT_DIR/frontend"
    npm test -- --coverage --coverageReporters=text --coverageReporters=html
    
    echo ""
    echo -e "${GREEN}覆盖率报告已生成:${NC}"
    echo "  后端: $PROJECT_DIR/htmlcov/backend/index.html"
    echo "  前端: $PROJECT_DIR/frontend/coverage/lcov-report/index.html"
}

# 性能测试
run_perf_tests() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${YELLOW}运行性能测试 (Locust)...${NC}"
    echo -e "${BLUE}========================================${NC}"
    cd "$PROJECT_DIR"
    source venv/bin/activate
    
    # 检查后端是否运行
    if ! lsof -ti:8000 > /dev/null 2>&1; then
        echo -e "${YELLOW}后端未运行，正在启动...${NC}"
        python run_api.py > /tmp/backend_test.log 2>&1 &
        sleep 3
    fi
    
    echo -e "${YELLOW}启动 Locust 性能测试...${NC}"
    echo -e "${YELLOW}访问 http://localhost:8089 进行测试配置${NC}"
    cd tests/performance
    locust -f locustfile.py --host=http://localhost:8000
}

# 安全扫描
run_security_tests() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${YELLOW}运行安全扫描 (Bandit)...${NC}"
    echo -e "${BLUE}========================================${NC}"
    cd "$PROJECT_DIR"
    source venv/bin/activate
    bandit -r src -c .bandit
    local result=$?
    if [ $result -eq 0 ]; then
        echo -e "${GREEN}✓ 安全扫描通过${NC}"
    else
        echo -e "${RED}✗ 发现安全问题${NC}"
    fi
    return $result
}

# 运行所有测试
run_all_tests() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${YELLOW}运行所有测试...${NC}"
    echo -e "${BLUE}========================================${NC}"
    
    local failed=0
    
    # 后端测试
    run_backend_tests || ((failed++))
    echo ""
    
    # 前端测试
    run_frontend_tests || ((failed++))
    echo ""
    
    # E2E 测试
    run_e2e_tests || ((failed++))
    echo ""
    
    # 安全扫描
    run_security_tests || ((failed++))
    echo ""
    
    # 总结
    echo -e "${BLUE}========================================${NC}"
    echo -e "${YELLOW}测试总结${NC}"
    echo -e "${BLUE}========================================${NC}"
    if [ $failed -eq 0 ]; then
        echo -e "${GREEN}✓ 所有测试通过！${NC}"
    else
        echo -e "${RED}✗ $failed 个测试套件失败${NC}"
    fi
    
    return $failed
}

# 显示帮助
show_help() {
    echo "Story2 测试运行脚本"
    echo ""
    echo "用法: ./test.sh [命令]"
    echo ""
    echo "命令:"
    echo "  无参数/backend  - 运行后端 Python 测试"
    echo "  frontend        - 运行前端 Jest 单元测试"
    echo "  e2e             - 运行 E2E Playwright 测试"
    echo "  coverage        - 运行测试并生成覆盖率报告"
    echo "  perf            - 运行性能测试 (Locust)"
    echo "  security        - 运行安全扫描 (Bandit)"
    echo "  all             - 运行所有测试"
    echo "  help            - 显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  ./test.sh              # 运行后端测试"
    echo "  ./test.sh frontend     # 运行前端测试"
    echo "  ./test.sh e2e          # 运行 E2E 测试"
    echo "  ./test.sh all          # 运行所有测试"
}

# 主逻辑
case "$1" in
    frontend)
        run_frontend_tests
        ;;
    e2e)
        run_e2e_tests
        ;;
    coverage)
        run_coverage_tests
        ;;
    perf)
        run_perf_tests
        ;;
    security)
        run_security_tests
        ;;
    all)
        run_all_tests
        ;;
    help|--help|-h)
        show_help
        ;;
    backend|"")
        run_backend_tests
        ;;
    *)
        echo -e "${RED}未知命令: $1${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac
