"""Early no-mock checks that should fail before slower DB/E2E layers."""

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
    assert "tests/test_music_degradation_no_mock.py" in script
    assert "tests/test_shift_left_e2e_contract_no_mock.py" in script
    assert "storyContinuityPreflight.test.tsx" in script
    assert "src/__tests__/lib/sse.test.ts" in script
    assert "python -m flake8 src/services/story_voice_reading.py" in script
    assert "python scripts/export_openapi.py" in script
    assert "git diff --exit-code -- frontend/src/types/openapi-schema.json" in script
    assert script.index("run_preflight || ((failed++))") < script.index("run_mypy || ((failed++))")
    assert script.index("run_preflight || ((failed++))") < script.index(
        "run_e2e_browser || ((failed++))"
    )


def test_playwright_log_tempfile_template_has_enough_random_suffix() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")

    assert 'mktemp "/tmp/story2-playwright-${label}-XXXXXX.log"' in script
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


def test_preflight_validates_minimax_story_audio_generation_change() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")
    change_dir = ROOT / "openspec" / "changes" / "add-minimax-story-audio-generation"

    assert change_dir.exists()
    assert (change_dir / "proposal.md").exists()
    assert (change_dir / "design.md").exists()
    assert (change_dir / "tasks.md").exists()
    assert "openspec validate add-minimax-story-audio-generation --strict" in script
    assert "tests/test_minimax_audio_generation_contract.py" in script
    assert "tests/test_minimax_audio_generation_db.py" in script
    assert "e2e/minimax-story-audio-generation.spec.ts" in script


def test_minimax_api_key_is_not_committed_to_repository_files() -> None:
    scanned_suffixes = {".py", ".ts", ".tsx", ".js", ".jsx", ".md", ".yml", ".yaml", ".sh"}
    allowed_dirs = {".git", ".next", "node_modules", "venv", "test-results", "playwright-report"}
    leaked_paths: list[str] = []

    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in scanned_suffixes:
            continue
        if any(part in allowed_dirs for part in path.relative_to(ROOT).parts):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        token_prefix = "sk-" + "cp-"
        if token_prefix in text:
            leaked_paths.append(str(path.relative_to(ROOT)))

    assert leaked_paths == []


