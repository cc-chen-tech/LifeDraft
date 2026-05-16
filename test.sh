#!/bin/bash
# Story2 测试运行脚本 - Preflight + 5 层测试架构
# 用法: ./test.sh [命令]
#
# Preflight: 前置校验       - OpenSpec、前端类型、关键回归夹具漂移
# 5 层测试架构:
#   Layer 1: 静态分析 (mypy)      - 类型不匹配、不存在的属性
#   Layer 2: 导入验证 (imports)   - 所有延迟导入路径可达
#   Layer 3: 契约测试 (contract)  - 生产者/消费者字段名一致
#   Layer 4: DB集成测试 (db)      - 保存→读取链路完整
#   Layer 5: E2E浏览器测试        - 前端进度显示、面板交互 (需 browser-agent)

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# 测试结果跟踪
MYPY_RESULT=0
PREFLIGHT_RESULT=0
IMPORTS_RESULT=0
CONTRACT_RESULT=0
DB_RESULT=0
E2E_RESULT=0

activate_python_env() {
    if [ -f "$PROJECT_DIR/venv/bin/activate" ]; then
        source "$PROJECT_DIR/venv/bin/activate"
    fi
}

# 打印层级标题
print_layer_header() {
    local layer_num=$1
    local layer_name=$2
    local layer_desc=$3
    echo ""
    echo -e "${MAGENTA}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${MAGENTA}║${NC} ${CYAN}Layer $layer_num: $layer_name${NC}"
    echo -e "${MAGENTA}║${NC} ${YELLOW}$layer_desc${NC}"
    echo -e "${MAGENTA}╚════════════════════════════════════════════════════════════╝${NC}"
}

# 打印层级结果
print_layer_result() {
    local layer_name=$1
    local result=$2
    if [ $result -eq 0 ]; then
        echo -e "${GREEN}✓ Layer [$layer_name] 通过${NC}"
    else
        echo -e "${RED}✗ Layer [$layer_name] 失败${NC}"
    fi
}

# Preflight: 前置校验
run_preflight() {
    print_layer_header "0" "前置校验 (preflight)" "OpenSpec、前端类型、关键回归夹具漂移"
    cd "$PROJECT_DIR"
    activate_python_env

    echo -e "${YELLOW}运行 OpenSpec strict 校验...${NC}"
    openspec validate fix-story-continuity-history-media --strict
    local openspec_code=$?
    openspec validate improve-story-music-recommendation-and-premium-ai-queue --strict
    local music_openspec_code=$?
    openspec validate redesign-bottom-bar-and-improve-music-matching --strict
    local redesign_openspec_code=$?

    echo -e "${YELLOW}运行前置 gate 测试...${NC}"
    python -m pytest \
        tests/test_gate_preflight_no_mock.py \
        tests/test_gate_gameplay_behavior_no_mock.py \
        tests/test_gate_contracts_no_mock.py \
        tests/test_music_degradation_no_mock.py \
        -v
    local gate_code=$?

    echo -e "${YELLOW}运行前端 strict typecheck...${NC}"
    cd "$PROJECT_DIR/frontend"
    export PYTHON="$(command -v python)"
    npx tsc --noEmit --strict
    local tsc_code=$?
    cd "$PROJECT_DIR"

    echo -e "${YELLOW}运行前端 preflight Jest 回归测试...${NC}"
    cd "$PROJECT_DIR/frontend"
    npx jest \
        src/__tests__/preflight/storyContinuityPreflight.test.tsx \
        src/__tests__/lib/sse.test.ts \
        src/__tests__/stores/useGameStore.test.ts \
        src/__tests__/hooks/eventUtils.test.ts \
        src/__tests__/components/ChatBar.test.tsx \
        src/__tests__/stores/useMusicStore.musicQueuePolicy.test.ts \
        --runInBand
    local jest_code=$?
    cd "$PROJECT_DIR"

    local result=0
    if [ $openspec_code -ne 0 ] || [ $music_openspec_code -ne 0 ] || [ $redesign_openspec_code -ne 0 ] || [ $gate_code -ne 0 ] || [ $tsc_code -ne 0 ] || [ $jest_code -ne 0 ]; then
        result=1
    fi

    print_layer_result "preflight" $result
    PREFLIGHT_RESULT=$result
    return $result
}

