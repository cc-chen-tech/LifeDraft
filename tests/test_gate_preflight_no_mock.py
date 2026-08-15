"""Early no-mock checks that should fail before slower DB/E2E layers."""

import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CHANGE_DIR = (
    ROOT
    / "openspec"
    / "changes"
    / "archive"
    / "2026-06-02-fix-story-continuity-history-media"
)
SPEC_NAMES = (
    "collection-stability",
    "gameplay-continuity",
    "history-review",
    "member-voice-reading",
    "test-gates",
)


def _read_e2e_regression_fixture_sources() -> str:
    fixture_dir = ROOT / "frontend" / "src" / "app" / "e2e-regression"
    return "\n".join(
        (fixture_dir / source_name).read_text(encoding="utf-8")
        for source_name in ("page.tsx", "E2ERegressionClient.tsx")
    )


def test_fix_story_continuity_change_tasks_stay_complete() -> None:
    tasks = (CHANGE_DIR / "tasks.md").read_text(encoding="utf-8")

    assert "- [ ]" not in tasks
    assert tasks.count("- [x]") == 34
    assert "7.1 Add frontend no-skip regression coverage for `/story/opening`" in tasks
    assert "8.8 Run targeted regression tests and `./test.sh all`." in tasks


def test_archived_story_continuity_specs_are_synced_to_main_specs() -> None:
    for spec_name in SPEC_NAMES:
        archived_spec = CHANGE_DIR / "specs" / spec_name / "spec.md"
        main_spec = ROOT / "openspec" / "specs" / spec_name / "spec.md"

        assert archived_spec.exists()
        assert main_spec.exists()

        archived_text = archived_spec.read_text(encoding="utf-8")
        main_text = main_spec.read_text(encoding="utf-8")
        for requirement in archived_text.split("### Requirement: ")[1:]:
            title = requirement.split("\n", 1)[0]
            assert f"### Requirement: {title}" in main_text


def test_preflight_script_runs_before_expensive_layers() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")

    assert "run_preflight" in script
    assert "openspec validate --all --strict" in script
    assert "openspec validate add-story-voice-reading --strict" in script
    assert "openspec validate shift-left-e2e-contract-gates --strict" in script
    assert "npx tsc --noEmit --strict" in script
    assert "tests/test_gate_preflight_no_mock.py" in script
    assert "tests/test_gate_gameplay_behavior_no_mock.py" in script
    assert "tests/test_gate_contracts_no_mock.py" in script
    assert "tests/test_story_voice_chapter_contract.py" in script
    assert "tests/test_music_runtime_removed.py" in script
    assert "tests/test_shift_left_e2e_contract_no_mock.py" in script
    assert "storyContinuityPreflight.test.tsx" in script
    assert "src/__tests__/lib/sse.test.ts" in script
    assert "python -m flake8 src/services/story_voice_reading.py" in script
    assert "python scripts/export_openapi.py" in script
    assert 'local openapi_check_dir="$TEST_RUN_DIR/openapi-check"' in script
    assert 'python scripts/export_openapi.py "$generated_openapi_schema"' in script
    assert 'cmp -s "$generated_openapi_schema" frontend/src/types/openapi-schema.json' in script
    assert script.index("run_preflight || ((failed++))") < script.index("run_mypy || ((failed++))")
    assert script.index("run_preflight || ((failed++))") < script.index(
        "run_e2e_browser || ((failed++))"
    )


def test_preflight_runs_authoritative_continuity_ledger_regressions() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")

    assert "tests/test_continuity_ledger.py" in script
    assert "tests/test_continuity_ledger_integration.py" in script


def test_preflight_runs_read_only_assistant_grounding_regressions() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")

    assert "tests/test_assistant_grounding.py" in script
    assert "src/game/assistant_grounding.py" in script


def test_playwright_log_tempfile_template_has_enough_random_suffix() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")

    assert 'PLAYWRIGHT_LOG_DIR="$TEST_RUN_DIR/playwright"' in script
    assert 'output_file="${PLAYWRIGHT_LOG_DIR}/story2-playwright-${label}-$(date +%Y%m%d_%H%M%S)-${RANDOM}.log"' in script
    assert 'rm -f "$PLAYWRIGHT_LOG_DIR/story2-playwright-${label}-"*.log' in script
    assert '"$PLAYWRIGHT_LOG_DIR/story2-playwright-${label}-"*.log' in script
    assert '$(date +%Y%m%d_%H%M%S)-${RANDOM}.log' in script
    assert 'mktemp "/tmp/story2-playwright-${label}-XXXX.log"' not in script


