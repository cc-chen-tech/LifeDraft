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
TEST_NAMESPACE="${TEST_NAMESPACE:-$(printf '%s' "$PROJECT_DIR" | tr '/ ' '__' | tr -c 'A-Za-z0-9._-' '_')}"
TEST_RUN_ROOT="${TEST_RUN_ROOT:-${TMPDIR:-/tmp}/story2-test-runs}"
TEST_RUN_DIR="${TEST_RUN_DIR:-$TEST_RUN_ROOT/$TEST_NAMESPACE}"
TEST_LOCK_DIR="$TEST_RUN_ROOT/locks"
E2E_ACTIVE_LOCK_DIR=""

BACKEND_PID_FILE="$TEST_RUN_DIR/backend.pid"
FRONTEND_PID_FILE="$TEST_RUN_DIR/frontend.pid"
BACKEND_LOG="$TEST_RUN_DIR/backend.log"
FRONTEND_LOG="$TEST_RUN_DIR/frontend.log"
PLAYWRIGHT_LOG_DIR="$TEST_RUN_DIR/playwright"
TEST_DATA_DIR="$TEST_RUN_DIR/data"

TEST_E2E_BACKEND_PORT_BASE="${TEST_E2E_BACKEND_PORT_BASE:-18000}"
TEST_E2E_FRONTEND_PORT_BASE="${TEST_E2E_FRONTEND_PORT_BASE:-19000}"
TEST_E2E_PORT_SCAN_RANGE="${TEST_E2E_PORT_SCAN_RANGE:-80}"

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

E2E_DB_PATH="$TEST_DATA_DIR/story2_e2e.sqlite"
E2E_BACKEND_PORT="${E2E_BACKEND_PORT:-}"
E2E_FRONTEND_PORT="${E2E_FRONTEND_PORT:-}"

ensure_test_dirs() {
    mkdir -p "$TEST_RUN_DIR" "$TEST_DATA_DIR" "$PLAYWRIGHT_LOG_DIR" "$TEST_LOCK_DIR"
}

cleanup_pid_file() {
    local pid_file="$1"
    local label="$2"

    if [ -z "$pid_file" ] || [ ! -f "$pid_file" ]; then
        return 0
    fi

    local pid
    pid="$(cat "$pid_file" 2>/dev/null | tr -cd '0-9' | head -n 1 || true)"
    if [ -z "$pid" ]; then
        rm -f "$pid_file"
        return 0
    fi

    if kill -0 "$pid" 2>/dev/null; then
        echo -e "${YELLOW}关闭现有${label}进程 (PID: $pid)...${NC}"
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
    fi

    if kill -0 "$pid" 2>/dev/null; then
        echo -e "${YELLOW}强制关闭${label}进程 (PID: $pid)...${NC}"
        kill -9 "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
    fi
    rm -f "$pid_file"
}

cleanup_e2e_runtimes() {
    cleanup_pid_file "$BACKEND_PID_FILE" "后端"
    cleanup_pid_file "$FRONTEND_PID_FILE" "前端"
}

with_e2e_lock() {
    mkdir -p "$TEST_LOCK_DIR"
    if ! acquire_e2e_lock; then
        E2E_RESULT=1
        return 1
    fi

    trap 'e2e_status=$?; trap - EXIT INT TERM; cleanup_e2e_session; exit "$e2e_status"' EXIT
    trap 'trap - EXIT INT TERM; cleanup_e2e_session; exit 130' INT
    trap 'trap - EXIT INT TERM; cleanup_e2e_session; exit 143' TERM

    "$@"
    local status=$?
    trap - EXIT INT TERM
    cleanup_e2e_session
    return $status
}

read_e2e_lock_owner_value() {
    local owner_file="$1"
    local key="$2"
    if [ ! -f "$owner_file" ]; then
        return 0
    fi
    sed -n "s/^${key}=//p" "$owner_file" | head -n 1
}