# Layer 1: 静态分析 (mypy)
run_mypy() {
    print_layer_header "1" "静态分析 (mypy)" "类型检查、不存在的属性检测"
    cd "$PROJECT_DIR"
    activate_python_env
    
    echo -e "${YELLOW}运行 mypy 严格静态类型检查...${NC}"
    MYPY_STRICT_TARGETS=(
        src/ai/text_quality.py
        src/services/music_service.py
        src/services/music_playlist_service.py
        src/database/models.py
    )
    python -m mypy "${MYPY_STRICT_TARGETS[@]}" --strict
    local mypy_code=$?

    echo -e "${YELLOW}运行静态 gate 测试...${NC}"
    python -m pytest tests/test_gate_static_no_mock.py -v
    local gate_code=$?

    local result=0
    if [ $mypy_code -ne 0 ] || [ $gate_code -ne 0 ]; then
        result=1
    fi
    
    print_layer_result "mypy" $result
    MYPY_RESULT=$result
    return $result
}

# Layer 2: 导入验证测试
run_imports() {
    print_layer_header "2" "导入验证" "所有延迟导入路径可达"
    cd "$PROJECT_DIR"
    activate_python_env
    
    echo -e "${YELLOW}运行导入验证测试...${NC}"
    python -m pytest tests/test_imports.py tests/test_gate_imports_no_mock.py -v
    local result=$?
    
    print_layer_result "imports" $result
    IMPORTS_RESULT=$result
    return $result
}

# Layer 3: 契约测试
run_contract() {
    print_layer_header "3" "契约测试" "生产者/消费者字段名一致性"
    cd "$PROJECT_DIR"
    activate_python_env
    
    echo -e "${YELLOW}运行 API 契约测试...${NC}"
    python -m pytest \
        tests/test_api_contract.py \
        tests/test_gate_contracts_no_mock.py \
        tests/test_story_music_recommendation_contract.py \
        tests/test_ui_bottom_layout_contract_no_mock.py \
        -v
    local result=$?
    
    print_layer_result "contract" $result
    CONTRACT_RESULT=$result
    return $result
}

# Layer 4: 真实 DB 集成测试
run_db() {
    print_layer_header "4" "真实 DB 集成测试" "保存→读取链路完整性"
    cd "$PROJECT_DIR"
    activate_python_env
    
    echo -e "${YELLOW}初始化真实数据库表结构...${NC}"
    python -c "from src.database.models import init_db; init_db()"
    local init_result=$?
    if [ $init_result -ne 0 ]; then
        print_layer_result "db" $init_result
        DB_RESULT=$init_result
        return $init_result
    fi

    echo -e "${YELLOW}运行真实数据库集成测试...${NC}"
    python -m pytest \
        tests/test_integration_real_db.py \
        tests/test_database.py \
        tests/test_gate_real_db_no_mock.py \
        tests/test_story_music_recommendation_db.py \
        -v
    local result=$?
    
    print_layer_result "db" $result
    DB_RESULT=$result
    return $result
}