def test_preflight_validates_archived_provider_story_tts_spec() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")
    archived_spec = (
        ROOT
        / "openspec"
        / "changes"
        / "archive"
        / "2026-06-02-add-provider-backed-story-tts"
        / "specs"
        / "provider-backed-story-tts"
        / "spec.md"
    )
    main_spec = ROOT / "openspec" / "specs" / "provider-backed-story-tts" / "spec.md"

    assert archived_spec.exists()
    assert main_spec.exists()
    assert "openspec validate provider-backed-story-tts --strict" in script
    assert "openspec validate add-provider-backed-story-tts --strict" not in script


def test_preflight_validates_current_story_tts_contracts() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")
    config = (ROOT / "frontend" / "playwright.config.ts").read_text(encoding="utf-8")

    assert "openspec validate add-story-voice-reading --strict" in script
    assert "openspec validate provider-backed-story-tts --strict" in script
    assert "tests/test_story_voice_chapter_contract.py" in script
    assert "tests/test_story_voice_async_chapter.py" in script
    assert 'run_playwright_command "core" npx playwright test --project=core' in script
    assert "minimax-story-audio-generation.spec.ts" not in config.split(
        "const AI_HEAVY_TESTS", 1
    )[1].split("const MANUAL_EXPLORATION_TESTS", 1)[0]


def test_minimax_api_key_is_not_committed_to_repository_files() -> None:
    scanned_suffixes = {".py", ".ts", ".tsx", ".js", ".jsx", ".md", ".yml", ".yaml", ".sh"}
    allowed_dirs = {".git", ".next", "node_modules", "venv", "test-results", "playwright-report"}
    leaked_paths: list[str] = []

    for path in _iter_scannable_files(ROOT, allowed_dirs, scanned_suffixes):
        token_prefix = "sk-" + "cp-"
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if token_prefix in text:
            leaked_paths.append(str(path.relative_to(ROOT)))

    assert leaked_paths == []


def test_e2e_backend_uses_dotenv_minimax_key_not_fake_override() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")

    assert "MINIMAX_API_KEY=test-key" not in script
    assert (
        "STORY_TTS_PROVIDER=minimax"
    ) in script
    assert "MINIMAX_E2E_LOCAL_AUDIO=1 MINIMAX_E2E_LOCAL_IMAGE=1 API_RELOAD=false" in script
    assert "NETEASE_E2E_LOCAL_MUSIC" not in script


def _iter_scannable_files(
    root: Path, allowed_dirs: set[str], scanned_suffixes: set[str]
) -> list[Path]:
    files: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in allowed_dirs]
        for filename in filenames:
            path = Path(dirpath) / filename
            if not path.is_file() or path.suffix not in scanned_suffixes:
                continue
            files.append(path)

    return files


def test_generated_minimax_audio_assets_are_gitignored() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "data/music_assets/" in gitignore
    assert "data/voice_assets/" in gitignore


def test_frontend_layout_does_not_depend_on_google_font_network() -> None:
    layout = (ROOT / "frontend" / "src" / "app" / "layout.tsx").read_text(
        encoding="utf-8"
    )
    globals_css = (ROOT / "frontend" / "src" / "app" / "globals.css").read_text(
        encoding="utf-8"
    )

    assert "next/font/google" not in layout
    assert "fonts.gstatic.com" not in layout
    assert "--font-sans-sc" in globals_css
    assert "--font-serif-sc" in globals_css