acquire_e2e_lock() {
    if [ "${TEST_ALLOW_PARALLEL_E2E:-0}" = "1" ]; then
        echo -e "${RED}TEST_ALLOW_PARALLEL_E2E=1 已禁用：E2E 必须跨 worktree 串行运行。${NC}" >&2
        return 2
    fi

    local lock_dir="$TEST_LOCK_DIR/e2e.lock"
    local owner_file="$lock_dir/owner"
    local attempt=0
    mkdir -p "$TEST_LOCK_DIR"

    while [ "$attempt" -lt 2 ]; do
        if ! mkdir "$lock_dir" 2>/dev/null; then
            E2E_RESULT=1
            local owner_pid
            owner_pid="$(read_e2e_lock_owner_value "$owner_file" "pid")"
            if [ -n "$owner_pid" ] && kill -0 "$owner_pid" 2>/dev/null; then
                echo -e "${RED}另一个 E2E 运行已持有锁，当前运行将退出：${lock_dir}${NC}" >&2
                cat "$owner_file" >&2
                return 1
            fi
            if [ -z "$owner_pid" ] && ! find "$lock_dir" -maxdepth 0 -mmin +1 -print -quit | grep -q .; then
                echo -e "${RED}E2E 锁 owner 正在发布，当前运行将退出：${lock_dir}${NC}" >&2
                return 1
            fi

            local stale_dir="${lock_dir}.stale.$$"
            if mv "$lock_dir" "$stale_dir" 2>/dev/null; then
                echo -e "${YELLOW}回收已失效的 E2E 锁：${lock_dir}${NC}" >&2
                rm -rf "$stale_dir"
                attempt=$((attempt + 1))
                continue
            fi

            echo -e "${RED}E2E 锁状态在检查期间发生变化，请重试：${lock_dir}${NC}" >&2
            return 1
        fi

        local owner_tmp="$lock_dir/owner.$$"
        {
            echo "pid=$$"
            echo "namespace=$TEST_NAMESPACE"
            echo "project=$PROJECT_DIR"
        } > "$owner_tmp"
        mv "$owner_tmp" "$owner_file"
        E2E_ACTIVE_LOCK_DIR="$lock_dir"
        return 0
    done

    echo -e "${RED}无法获取 E2E 锁：${lock_dir}${NC}" >&2
    return 1
}

release_e2e_lock() {
    local lock_dir="$E2E_ACTIVE_LOCK_DIR"
    if [ -z "$lock_dir" ]; then
        return 0
    fi

    local owner_file="$lock_dir/owner"
    local owner_pid
    owner_pid="$(read_e2e_lock_owner_value "$owner_file" "pid")"
    if [ "$owner_pid" = "$$" ]; then
        rm -f "$owner_file"
        rmdir "$lock_dir" 2>/dev/null || true
    else
        echo -e "${YELLOW}E2E 锁所有者已变化，保留当前锁：${lock_dir}${NC}" >&2
    fi
    E2E_ACTIVE_LOCK_DIR=""
}

cleanup_e2e_session() {
    cleanup_e2e_runtimes
    release_e2e_lock
}