def test_e2e_gate_does_not_reuse_frontend_from_other_worktree() -> None:
    script = (ROOT / "test.sh").read_text(encoding="utf-8")
    config = (ROOT / "frontend" / "playwright.config.ts").read_text(encoding="utf-8")

    assert "ensure_e2e_frontend_port_available" in script
    assert 'local frontend_port="${E2E_FRONTEND_PORT:-3000}"' in script
    assert "export E2E_FRONTEND_PORT" in script
    assert "占用 3000 端口的前端不属于当前 worktree" in script
    assert script.index("ensure_e2e_frontend_port_available") < script.index(
        "npx playwright test --project=core"
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
        assert "toContain('localhost:3000')" not in spec


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
    assert "E2E_BACKEND_HOST=127.0.0.1 E2E_BACKEND_PORT=8000" in script
    assert "关闭当前 8000 端口遗留后端进程" in script
    assert "MINIMAX_E2E_LOCAL_AUDIO=1" in script
    assert "E2E_FRONTEND_MODE:-prod" in script
    assert "npm run start -- --hostname 127.0.0.1" in script
    assert "if ! [ -d \".next\" ]" not in script
    assert "ulimit -n 8192" in script


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
    fixture = (ROOT / "frontend" / "src" / "app" / "e2e-regression" / "page.tsx").read_text(
        encoding="utf-8"
    )
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


def test_regression_fixture_does_not_hit_real_music_recommendation_by_default() -> None:
    fixture = (ROOT / "frontend" / "src" / "app" / "e2e-regression" / "page.tsx").read_text(
        encoding="utf-8"
    )

    assert "autoFetchRecommendation={false}" in fixture


def test_frontend_image_generation_path_is_checked_before_e2e() -> None:
    api_source = (ROOT / "frontend" / "src" / "lib" / "api.ts").read_text(encoding="utf-8")

    assert (
        "fetchJson<{ images: Array<{ image_id: number; image_url: string }>; total: number }>('/images/generate'"
        in api_source
    )
    assert "fetchJson('/images'" not in api_source


def test_api_runtime_files_remain_python39_import_compatible() -> None:
    router_source = (ROOT / "src" / "api" / "routers" / "friends.py").read_text(
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
    ui_test = spec.split('test("选择后显示资源变化"')[1].split('test("同步选择 API 返回 effects_applied"')[0]

    assert "seedEventForGame" in spec
    assert "await seedEventForGame(context, gameId);" in ui_test
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
        ROOT / "frontend" / "src" / "components" / "game" / "StoryVoiceControls.tsx"
    ).read_text(encoding="utf-8")
    play_page = (ROOT / "frontend" / "src" / "app" / "play" / "page.tsx").read_text(
        encoding="utf-8"
    )
    regression_page = (
        ROOT / "frontend" / "src" / "app" / "e2e-regression" / "page.tsx"
    ).read_text(encoding="utf-8")

    assert "showTestControls?: boolean" in component
    assert "showTestControls = false" in component
    assert "enablePlaybackControls?: boolean" in component
    assert "enablePlaybackControls = false" in component
    assert "{showTestControls &&" in component
    assert "enablePlaybackControls" in play_page
    assert "showTestControls" not in play_page
    assert "showTestControls" in regression_page


def test_story_voice_production_controls_expose_persistent_auto_read_toggle() -> None:
    component = (
        ROOT / "frontend" / "src" / "components" / "game" / "StoryVoiceControls.tsx"
    ).read_text(encoding="utf-8")

    auto_read_label = 'aria-label={autoReadEnabled ? "关闭自动朗读" : "启用自动朗读"}'
    assert auto_read_label in component
    assert "api.voice_reading.getSettings" in component
    assert "api.voice_reading.updateSettings" in component
    assert "settings.auto_read_enabled" in component
    assert component.index(auto_read_label) < component.index("{showTestControls &&")


def test_story_voice_production_controls_expose_voice_selection() -> None:
    component = (
        ROOT / "frontend" / "src" / "components" / "game" / "StoryVoiceControls.tsx"
    ).read_text(encoding="utf-8")
    store = (ROOT / "frontend" / "src" / "stores" / "useStoryVoiceStore.ts").read_text(
        encoding="utf-8"
    )

    assert 'aria-label="选择朗读声音"' in component
    assert "warm_female" in component
    assert "calm_male" in component
    assert "clear_neutral" in component
    assert "selectedVoiceId" in store
    assert "settings.selected_voice_color" in component
    assert 'voice_id: get().selectedVoiceId' in store
    assert 'voice_id: "warm_female"' not in store


def test_story_voice_production_settings_do_not_duplicate_test_controls() -> None:
    component = (
        ROOT / "frontend" / "src" / "components" / "game" / "StoryVoiceControls.tsx"
    ).read_text(encoding="utf-8")

    assert "const showProductionSettings = !showTestControls;" in component
    assert "{showProductionSettings && (" in component
    assert component.index("{showProductionSettings && (") < component.index("{showTestControls &&")


def test_global_music_player_autogenerates_music_from_completed_story_when_collapsed() -> None:
    global_player = (
        ROOT / "frontend" / "src" / "components" / "game" / "GlobalMusicPlayer.tsx"
    ).read_text(encoding="utf-8")

    assert "const shouldAutoFetchRecommendation" in global_player
    assert "activeStoryText" in global_player
    assert "effectiveGameId" in global_player
    assert "autoFetchRecommendation={shouldAutoFetchRecommendation}" in global_player
    assert "autoFetchRecommendation={isExpanded}" not in global_player


def test_regression_fixture_does_not_autogenerate_global_ai_music() -> None:
    fixture = (ROOT / "frontend" / "src" / "app" / "e2e-regression" / "page.tsx").read_text(
        encoding="utf-8"
    )

    assert "setActiveStoryText(" in fixture
    assert "setActiveGameId(null);" in fixture
    assert "setActiveGameId(101);" not in fixture


def test_play_page_missing_game_state_has_actionable_recovery_ui() -> None:
    play_page = (ROOT / "frontend" / "src" / "app" / "play" / "page.tsx").read_text(
        encoding="utf-8"
    )

    assert "正在恢复当前进度" in play_page
    assert "返回首页" in play_page
    assert "window.location.reload()" in play_page
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

    assert "STORY_TTS_PROVIDER=local" in workflow
    assert "STORY_TTS_ALLOW_REQUEST_PROVIDER=1" in workflow
    assert "MINIMAX_E2E_LOCAL_AUDIO=1" in workflow
    assert "MINIMAX_API_KEY=test-key" in workflow


def test_story_voice_browser_fallback_e2e_accepts_real_browser_speech_capability() -> None:
    spec = (ROOT / "frontend" / "e2e" / "story-voice-reading.spec.ts").read_text(
        encoding="utf-8"
    )
    fallback_test = spec.split(
        "uses browser speech fallback with the actual story text when backend audio is unavailable"
    )[1].split("test('auto-read supersedes stale regenerated attempts", 1)[0]

    assert "const fallbackState = await expectBrowserSpeechAttempt(page);" in fallback_test
    assert "if (fallbackState === 'playing')" in fallback_test
    assert "speechSynthesis" in fallback_test


def test_security_e2e_logout_uses_context_request_not_cross_origin_page_fetch() -> None:
    spec = (ROOT / "frontend" / "e2e" / "security.spec.ts").read_text(encoding="utf-8")
    logout_test = spec.split("test('logout actually invalidates session'")[1].split(
        "test('XSS in story content is escaped'"
    )[0]

    assert "context.request.post" in logout_test
    assert "context.request.get" in logout_test
    assert "page.evaluate(async (apiUrl)" not in logout_test