def test_e2e_gate_does_not_reuse_frontend_from_other_worktree() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")
    config = (ROOT / "frontend" / "playwright.config.ts").read_text(encoding="utf-8")

    assert 'TEST_NAMESPACE="${TEST_NAMESPACE:-$(printf' in script
    assert 'TEST_RUN_ROOT="${TEST_RUN_ROOT:-${TMPDIR:-/tmp}/story2-test-runs}"' in script
    assert 'TEST_RUN_DIR="${TEST_RUN_DIR:-$TEST_RUN_ROOT/$TEST_NAMESPACE}"' in script
    assert 'TEST_LOCK_DIR="$TEST_RUN_ROOT/locks"' in script
    assert 'mkdir -p "$TEST_LOCK_DIR"' in script
    assert script.index('mkdir -p "$TEST_LOCK_DIR"') < script.index('mkdir "$lock_dir"')
    assert "E2E_RESULT=1" in script.split('if ! mkdir "$lock_dir"', 1)[1].split("fi", 1)[0]
    assert 'BACKEND_PID_FILE="$TEST_RUN_DIR/backend.pid"' in script
    assert 'FRONTEND_PID_FILE="$TEST_RUN_DIR/frontend.pid"' in script
    assert 'E2E_DB_PATH="$TEST_DATA_DIR/story2-e2e.sqlite"' in script
    assert 'find_free_port "$E2E_BACKEND_PORT" "$(port_of_namespace_seed "$TEST_E2E_BACKEND_PORT_BASE")"' in script
    assert 'find_free_port "$E2E_FRONTEND_PORT" "$(port_of_namespace_seed "$TEST_E2E_FRONTEND_PORT_BASE")"' in script
    assert "export E2E_FRONTEND_PORT" in script
    assert "E2E 运行目录: ${TEST_RUN_DIR}" in script
    assert "占用 3000 端口的前端不属于当前 worktree" not in script
    assert "ensure_e2e_frontend_port_available" not in script
    assert 'find_free_port "$E2E_FRONTEND_PORT"' in script
    assert "TEST_E2E_FRONTEND_PORT_BASE" in script
    assert 'local frontend_port="$E2E_FRONTEND_PORT"' in script
    assert script.index('find_free_port "$E2E_FRONTEND_PORT"') < script.index(
        "npm run start -- --hostname 127.0.0.1"
    )
    assert "process.env.E2E_FRONTEND_PORT" in config
    assert "reuseExistingServer: false" in config


def test_e2e_specs_use_configured_frontend_port() -> None:
    global_setup = (ROOT / "frontend" / "e2e" / "global-setup.ts").read_text(
        encoding="utf-8"
    )
    assert "process.env.E2E_FRONTEND_PORT" in global_setup
    assert "const FRONTEND_URL = 'http://localhost:3000'" not in global_setup

    for spec_path in (ROOT / "frontend" / "e2e").glob("*.spec.ts"):
        if spec_path.name == "story101-exploration.spec.ts":
            continue

        spec = spec_path.read_text(encoding="utf-8")
        assert "const BASE_URL = 'http://localhost:3000'" not in spec
        assert "const BASE_URL = process.env.E2E_BASE_URL || ;" not in spec
        assert "const API_URL = process.env.E2E_API_URL || ;" not in spec
        assert "const API_BASE = process.env.E2E_API_URL || ;" not in spec
        assert "toContain('localhost:3000')" not in spec
        assert "http://localhost:8000" not in spec


def test_e2e_local_backend_and_browser_launch_are_configurable() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")
    config = (ROOT / "frontend" / "playwright.config.ts").read_text(
        encoding="utf-8"
    )
    global_setup = (ROOT / "frontend" / "e2e" / "global-setup.ts").read_text(
        encoding="utf-8"
    )
    auth_helper = (ROOT / "frontend" / "e2e" / "helpers" / "auth.ts").read_text(
        encoding="utf-8"
    )

    assert "process.env.E2E_BROWSER_CHANNEL" in config
    assert "process.env.E2E_CHROME_EXECUTABLE" in config
    assert "process.env.E2E_NO_SANDBOX" in config
    assert "const browserChannel = process.env.E2E_BROWSER_CHANNEL?.trim()" in config
    assert "const chromeExecutable = process.env.E2E_CHROME_EXECUTABLE?.trim()" in config
    assert "const ciEnabled = parseBooleanEnv(process.env.CI) === true" in config
    assert "const hasExplicitNoSandbox = process.env.E2E_NO_SANDBOX !== undefined" in config
    assert "const explicitNoSandbox = parseBooleanEnv(process.env.E2E_NO_SANDBOX)" in config
    assert "const noSandbox = hasExplicitNoSandbox ? explicitNoSandbox === true : ciEnabled" in config
    assert "browserChannel ? { channel: browserChannel }" in config
    assert "chromeExecutable ? { executablePath: chromeExecutable }" in config
    assert "const launchArgs = noSandbox ? ['--no-sandbox', '--disable-dev-shm-usage'] : []" in config
    assert "const ignoreLaunchDefaultArgs = noSandbox ? [] : ['--no-sandbox']" in config
    assert "use: desktopChromeUse" in config
    assert 'if [ -z "${E2E_NO_SANDBOX+x}" ]; then' in script
    assert 'if [ "${CI:-}" = "true" ] || [ "${CI:-}" = "1" ]; then' in script
    assert "export E2E_NO_SANDBOX=1" in script
    assert "export E2E_NO_SANDBOX=0" in script
    assert "process.env.E2E_BACKEND_HOST || '127.0.0.1'" in global_setup
    assert "process.env.E2E_BACKEND_PORT || '8000'" in global_setup
    assert "process.env.E2E_BACKEND_HOST || '127.0.0.1'" in auth_helper
    assert "process.env.E2E_BACKEND_PORT || '8000'" in auth_helper
    assert "API_HOST.includes(c.domain)" in auth_helper
    register_user_body = auth_helper.split("export async function registerUser", 1)[1].split(
        "/**\n * 确保用户已登录", 1
    )[0]
    assert "await context.addCookies" in register_user_body
    assert "domain: 'localhost'" in register_user_body
    assert 'E2E_BACKEND_HOST=127.0.0.1 E2E_BACKEND_PORT="$E2E_BACKEND_PORT"' in script
    assert 'API_HOST=127.0.0.1 API_PORT="$E2E_BACKEND_PORT"' in script
    assert 'DATABASE_URL="$LOCAL_E2E_DB_URL"' in script
    assert 'cleanup_pid_file "$BACKEND_PID_FILE" "后端"' in script
    assert "MINIMAX_E2E_LOCAL_AUDIO=1" in script
    assert "MINIMAX_E2E_LOCAL_IMAGE=1" in script
    assert "E2E_FRONTEND_MODE:-prod" in script
    assert 'local backend_url="http://127.0.0.1:$E2E_BACKEND_PORT"' in script
    assert 'BACKEND_URL="$backend_url"' in script
    assert "cleanup_e2e_runtimes" in script
    assert 'NEXT_DISABLE_STANDALONE=1 BACKEND_URL="$backend_url" NEXT_PUBLIC_API_URL="/api" npm run build' in script
    assert "npm run start -- --hostname 127.0.0.1" in script
    assert "if ! [ -d \".next\" ]" not in script
    assert "ulimit -n 8192" in script