# Layer 5: E2E 浏览器测试 (Playwright)
run_e2e_browser() {
    print_layer_header "5" "E2E 浏览器测试" "前端页面渲染、用户交互、前后端联调"
    cd "$PROJECT_DIR"
    activate_python_env
    echo -e "${YELLOW}初始化 E2E 数据库表结构...${NC}"
    python -c "from src.database.models import init_db; init_db()"
    local init_result=$?
    if [ $init_result -ne 0 ]; then
        print_layer_result "e2e" $init_result
        E2E_RESULT=$init_result
        return $init_result
    fi

    cd "$PROJECT_DIR/frontend"
    export PYTHON="$(command -v python)"
    
    # 检查后端是否运行
    if ! lsof -ti:8000 > /dev/null 2>&1; then
        echo -e "${YELLOW}后端未运行，正在启动...${NC}"
        cd "$PROJECT_DIR"
        activate_python_env
        API_RELOAD=false python run_api.py > /tmp/backend_e2e.log 2>&1 &
        BACKEND_PID=$!
        sleep 3
        if ! lsof -ti:8000 > /dev/null 2>&1; then
            echo -e "${RED}后端启动失败，跳过 E2E 测试${NC}"
            E2E_RESULT=1
            return 1
        fi
        echo -e "${GREEN}后端已启动 (PID: $BACKEND_PID)${NC}"
        cd "$PROJECT_DIR/frontend"
    else
        BACKEND_PID=""
        echo -e "${GREEN}后端已在运行${NC}"
    fi
    
    echo -e "${YELLOW}运行完整 Playwright E2E 测试 (chromium)...${NC}"
    npx playwright test --project=core --reporter=list --workers=1
    local core_result=$?

    echo -e "${YELLOW}运行会员 AI 音乐队列补充 E2E 测试...${NC}"
    npx playwright test e2e/music-player.spec.ts \
        --project=ai-heavy \
        --grep "会员 AI 曲目生成后只进入后续队列且不切换当前歌曲" \
        --reporter=list \
        --workers=1 \
        --no-deps
    local music_ai_result=$?

    local result=0
    if [ $core_result -ne 0 ] || [ $music_ai_result -ne 0 ]; then
        result=1
    fi
    
    # 清理：如果是我们启动的后端，关掉它
    if [ -n "$BACKEND_PID" ]; then
        echo -e "${YELLOW}关闭测试用后端 (PID: $BACKEND_PID)...${NC}"
        kill $BACKEND_PID 2>/dev/null
    fi
    
    print_layer_result "e2e" $result
    E2E_RESULT=$result
    return $result
}

# 单元测试 (pytest -m unit)
run_unit() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${YELLOW}运行单元测试 (pytest -m unit)...${NC}"
    echo -e "${BLUE}========================================${NC}"
    cd "$PROJECT_DIR"
    activate_python_env
    
    python -m pytest tests/ -m unit -v
    local result=$?
    
    if [ $result -eq 0 ]; then
        echo -e "${GREEN}✓ 单元测试通过${NC}"
    else
        echo -e "${RED}✗ 单元测试失败${NC}"
    fi
    return $result
}

# 集成测试 (pytest -m integration)
run_integration() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${YELLOW}运行集成测试 (pytest -m integration)...${NC}"
    echo -e "${BLUE}========================================${NC}"
    cd "$PROJECT_DIR"
    activate_python_env
    
    python -m pytest tests/ -m integration -v
    local result=$?
    
    if [ $result -eq 0 ]; then
        echo -e "${GREEN}✓ 集成测试通过${NC}"
    else
        echo -e "${RED}✗ 集成测试失败${NC}"
    fi
    return $result
}

# API 测试 (pytest -m api)
run_api() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${YELLOW}运行 API 测试 (pytest -m api)...${NC}"
    echo -e "${BLUE}========================================${NC}"
    cd "$PROJECT_DIR"
    activate_python_env
    
    python -m pytest tests/ -m api -v
    local result=$?
    
    if [ $result -eq 0 ]; then
        echo -e "${GREEN}✓ API 测试通过${NC}"
    else
        echo -e "${RED}✗ API 测试失败${NC}"
    fi
    return $result
}

# 前端测试 (tsc + Jest)
run_frontend() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${YELLOW}运行前端测试 (TypeScript + Jest)...${NC}"
    echo -e "${BLUE}========================================${NC}"
    cd "$PROJECT_DIR/frontend"
    
    # TypeScript 类型检查
    echo -e "${YELLOW}--- TypeScript 类型检查 ---${NC}"
    npx tsc --noEmit
    local tsc_result=$?
    
    if [ $tsc_result -eq 0 ]; then
        echo -e "${GREEN}✓ TypeScript 类型检查通过${NC}"
    else
        echo -e "${RED}✗ TypeScript 类型检查失败${NC}"
    fi
    
    # Jest 单元测试
    echo ""
    echo -e "${YELLOW}--- Jest 单元测试 ---${NC}"
    npm test -- --passWithNoTests
    local jest_result=$?
    
    if [ $jest_result -eq 0 ]; then
        echo -e "${GREEN}✓ Jest 测试通过${NC}"
    else
        echo -e "${RED}✗ Jest 测试失败${NC}"
    fi
    
    local result=0
    [ $tsc_result -ne 0 ] || [ $jest_result -ne 0 ] && result=1
    
    return $result
}