is_port_listening() {
    lsof -tiTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

port_of_namespace_seed() {
    local base="$1"
    local ns_hash
    ns_hash="$(printf '%s' "$TEST_NAMESPACE" | cksum | awk '{print $1}' 2>/dev/null)"
    if [ -z "$ns_hash" ]; then
        ns_hash="$(printf '%s' "$PROJECT_DIR" | wc -c | tr -dc '0-9')"
    fi
    echo $((base + (ns_hash % 90)))
}

find_free_port() {
    local preferred="$1"
    local base="$2"
    local range="${3:-80}"

    if [ -n "$preferred" ] && [ "$preferred" -gt 0 ]; then
        if is_port_listening "$preferred"; then
            >&2 echo -e "${RED}端口 $preferred 已被占用。请先释放该端口或设置 E2E_BACKEND_PORT / E2E_FRONTEND_PORT。${NC}"
            return 1
        fi
        echo "$preferred"
        return 0
    fi

    local candidate=$base
    local idx
    for idx in $(seq 0 "$range"); do
        if ! is_port_listening "$candidate"; then
            echo "$candidate"
            return 0
        fi
        candidate=$((candidate + 1))
    done

    >&2 echo -e "${RED}无法分配空闲端口（$base-$((base + range))）${NC}"
    return 1
}

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

run_playwright_command() {
    local label=$1
    shift
    local output_file
    rm -f "$PLAYWRIGHT_LOG_DIR/story2-playwright-${label}-"*.log 2>/dev/null || true
    output_file="${PLAYWRIGHT_LOG_DIR}/story2-playwright-${label}-$(date +%Y%m%d_%H%M%S)-${RANDOM}.log"

    "$@" 2>&1 | tee "$output_file"
    local result=${PIPESTATUS[0]}

    if [ $result -ne 0 ]; then
        if rg -E "browserType\.launch: Target page, context or browser has been closed|permission denied|SIGABRT|SIGTRAP|bootstrap_check_in|Target page, context or browser" "$output_file" >/dev/null 2>&1; then
            echo -e "${RED}检测到 Playwright 浏览器启动异常：当前沙箱环境可能阻断 Chromium 启动。${NC}"
            echo -e "${YELLOW}建议在有较高系统权限的终端重跑：${NC}"
            echo -e "${BLUE}  cd ${PROJECT_DIR}/frontend${NC}"
            echo -e "${BLUE}  export E2E_NO_SANDBOX=${E2E_NO_SANDBOX:-0}${NC}"
            echo -e "${BLUE}  cd \"${PROJECT_DIR}\"/frontend && CI=1 E2E_FRONTEND_PORT=\${E2E_FRONTEND_PORT} npx playwright test ...${NC}"
            echo -e "${YELLOW}若为 CI/容器环境，请显式设置 E2E_NO_SANDBOX=0 做对照验证。${NC}"
        fi
    fi

    rm -f "$output_file"
    return $result
}

# Preflight: 前置校验
run_preflight() {
    print_layer_header "0" "前置校验 (preflight)" "OpenSpec、前端类型、关键回归夹具漂移"
    cd "$PROJECT_DIR"
    activate_python_env
    ensure_test_dirs

    echo -e "${YELLOW}运行 OpenSpec strict 校验...${NC}"
    openspec validate --all --strict
    local openspec_code=$?
    openspec validate improve-story-music-recommendation-and-premium-ai-queue --strict
    local music_openspec_code=$?
    openspec validate redesign-bottom-bar-and-improve-music-matching --strict
    local redesign_openspec_code=$?
    openspec validate shift-left-e2e-contract-gates --strict
    local shift_left_openspec_code=$?
    openspec validate add-story-voice-reading --strict
    local story_voice_openspec_code=$?
    openspec validate provider-backed-story-tts --strict
    local story_tts_openspec_code=$?
    openspec validate add-minimax-story-audio-generation --strict
    local minimax_audio_openspec_code=$?

    echo -e "${YELLOW}运行后端 preflight quality 检查...${NC}"
    python -m flake8 src/services/story_voice_reading.py --max-line-length=100 --ignore=E501,W503,E203
    local flake8_code=$?

    echo -e "${YELLOW}运行前置 gate 测试...${NC}"
    python -m pytest \
        tests/test_gate_preflight_no_mock.py \
        tests/test_e2e_runtime_isolation_no_mock.py \
        tests/test_e2e_lock_owner_publication_no_mock.py \
        tests/test_gate_gameplay_behavior_no_mock.py \
        tests/test_gate_contracts_no_mock.py \
        tests/test_continuity_ledger.py \
        tests/test_continuity_ledger_integration.py \
        tests/test_assistant_grounding.py \
        tests/test_wealth_removal_contract.py \
        tests/test_opening_story_contract.py \
        tests/test_character_creation_deep.py::TestCharacterCreatorGenerateSetting::test_generate_era_feedback_still_aligns_with_modern_life_vision \
        tests/test_music_degradation_no_mock.py \
        tests/test_minimax_audio_generation_contract.py \
        tests/test_sse_timeout_contract.py \
        -v
    local gate_code=$?

    echo -e "${YELLOW}运行前端 strict typecheck...${NC}"
    cd "$PROJECT_DIR/frontend"
    export PYTHON="$(command -v python)"
    npx tsc --noEmit --strict
    local tsc_code=$?
    cd "$PROJECT_DIR"

    echo -e "${YELLOW}运行 OpenAPI 类型漂移检查...${NC}"
    local openapi_check_dir="$TEST_RUN_DIR/openapi-check"
    local generated_openapi_schema="$openapi_check_dir/openapi-schema.json"
    local generated_openapi_types="$openapi_check_dir/api-generated.d.ts"
    local generated_input_limits="$openapi_check_dir/input-limits.generated.ts"
    rm -rf "$openapi_check_dir"
    mkdir -p "$openapi_check_dir"
    python scripts/export_openapi.py "$generated_openapi_schema"
    local openapi_export_code=$?
    python scripts/export_input_limits.py "$generated_input_limits"
    local input_limits_export_code=$?
    cd "$PROJECT_DIR/frontend"
    npx openapi-typescript "$generated_openapi_schema" -o "$generated_openapi_types"
    local openapi_ts_code=$?
    cd "$PROJECT_DIR"
    cmp -s "$generated_openapi_schema" frontend/src/types/openapi-schema.json
    local openapi_schema_diff_code=$?
    cmp -s "$generated_openapi_types" frontend/src/types/api-generated.d.ts
    local openapi_types_diff_code=$?
    cmp -s "$generated_input_limits" frontend/src/types/input-limits.generated.ts
    local input_limits_diff_code=$?
    local openapi_diff_code=0
    if [ $openapi_schema_diff_code -ne 0 ] || [ $openapi_types_diff_code -ne 0 ] || [ $input_limits_export_code -ne 0 ] || [ $input_limits_diff_code -ne 0 ]; then
        echo -e "${RED}OpenAPI 生成物与受版本控制的前端类型不一致。${NC}" >&2
        echo -e "${YELLOW}请执行 npm run sync:api-types 后提交生成物。${NC}" >&2
        openapi_diff_code=1
    fi

    echo -e "${YELLOW}运行前端 preflight Jest 回归测试...${NC}"
    cd "$PROJECT_DIR/frontend"
    npx jest \
        src/__tests__/preflight/storyContinuityPreflight.test.tsx \
        src/__tests__/lib/sse.test.ts \
        src/__tests__/lib/sessionRecovery.test.ts \
        src/__tests__/lib/storyTextHash.test.ts \
        src/__tests__/lib/storyVoiceTextHash.test.ts \
        src/__tests__/stores/useGameStore.test.ts \
        src/__tests__/pages/CreatePage.test.tsx \
        src/__tests__/hooks/eventUtils.test.ts \
        src/__tests__/components/StoryVoiceControls.test.tsx \
        src/__tests__/components/CompletedStoryMediaGate.test.tsx \
        src/__tests__/components/StatusBar.test.tsx \
        src/__tests__/components/DialogA11y.test.tsx \
        src/__tests__/components/CompletionScreen.loading.test.tsx \
        src/__tests__/components/SheetA11y.test.tsx \
        src/__tests__/pages/PlayPage.test.tsx \
        src/__tests__/components/game/MusicPlayer.test.tsx \
        src/__tests__/components/MusicPlayer.test.tsx \
        src/__tests__/components/ChatBar.test.tsx \
        src/__tests__/components/GlobalMusicPlayer.escape.test.tsx \
        src/__tests__/stores/useStoryVoiceStore.test.ts \
        src/__tests__/lib/apiRetryPolicy.test.ts \
        src/__tests__/app/api/route.test.ts \
        src/__tests__/components/game/CollectionPanelAutoCollect.test.tsx \
        src/__tests__/stores/useCollectionStore.test.ts \
        src/__tests__/stores/useMusicStore.musicQueuePolicy.test.ts \
        --runInBand
    local jest_code=$?
    cd "$PROJECT_DIR"

    local result=0
    if [ $openspec_code -ne 0 ] || [ $music_openspec_code -ne 0 ] || [ $redesign_openspec_code -ne 0 ] || [ $shift_left_openspec_code -ne 0 ] || [ $story_voice_openspec_code -ne 0 ] || [ $story_tts_openspec_code -ne 0 ] || [ $minimax_audio_openspec_code -ne 0 ] || [ $flake8_code -ne 0 ] || [ $gate_code -ne 0 ] || [ $tsc_code -ne 0 ] || [ $openapi_export_code -ne 0 ] || [ $openapi_ts_code -ne 0 ] || [ $openapi_diff_code -ne 0 ] || [ $jest_code -ne 0 ]; then
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
        src/services/minimax_config.py
        src/services/minimax_story_tts_provider.py
        src/services/minimax_music_generation.py
        src/game/relationship_authority.py
        src/game/assistant_grounding.py
        src/services/story_tts_provider.py
        src/services/story_voice_reading.py
        src/services/story_voice_repository.py
        src/services/entity_recognition_service.py
        src/ai/narrative/style_matcher.py
        src/database/models.py
        src/services/life_summary_grounding.py
        src/ai/generation_budget.py
        src/game/world_fact_safety.py
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
    python -m pytest \
        tests/test_imports.py \
        tests/test_gate_imports_no_mock.py \
        tests/test_audio_regeneration_state_imports_no_mock.py \
        tests/test_life_summary_grounding_imports_no_mock.py \
        tests/test_fast_generation_budget_imports_no_mock.py \
        tests/test_world_fact_safety_imports_no_mock.py \
        tests/test_entity_collection_reliability_imports_no_mock.py \
        tests/test_collection_imports.py \
        -v
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
        tests/test_input_limits_contract.py \
        tests/test_player_name_in_prompts_contract.py \
        tests/test_gate_contracts_no_mock.py \
        tests/test_music_playlist_contract.py \
        tests/test_music_recommend_api_degradation_contract.py \
        tests/test_minimax_audio_generation_contract.py \
        tests/test_minimax_image_generation_contract.py \
        tests/test_character_settings_api_contract.py \
        tests/test_shift_left_e2e_contract_no_mock.py \
        tests/test_story_music_recommendation_contract.py \
        tests/test_preset_cast_authority_contract.py \
        tests/test_story_voice_reading_contract.py \
        tests/test_collection_contract.py \
        tests/test_collection_cache_contract.py \
        tests/test_collection_recognition_current_event.py \
        tests/test_live_gameplay_recovery_collection_contract.py \
        tests/test_ui_bottom_layout_contract_no_mock.py \
        tests/test_audio_regeneration_state_contract_no_mock.py \
        tests/test_life_summary_grounding_no_mock.py \
        tests/test_fast_generation_budget_no_mock.py \
        tests/test_world_fact_safety_contract_no_mock.py \
        tests/test_entity_collection_reliability_no_mock.py \
        tests/test_realistic_style_alignment_no_mock.py \
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
        tests/test_minimax_audio_generation_db.py \
        tests/test_story_music_recommendation_db.py \
        tests/test_story_voice_reading_db.py \
        tests/test_collection_cache_db.py \
        tests/test_audio_regeneration_state_db_no_mock.py \
        tests/test_life_summary_grounding_db_no_mock.py \
        tests/test_fast_generation_budget_db_no_mock.py \
        tests/test_world_fact_safety_db_no_mock.py \
        tests/test_entity_collection_reliability_db_no_mock.py \
        tests/test_realistic_style_alignment_no_mock.py \
        -v
    local result=$?
    
    print_layer_result "db" $result
    DB_RESULT=$result
    return $result
}

# Layer 5: E2E 浏览器测试 (Playwright)
run_e2e_browser() {
    with_e2e_lock run_e2e_browser_impl
}

run_e2e_browser_impl() {
    print_layer_header "5" "E2E 浏览器测试" "前端页面渲染、用户交互、前后端联调"
    ensure_test_dirs
    cleanup_e2e_runtimes

    cd "$PROJECT_DIR"
    activate_python_env
    echo -e "${YELLOW}初始化 E2E 数据库表结构...${NC}"
    E2E_DB_PATH="$TEST_DATA_DIR/story2-e2e.sqlite"
    E2E_BACKEND_PORT="$(
        find_free_port "$E2E_BACKEND_PORT" "$(port_of_namespace_seed "$TEST_E2E_BACKEND_PORT_BASE")" "$TEST_E2E_PORT_SCAN_RANGE"
    )"
    if [ -z "$E2E_BACKEND_PORT" ]; then
        print_layer_result "e2e" 1
        E2E_RESULT=1
        cleanup_e2e_runtimes
        return 1
    fi

    E2E_FRONTEND_PORT="$(
        find_free_port "$E2E_FRONTEND_PORT" "$(port_of_namespace_seed "$TEST_E2E_FRONTEND_PORT_BASE")" "$TEST_E2E_PORT_SCAN_RANGE"
    )"
    if [ -z "$E2E_FRONTEND_PORT" ]; then
        print_layer_result "e2e" 1
        E2E_RESULT=1
        cleanup_e2e_runtimes
        return 1
    fi

    export E2E_BACKEND_PORT
    export E2E_FRONTEND_PORT

    echo -e "${YELLOW}E2E 命名空间: ${TEST_NAMESPACE}${NC}"
    echo -e "${YELLOW}E2E 运行目录: ${TEST_RUN_DIR}${NC}"
    echo -e "${YELLOW}后端 DB: ${E2E_DB_PATH}${NC}"
    echo -e "${YELLOW}后端端口: ${E2E_BACKEND_PORT}，前端端口: ${E2E_FRONTEND_PORT}${NC}"

    LOCAL_E2E_DB_URL="sqlite:///$E2E_DB_PATH"
    DATABASE_URL="$LOCAL_E2E_DB_URL" \
    python -c "from src.database.models import init_db; init_db()"
    local init_result=$?
    if [ $init_result -ne 0 ]; then
        print_layer_result "e2e" $init_result
        E2E_RESULT=$init_result
        cleanup_e2e_runtimes
        return $init_result
    fi

    cd "$PROJECT_DIR/frontend"
    export PYTHON="$(command -v python)"
    # 本地默认使用 Playwright 自带 Chromium，避免系统 Chrome 与 --no-sandbox 的组合引发启动崩溃
    export E2E_BROWSER_CHANNEL="${E2E_BROWSER_CHANNEL:-}"
    export E2E_CHROME_EXECUTABLE="${E2E_CHROME_EXECUTABLE:-}"
    # 仅在 CI/容器环境默认开启 --no-sandbox；本地优先保持 sandbox=true，避免 macOS 下权限错误
    if [ -z "${E2E_NO_SANDBOX+x}" ]; then
        if [ "${CI:-}" = "true" ] || [ "${CI:-}" = "1" ]; then
            if [ -n "${GITHUB_ACTIONS:-}" ] || [ -n "${CI_PIPELINE_ID:-}" ] || [ -n "${CI_SERVER_NAME:-}" ]; then
                export E2E_NO_SANDBOX=1
            else
                export E2E_NO_SANDBOX=0
            fi
        else
            export E2E_NO_SANDBOX=0
        fi
    fi

    echo -e "${BLUE}E2E runtime config: channel='${E2E_BROWSER_CHANNEL:-<auto>}' executable='${E2E_CHROME_EXECUTABLE:-<auto>}' no-sandbox='${E2E_NO_SANDBOX}'${NC}"

    # 提高文件描述符上限，降低 macOS 下 EMFILE 命中率
    ulimit -n 8192 >/dev/null 2>&1 || ulimit -n 4096 >/dev/null 2>&1 || true

    echo -e "${YELLOW}启动确定性 E2E 后端...${NC}"
    cd "$PROJECT_DIR"
    activate_python_env
    JWT_SECRET="${JWT_SECRET:-e2e-test-secret}" \
    API_HOST=127.0.0.1 API_PORT="$E2E_BACKEND_PORT" \
    E2E_BACKEND_HOST=127.0.0.1 E2E_BACKEND_PORT="$E2E_BACKEND_PORT" \
    DATABASE_URL="$LOCAL_E2E_DB_URL" \
    E2E_CONTRACT_PROBE_FAST=1 E2E_DETERMINISTIC_STORY=1 STORY_TTS_ALLOW_REQUEST_PROVIDER=1 \
    MINIMAX_E2E_LOCAL_AUDIO=1 MINIMAX_E2E_LOCAL_IMAGE=1 NETEASE_E2E_LOCAL_MUSIC=1 API_RELOAD=false \
    python run_api.py > "$BACKEND_LOG" 2>&1 &
    BACKEND_PID=$!
    echo "$BACKEND_PID" > "$BACKEND_PID_FILE"
    local backend_ready=0
    for backend_ready_attempt in {1..30}; do
        if curl -fsS "http://127.0.0.1:$E2E_BACKEND_PORT/api/health" >/dev/null 2>&1; then
            backend_ready=1
            break
        fi
        if ! kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
            break
        fi
        sleep 1
    done
    if [ "$backend_ready" -ne 1 ]; then
        echo -e "${RED}后端启动失败，跳过 E2E 测试${NC}"
        echo -e "${RED}日志: $BACKEND_LOG${NC}"
        cat "$BACKEND_LOG" 2>/dev/null || true
        E2E_RESULT=1
        cleanup_e2e_runtimes
        return 1
    fi
    echo -e "${GREEN}后端已启动 (PID: $BACKEND_PID)${NC}"
    cd "$PROJECT_DIR/frontend"

    local frontend_mode="${E2E_FRONTEND_MODE:-prod}"
    local FRONTEND_PID=""
    local backend_url="http://127.0.0.1:$E2E_BACKEND_PORT"

    if [ "$frontend_mode" = "dev" ]; then
        echo -e "${YELLOW}使用 Playwright webServer（dev）模式运行 E2E（不推荐）...${NC}"
        BACKEND_URL="$backend_url"
        NEXT_PUBLIC_API_URL="/api"
        export BACKEND_URL NEXT_PUBLIC_API_URL
        # default behavior will use playwright.config.ts webServer branch
    else
        echo -e "${YELLOW}使用生产模式启动前端（next build + start）以规避开发监听问题...${NC}"
        cd "$PROJECT_DIR/frontend"
        echo -e "${YELLOW}执行 npm run build，避免复用旧 .next 构建...${NC}"
        NEXT_DISABLE_STANDALONE=1 BACKEND_URL="$backend_url" NEXT_PUBLIC_API_URL="/api" npm run build
        if [ $? -ne 0 ]; then
            echo -e "${RED}前端构建失败，跳过 E2E 测试${NC}"
            E2E_RESULT=1
            cleanup_e2e_runtimes
            return 1
        fi

        local frontend_port="$E2E_FRONTEND_PORT"
        cd "$PROJECT_DIR/frontend"
        NEXT_DISABLE_STANDALONE=1 BACKEND_URL="$backend_url" NEXT_PUBLIC_API_URL="/api" CI=1 E2E_FRONTEND_PORT="$frontend_port" npm run start -- --hostname 127.0.0.1 --port "$frontend_port" > "$FRONTEND_LOG" 2>&1 &
        FRONTEND_PID=$!
        echo "$FRONTEND_PID" > "$FRONTEND_PID_FILE"
        local frontend_started=0
        for frontend_ready_attempt in $(seq 1 45); do
            if curl -fsS "http://127.0.0.1:$frontend_port" >/dev/null 2>&1; then
                frontend_started=1
                break
            fi
            if lsof -iTCP:"$frontend_port" -sTCP:LISTEN >/dev/null 2>&1; then
                frontend_started=1
                break
            fi
            if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
                break
            fi
            sleep 1
        done
        if [ "$frontend_started" -ne 1 ]; then
            echo -e "${RED}前端启动失败，跳过 E2E 测试${NC}"
            echo -e "${RED}日志: $FRONTEND_LOG${NC}"
            cat "$FRONTEND_LOG" 2>/dev/null || true
            E2E_RESULT=1
            cleanup_e2e_runtimes
            return 1
        fi
        echo -e "${GREEN}前端已启动 (PID: $FRONTEND_PID)${NC}"
    fi

    export CI=1
    export E2E_BACKEND_HOST=127.0.0.1
    export E2E_BROWSER_API_HOST="${E2E_BROWSER_API_HOST:-localhost}"
    export E2E_BACKEND_PORT

    echo -e "${YELLOW}运行完整 Playwright E2E 测试 (chromium)...${NC}"
    run_playwright_command "core" npx playwright test --project=core --reporter=dot --workers=1
    local core_result=$?

    echo -e "${YELLOW}运行会员 AI 音乐队列补充 E2E 测试...${NC}"
    run_playwright_command "music-player" npx playwright test e2e/music-player.spec.ts \
        --project=ai-heavy \
        --grep "会员 AI 曲目生成后只进入后续队列且不切换当前歌曲" \
        --reporter=list \
        --workers=1 \
        --no-deps
    local music_ai_result=$?

    echo -e "${YELLOW}运行角色设定 PATCH 持久化 E2E 浏览器测试...${NC}"
    run_playwright_command "character-settings" npx playwright test e2e/character-settings-persistence.spec.ts \
        --project=ai-heavy \
        --reporter=list \
        --workers=1 \
        --no-deps
    local character_settings_result=$?

    local result=0
    if [ $core_result -ne 0 ] || [ $music_ai_result -ne 0 ] || [ $character_settings_result -ne 0 ]; then
        result=1
    fi

    cleanup_e2e_runtimes

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
    ensure_test_dirs
    
    # 后端覆盖率
    echo -e "${YELLOW}--- 后端覆盖率 ---${NC}"
    cd "$PROJECT_DIR"
    activate_python_env
    pytest tests/ --cov=src --cov-report=term-missing --cov-report=html:"$TEST_RUN_DIR"/htmlcov/backend
    
    # 前端覆盖率
    echo ""
    echo -e "${YELLOW}--- 前端覆盖率 ---${NC}"
    cd "$PROJECT_DIR/frontend"
    npm test -- --coverage --coverageReporters=text --coverageReporters=html --coverageDirectory="$TEST_RUN_DIR"/frontend/coverage
    
    echo ""
    echo -e "${GREEN}覆盖率报告已生成:${NC}"
    echo "  后端: $TEST_RUN_DIR/htmlcov/backend/index.html"
    echo "  前端: $TEST_RUN_DIR/frontend/coverage/lcov-report/index.html"
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
    ensure_test_dirs
    cd "$PROJECT_DIR"
    activate_python_env
    PERF_BACKEND_PORT="${E2E_BACKEND_PORT:-8000}"
    
    # 检查后端是否运行
    if ! is_port_listening "$PERF_BACKEND_PORT"; then
        echo -e "${YELLOW}后端未运行，正在启动...${NC}"
        DATABASE_URL="sqlite:///$TEST_DATA_DIR/perf.sqlite" \
        python run_api.py > "$TEST_RUN_DIR/backend_perf.log" 2>&1 &
        sleep 3
    fi
    
    echo -e "${YELLOW}启动 Locust 性能测试...${NC}"
    echo -e "${YELLOW}访问 http://localhost:8089 进行测试配置${NC}"
    cd tests/performance
    locust -f locustfile.py --host="http://127.0.0.1:${PERF_BACKEND_PORT}"
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

# 主逻辑。被测试子 shell source 时只加载函数，不执行测试命令。
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
    return 0
fi

case "${1:-}" in
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