def test_e2e_backend_sets_required_jwt_secret() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")

    assert "JWT_SECRET" in script
    assert "e2e-test-secret" in script


def test_e2e_backend_start_waits_for_health_endpoint() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")
    start_block = script.split("启动确定性 E2E 后端", 1)[1].split(
        "cd \"$PROJECT_DIR/frontend\"", 1
    )[0]

    assert 'API_HOST=127.0.0.1 API_PORT="$E2E_BACKEND_PORT"' in start_block
    assert "for backend_ready_attempt in" in start_block
    assert 'curl -fsS "http://127.0.0.1:$E2E_BACKEND_PORT/api/health"' in start_block
    assert 'cat "$BACKEND_LOG"' in start_block
    assert "sleep 3\n    if ! lsof" not in start_block


def test_e2e_frontend_proxy_targets_dynamic_backend_port() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")
    build_block = script.split("使用生产模式启动前端", 1)[1].split(
        "local frontend_started=0", 1
    )[0]
    command_lines = [
        line.strip()
        for line in build_block.splitlines()
        if line.strip().startswith("NEXT_DISABLE_STANDALONE=1")
    ]
    build_command = next(line for line in command_lines if "npm run build" in line)
    start_command = next(line for line in command_lines if "npm run start" in line)

    assert 'local backend_url="http://127.0.0.1:$E2E_BACKEND_PORT"' in script
    assert 'BACKEND_URL="$backend_url"' in build_command
    assert 'NEXT_PUBLIC_API_URL="/api"' in build_command
    assert 'BACKEND_URL="$backend_url"' in start_command
    assert 'NEXT_PUBLIC_API_URL="/api"' in start_command


def test_e2e_dev_frontend_proxy_targets_dynamic_backend_port() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")
    dev_block = script.split('if [ "$frontend_mode" = "dev" ]; then', 1)[1].split(
        "else", 1
    )[0]

    assert 'local backend_url="http://127.0.0.1:$E2E_BACKEND_PORT"' in script
    assert 'BACKEND_URL="$backend_url"' in dev_block
    assert 'NEXT_PUBLIC_API_URL="/api"' in dev_block
    assert "export BACKEND_URL NEXT_PUBLIC_API_URL" in dev_block


def test_find_free_port_errors_do_not_pollute_captured_port_value() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")
    port_func = script.split("find_free_port() {", 1)[1].split(
        "\n}\n\nactivate_python_env", 1
    )[0]

    assert '>&2 echo -e "${RED}端口 $preferred 已被占用。请先释放该端口或设置 E2E_BACKEND_PORT / E2E_FRONTEND_PORT。${NC}"' in port_func
    assert '>&2 echo -e "${RED}无法分配空闲端口（$base-$((base + range))）${NC}"' in port_func


def test_collection_panel_cache_spec_uses_scoped_character_locator() -> None:
    spec = (
        ROOT / "frontend" / "e2e" / "collection-panel-cache.spec.ts"
    ).read_text(encoding="utf-8")

    assert "page.locator('text=缓存测试角色')" not in spec
    assert "function collectionDialog" in spec
    assert "name: '查看人物：缓存测试角色'" in spec
    assert "initialPlayerRow.getByText('主角', { exact: true })" in spec
    assert "cachedPlayerRow.getByText('主角', { exact: true })" in spec