# 后端全量测试
run_backend() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${YELLOW}运行后端 Python 测试...${NC}"
    echo -e "${BLUE}========================================${NC}"
    cd "$PROJECT_DIR"
    activate_python_env
    pytest tests/ -v --tb=short
    local result=$?
    if [ $result -eq 0 ]; then
        echo -e "${GREEN}✓ 后端测试通过${NC}"
    else
        echo -e "${RED}✗ 后端测试失败${NC}"
    fi
    return $result
}

# 覆盖率测试
run_coverage() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${YELLOW}运行测试并生成覆盖率报告...${NC}"
    echo -e "${BLUE}========================================${NC}"
    
    # 后端覆盖率
    echo -e "${YELLOW}--- 后端覆盖率 ---${NC}"
    cd "$PROJECT_DIR"
    activate_python_env
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

# 安全扫描
run_security() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${YELLOW}运行安全扫描 (Bandit)...${NC}"
    echo -e "${BLUE}========================================${NC}"
    cd "$PROJECT_DIR"
    activate_python_env
    bandit -r src -c .bandit
    local result=$?
    if [ $result -eq 0 ]; then
        echo -e "${GREEN}✓ 安全扫描通过${NC}"
    else
        echo -e "${RED}✗ 发现安全问题${NC}"
    fi
    return $result
}

# 性能测试
run_perf() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${YELLOW}运行性能测试 (Locust)...${NC}"
    echo -e "${BLUE}========================================${NC}"
    cd "$PROJECT_DIR"
    activate_python_env
    
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

# 运行所有自动化测试 (Preflight + 5 层)
run_all() {
    echo -e "${MAGENTA}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${MAGENTA}║${NC}           ${CYAN}Story2 测试架构 - 自动化测试${NC}                  ${MAGENTA}║${NC}"
    echo -e "${MAGENTA}║${NC}           ${YELLOW}(Preflight + Layer 1-5 全自动化)${NC}           ${MAGENTA}║${NC}"
    echo -e "${MAGENTA}╚════════════════════════════════════════════════════════════╝${NC}"
    
    local failed=0

    # Preflight: 前置校验
    run_preflight || ((failed++))
    
    # Layer 1: 静态分析
    run_mypy || ((failed++))
    
    # Layer 2: 导入验证
    run_imports || ((failed++))
    
    # Layer 3: 契约测试
    run_contract || ((failed++))
    
    # Layer 4: DB 集成测试
    run_db || ((failed++))
    
    # Layer 5: E2E 浏览器测试
    run_e2e_browser || ((failed++))
    
    # 打印总结
    echo ""
    echo -e "${MAGENTA}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${MAGENTA}║${NC}                     ${CYAN}测试结果汇总${NC}                         ${MAGENTA}║${NC}"
    echo -e "${MAGENTA}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    if [ $PREFLIGHT_RESULT -eq 0 ]; then
        echo -e "  Preflight:          ${GREEN}✓ PASS${NC}"
    else
        echo -e "  Preflight:          ${RED}✗ FAIL${NC}"
    fi
    if [ $MYPY_RESULT -eq 0 ]; then
        echo -e "  Layer 1 - mypy:     ${GREEN}✓ PASS${NC}"
    else
        echo -e "  Layer 1 - mypy:     ${RED}✗ FAIL${NC}"
    fi
    if [ $IMPORTS_RESULT -eq 0 ]; then
        echo -e "  Layer 2 - imports:  ${GREEN}✓ PASS${NC}"
    else
        echo -e "  Layer 2 - imports:  ${RED}✗ FAIL${NC}"
    fi
    if [ $CONTRACT_RESULT -eq 0 ]; then
        echo -e "  Layer 3 - contract: ${GREEN}✓ PASS${NC}"
    else
        echo -e "  Layer 3 - contract: ${RED}✗ FAIL${NC}"
    fi
    if [ $DB_RESULT -eq 0 ]; then
        echo -e "  Layer 4 - db:       ${GREEN}✓ PASS${NC}"
    else
        echo -e "  Layer 4 - db:       ${RED}✗ FAIL${NC}"
    fi
    if [ $E2E_RESULT -eq 0 ]; then
        echo -e "  Layer 5 - e2e:      ${GREEN}✓ PASS${NC}"
    else
        echo -e "  Layer 5 - e2e:      ${RED}✗ FAIL${NC}"
    fi
    echo ""
    
    if [ $failed -eq 0 ]; then
        echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
        echo -e "${GREEN}✓ 所有测试通过！ (Preflight + 5/5 layers)${NC}"
        echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
    else
        echo -e "${RED}══════════════════════════════════════════════════════════════${NC}"
        echo -e "${RED}✗ $failed 个测试层失败${NC}"
        echo -e "${RED}══════════════════════════════════════════════════════════════${NC}"
    fi
    
    return $failed
}