def test_e2e_specs_do_not_hardcode_default_backend_port() -> None:
    offenders = []
    for spec_path in sorted((ROOT / "frontend" / "e2e").glob("*.spec.ts")):
        text = spec_path.read_text(encoding="utf-8")
        if "http://localhost:8000" in text or "http://127.0.0.1:8000" in text:
            offenders.append(spec_path.name)

    assert offenders == []


def test_e2e_lock_initializes_lock_directory_before_acquire() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")
    lock_block = script.split("with_e2e_lock() {", 1)[1].split(
        "\n}\n\nis_port_listening", 1
    )[0]

    assert 'mkdir -p "$TEST_LOCK_DIR"' in lock_block
    assert lock_block.index('mkdir -p "$TEST_LOCK_DIR"') < lock_block.index('mkdir "$lock_dir"')


def test_playwright_global_setup_does_not_spawn_competing_backend() -> None:
    global_setup = (ROOT / "frontend" / "e2e" / "global-setup.ts").read_text(
        encoding="utf-8"
    )
    global_teardown = (ROOT / "frontend" / "e2e" / "global-teardown.ts").read_text(
        encoding="utf-8"
    )

    assert "startBackend()" not in global_setup
    assert "__e2e_backend_process" not in global_setup
    assert "__e2e_backend_process" not in global_teardown


def test_frontend_regression_fixture_exercises_changed_surfaces() -> None:
    fixture = _read_e2e_regression_fixture_sources()
    e2e = (ROOT / "frontend" / "e2e" / "no-mock-regression.spec.ts").read_text(encoding="utf-8")

    for token in (
        "streamed-story",
        "history-scene-image-state",
        "collection-refresh-state",
        "OptionCards",
        "ChatBar",
    ):
        assert token in fixture

    for test_name in (
        "stream retry replaces active story attempt instead of duplicating it",
        "history review stays pinned to selected round with matching scene image state",
        "collection panel keeps data visible during background refresh",
    ):
        assert test_name in e2e


def test_regression_fixture_contains_no_retired_music_runtime() -> None:
    fixture = _read_e2e_regression_fixture_sources()

    assert "MusicPlayer" not in fixture
    assert "useMusicStore" not in fixture
    assert "/api/music" not in fixture


def test_frontend_image_generation_path_is_checked_before_e2e() -> None:
    api_source = (ROOT / "frontend" / "src" / "lib" / "api.ts").read_text(encoding="utf-8")

    assert (
        "fetchJson<{ images: Array<{ image_id: number; image_url: string }>; total: number }>('/images/generate'"
        in api_source
    )
    assert "fetchJson('/images'" not in api_source


def test_api_runtime_files_remain_python39_import_compatible() -> None:
    router_source = (ROOT / "src" / "api" / "routers" / "auth.py").read_text(
        encoding="utf-8"
    )

    assert "str | None" not in router_source


def test_backend_docker_python_version_supports_runtime_requirements() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

    python_versions = [
        tuple(int(part) for part in match.groups())
        for match in re.finditer(r"^FROM python:(\d+)\.(\d+)-slim", dockerfile, re.MULTILINE)
    ]

    assert python_versions
    assert "websockets>=16.0" in requirements
    assert all(version >= (3, 10) for version in python_versions)


def test_ai_heavy_e2e_specs_do_not_override_project_timeout_too_low() -> None:
    spec = (ROOT / "frontend" / "e2e" / "claude-code-improvements.spec.ts").read_text(
        encoding="utf-8"
    )

    assert "test.setTimeout(120_000)" not in spec
    assert "test.setTimeout(300_000)" in spec


def test_ai_heavy_progression_uses_bounded_choice_waits() -> None:
    spec = (ROOT / "frontend" / "e2e" / "claude-code-improvements.spec.ts").read_text(
        encoding="utf-8"
    )
    progression_test = spec.split(
        "test('5. Game progression works correctly after post-processing'"
    )[1].split("test('6. Long-running game does not fail from context overflow'")[0]

    assert "waitForChoiceProgressionCheckpoint" in spec
    assert "45_000" in spec
    assert "await waitForNetworkIdle(page);\n      await page.waitForTimeout(3000);" not in progression_test
    assert "await page.waitForTimeout(5000);\n      await waitForNetworkIdle(page);" not in progression_test


def test_choice_impact_ui_e2e_seeds_event_before_opening_play_page() -> None:
    spec = (ROOT / "frontend" / "e2e" / "choice-impact-visible.spec.ts").read_text(
        encoding="utf-8"
    )
    ui_test = spec.split('test("选择后状态栏不显示资源变化"')[1].split('test("同步选择 API 返回 effects_applied"')[0]

    assert "seedEventForGame" in spec
    assert "await seedEventForGame(context, gameId);" in ui_test
    assert "not.toContainText" in ui_test
    assert 'await page.waitForTimeout(3000);' not in ui_test


def test_rewrite_discoverability_e2e_seeds_story_before_clicking_rewrite() -> None:
    spec = (ROOT / "frontend" / "e2e" / "rewrite-button-discoverable.spec.ts").read_text(
        encoding="utf-8"
    )

    assert "seedStoryForRewrite" in spec
    assert "await seedStoryForRewrite(page);" in spec
    assert "/e2e-regression" in spec
    assert "await expect(rewriteButton).toBeEnabled" in spec


def test_story_voice_test_controls_stay_out_of_real_play_page() -> None:
    component = (
        ROOT / "frontend" / "src" / "components" / "game" / "StoryListeningExperience.tsx"
    ).read_text(encoding="utf-8")
    play_page = (ROOT / "frontend" / "src" / "app" / "play" / "page.tsx").read_text(
        encoding="utf-8"
    )
    assert "showTestControls" not in component
    assert "StoryListeningExperience" in play_page
    assert "useStoryVoiceStore" not in play_page
    assert "GlobalMusicPlayer" not in play_page


def test_story_voice_production_controls_expose_persistent_auto_read_toggle() -> None:
    component = (
        ROOT / "frontend" / "src" / "components" / "game" / "StoryListeningExperience.tsx"
    ).read_text(encoding="utf-8")

    auto_read_label = "下一章自动播放"
    assert auto_read_label in component
    assert "api.voice_reading.getSettings" in component
    assert "api.voice_reading.updateSettings" in component
    assert "settings.auto_read_enabled" in component
    assert "autoReadRef.current" in component


def test_story_voice_production_controls_expose_voice_selection() -> None:
    component = (
        ROOT / "frontend" / "src" / "components" / "game" / "StoryListeningExperience.tsx"
    ).read_text(encoding="utf-8")

    assert "音色" in component
    assert "warm_female" in component
    assert "calm_male" in component
    assert "clear_neutral" in component
    assert "selectedVoice" in component
    assert "settings.selected_voice_color" in component
    assert "voice_id: selectedVoice" in component
    assert "selected_speed" in component


def test_story_voice_production_settings_do_not_duplicate_test_controls() -> None:
    component = (
        ROOT / "frontend" / "src" / "components" / "game" / "StoryListeningExperience.tsx"
    ).read_text(encoding="utf-8")

    assert "showTestControls" not in component
    assert "SPEEDS.map" in component
    assert "VOICES.map" in component


def test_preflight_runs_dialog_and_sheet_a11y_regressions() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")

    assert "src/__tests__/components/DialogA11y.test.tsx" in script
    assert "src/__tests__/components/SheetA11y.test.tsx" in script


def test_production_layout_does_not_mount_global_music_player() -> None:
    layout = (ROOT / "frontend" / "src" / "app" / "layout.tsx").read_text(encoding="utf-8")

    assert "GlobalMusicPlayer" not in layout
    assert "fixedRegions" not in layout


def test_play_page_does_not_activate_music_or_unified_sound_state() -> None:
    play_page = (ROOT / "frontend" / "src" / "app" / "play" / "page.tsx").read_text(
        encoding="utf-8"
    )

    assert "useMusicStore" not in play_page
    assert "setActiveStoryText" not in play_page
    assert "SOUND_PANEL" not in play_page


def test_play_page_missing_game_state_has_actionable_recovery_ui() -> None:
    play_page = (ROOT / "frontend" / "src" / "app" / "play" / "page.tsx").read_text(
        encoding="utf-8"
    )

    assert "正在恢复当前进度" in play_page
    assert "返回首页" in play_page
    assert 'onClick={() => router.replace("/")}' in play_page
    assert "window.location.reload()" not in play_page
    assert (
        'if (!gameId) {\n    return (\n      <div className="min-h-screen flex items-center justify-center">\n        <Loader2'
        not in play_page
    )


def test_story_voice_e2e_uses_same_origin_api_proxy() -> None:
    api_source = (ROOT / "frontend" / "src" / "lib" / "api.ts").read_text(encoding="utf-8")
    request_reading_block = api_source.split("requestReading: (data: StoryVoiceReadingRequest) =>")[
        1
    ].split("getJob:", 1)[0]

    assert "fetchJson<StoryVoiceReadingResponse>('/voice-reading/read'" in request_reading_block
    assert "fetchJsonFromBase" not in request_reading_block
    assert "getLocalBackendApiBase" not in request_reading_block


def test_story_voice_e2e_workflow_enables_deterministic_backend_audio() -> None:
    workflow = (ROOT / ".github" / "workflows" / "e2e-tests.yml").read_text(
        encoding="utf-8"
    )

    assert "STORY_TTS_PROVIDER=minimax" in workflow
    assert "MINIMAX_E2E_LOCAL_AUDIO=1" in workflow
    assert "MINIMAX_E2E_LOCAL_IMAGE=1" in workflow
    assert "NETEASE_E2E_LOCAL_MUSIC" not in workflow
    assert "STORY_TTS_ALLOW_REQUEST_PROVIDER" not in workflow
    assert "MINIMAX_API_KEY=test-key" in workflow


def test_e2e_workflow_uses_same_layered_gate_as_local_test_sh() -> None:
    workflow = (ROOT / ".github" / "workflows" / "e2e-tests.yml").read_text(
        encoding="utf-8"
    )

    assert "run: ./test.sh e2e" in workflow
    assert "run: npm run test:e2e" not in workflow
    assert "Start backend server" not in workflow
    assert "Start frontend server" not in workflow


def test_production_deploy_syncs_minimax_secret_to_ecs_env_without_committing_key() -> None:
    workflow = (ROOT / ".github" / "workflows" / "deploy-production.yml").read_text(
        encoding="utf-8"
    )

    assert "MINIMAX_API_KEY: ${{ secrets.MINIMAX_API_KEY }}" in workflow
    assert "MINIMAX_API_KEY_B64" in workflow
    assert "STORY_TTS_PROVIDER" in workflow
    assert "STORY_TTS_PROVIDER=minimax" in workflow
    assert "STORY_TTS_ALLOW_REQUEST_PROVIDER" not in workflow
    assert "STORY_TTS_AUTO_READ_DEFAULT_ENABLED=true" in workflow
    assert "ENABLE_DAILY_TIMELINE_V2=true" in workflow
    assert "STORY_MUSIC_AI_GENERATION_ENABLED" not in workflow
    assert "MINIMAX_TIMEOUT_SECONDS=180" in workflow
    assert "IMAGE_API_KEY" in workflow
    assert "IMAGE_API_BASE_URL=https://api.minimaxi.com/v1" in workflow
    assert "IMAGE_MODEL=image-01" in workflow
    assert "TEXT_TO_IMAGE_MODELS=image-01" in workflow
    assert "IMAGE_EDIT_MODELS=image-01,image-01-live" in workflow
    assert "sk-" not in workflow


def test_production_deploy_fetches_private_repo_without_persisting_github_token() -> None:
    workflow = (ROOT / ".github" / "workflows" / "deploy-production.yml").read_text(
        encoding="utf-8"
    )

    assert "GITHUB_DEPLOY_TOKEN_B64" in workflow
    assert "github.token" in workflow
    assert "x-access-token:${GITHUB_DEPLOY_TOKEN}@github.com" in workflow
    assert "git remote set-url origin https://github.com/cc-chen-tech/LifeDraft.git" in workflow
    assert "trap cleanup_git_remote EXIT" in workflow
    assert "unset GITHUB_DEPLOY_TOKEN_B64" in workflow
    assert workflow.index("x-access-token:${GITHUB_DEPLOY_TOKEN}@github.com") < workflow.index(
        "git fetch origin main"
    )
    assert workflow.index("git fetch origin main") < workflow.rindex(
        "git remote set-url origin https://github.com/cc-chen-tech/LifeDraft.git"
    )


def test_production_deploy_has_explicit_manual_local_preflight_override() -> None:
    workflow = (ROOT / ".github" / "workflows" / "deploy-production.yml").read_text(
        encoding="utf-8"
    )

    assert "force_after_local_preflight" in workflow
    assert "Local preflight passed and GitHub checks are unavailable" in workflow
    assert "'${{ github.event_name }}' === 'workflow_dispatch'" in workflow
    assert "core.warning('Manual production deployment is bypassing GitHub CI after local preflight.')" in workflow
    assert "return;" in workflow.split("Manual production deployment is bypassing GitHub CI", 1)[1].split(
        "const requiredWorkflows", 1
    )[0]


def test_env_example_documents_minimax_production_audio_settings() -> None:
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    required_lines = [
        "MINIMAX_API_KEY=",
        "MINIMAX_TTS_MODEL=speech-02-turbo",
        "MINIMAX_TIMEOUT_SECONDS=180",
        "MINIMAX_TTS_MAX_CHARS=50000",
        "STORY_TTS_PROVIDER=minimax",
        "STORY_TTS_AUTO_READ_DEFAULT_ENABLED=true",
        "ENABLE_DAILY_TIMELINE_V2=true",
        "STORY_TTS_ASSET_DIR=./data/voice_assets",
    ]
    for line in required_lines:
        assert line in env_example

    assert "sk-" not in env_example


def test_e2e_prod_frontend_start_waits_until_listening_in_ci() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")
    start_block = script.split("npm run start -- --hostname 127.0.0.1", 1)[1].split(
        "export CI=1", 1
    )[0]

    assert "for frontend_ready_attempt in" in start_block
    assert 'lsof -iTCP:"$frontend_port" -sTCP:LISTEN' in start_block
    assert 'cat "$FRONTEND_LOG"' in start_block
    assert "sleep 3\n        if ! lsof" not in start_block


def test_e2e_prod_frontend_start_uses_http_readiness_in_ci() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")
    start_block = script.split("npm run start -- --hostname 127.0.0.1", 1)[1].split(
        "export CI=1", 1
    )[0]

    assert 'curl -fsS "http://127.0.0.1:$frontend_port"' in start_block
    assert start_block.index('curl -fsS "http://127.0.0.1:$frontend_port"') < start_block.index(
        'kill -0 "$FRONTEND_PID"'
    )


def test_e2e_prod_frontend_disables_standalone_output_for_next_start() -> None:
    next_config = (ROOT / "frontend" / "next.config.ts").read_text(encoding="utf-8")
    script = (ROOT / "test.sh").read_text(encoding="utf-8")

    assert "process.env.NEXT_DISABLE_STANDALONE === '1'" in next_config
    assert "output: process.env.NEXT_DISABLE_STANDALONE === '1' ? undefined : 'standalone'" in next_config
    assert 'NEXT_DISABLE_STANDALONE=1 BACKEND_URL="$backend_url" NEXT_PUBLIC_API_URL="/api" npm run build' in script


def test_e2e_prod_frontend_explicitly_enables_regression_fixtures() -> None:
    script = (ROOT / "test.sh").read_text()

    assert "export ENABLE_E2E_REGRESSION_FIXTURES=1" in script
    assert 'NEXT_DISABLE_STANDALONE=1 BACKEND_URL="$backend_url" NEXT_PUBLIC_API_URL="/api" CI=1 E2E_FRONTEND_PORT="$frontend_port" npm run start' in script
    assert "npm run start -- --hostname 127.0.0.1" in script
    assert "node .next/standalone/server.js" not in script


def test_e2e_api_contract_probe_does_not_trigger_long_story_regeneration() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")
    story_router = (ROOT / "src" / "api" / "routers" / "story.py").read_text(encoding="utf-8")
    events_router = (
        ROOT / "src" / "api" / "routers" / "gameplay" / "events.py"
    ).read_text(encoding="utf-8")

    assert "E2E_CONTRACT_PROBE_FAST=1" in script
    assert "E2E_CONTRACT_PROBE_FAST" in story_router
    assert 'request.headers.get("x-e2e-contract-probe") == "1"' in story_router
    assert "API contract probe should not trigger story regeneration" in story_router
    assert "E2E_CONTRACT_PROBE_FAST" in events_router
    assert 'request.headers.get("x-e2e-contract-probe") == "1"' in events_router
    assert "API contract probe should not trigger event generation" in events_router


def test_daily_story_e2e_covers_high_quality_audio_without_music_fallback() -> None:
    spec = (ROOT / "frontend" / "e2e" / "daily-timeline.spec.ts").read_text(
        encoding="utf-8"
    )

    assert "selected paragraph" not in spec
    assert "从第 2 段开始朗读" in spec
    assert "narrationCalls" in spec
    assert "musicCalls" in spec
    assert "expect(musicCalls).toBe(0)" in spec
    assert "speechSynthesis" not in spec


def test_security_e2e_logout_uses_context_request_not_cross_origin_page_fetch() -> None:
    spec = (ROOT / "frontend" / "e2e" / "security.spec.ts").read_text(encoding="utf-8")
    logout_test = spec.split("test('logout actually invalidates session'")[1].split(
        "test('XSS in story content is escaped'"
    )[0]

    assert "context.request.post" in logout_test
    assert "context.request.get" in logout_test
    assert "page.evaluate(async (apiUrl)" not in logout_test