# 显示帮助
show_help() {
    echo -e "${CYAN}Story2 测试运行脚本 - Preflight + 五层测试架构${NC}"
    echo ""
    echo "用法: ./test.sh [命令]"
    echo ""
    echo -e "${YELLOW}五层测试命令:${NC}"
    echo "  preflight     - 前置校验: OpenSpec + 前端类型 + 快速漂移检查"
    echo "  mypy          - Layer 1: 静态分析 (类型检查)"
    echo "  imports       - Layer 2: 导入验证测试"
    echo "  contract      - Layer 3: API 契约测试"
    echo "  db            - Layer 4: 真实 DB 集成测试"
    echo "  e2e           - Layer 5: E2E 浏览器测试 (Playwright)"
    echo ""
    echo -e "${YELLOW}按标记运行:${NC}"
    echo "  unit          - 运行 pytest -m unit"
    echo "  integration   - 运行 pytest -m integration"
    echo "  api           - 运行 pytest -m api"
    echo ""
    echo -e "${YELLOW}其他命令:${NC}"
    echo "  all           - 运行全部测试 (Preflight + Layer 1-5)"
    echo "  backend       - 运行后端全量 pytest 测试"
    echo "  frontend      - 运行前端 tsc + Jest 测试"
    echo "  coverage      - 运行测试并生成覆盖率报告"
    echo "  security      - 运行安全扫描 (Bandit)"
    echo "  perf          - 运行性能测试 (Locust)"
    echo "  help          - 显示此帮助信息"
    echo ""
    echo -e "${YELLOW}示例:${NC}"
    echo "  ./test.sh              # 运行全部测试 (Preflight + Layer 1-5)"
    echo "  ./test.sh all          # 同上"
    echo "  ./test.sh preflight    # 只运行前置校验"
    echo "  ./test.sh mypy         # 只运行 mypy 静态分析"
    echo "  ./test.sh contract     # 只运行契约测试"
    echo "  ./test.sh frontend     # 运行前端 tsc + Jest"
}

# 主逻辑
case "$1" in
    preflight)
        run_preflight
        ;;
    mypy)
        run_mypy
        ;;
    imports)
        run_imports
        ;;
    contract)
        run_contract
        ;;
    db)
        run_db
        ;;
    e2e)
        run_e2e_browser
        ;;
    unit)
        run_unit
        ;;
    integration)
        run_integration
        ;;
    api)
        run_api
        ;;
    frontend)
        run_frontend
        ;;
    backend)
        run_backend
        ;;
    coverage)
        run_coverage
        ;;
    security)
        run_security
        ;;
    perf)
        run_perf
        ;;
    all|"")
        run_all
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}未知命令: $1${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac
