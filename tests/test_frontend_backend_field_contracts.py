"""Frontend/backend field contract gates for browser-visible payloads.

These tests intentionally inspect backend schemas, generated OpenAPI artifacts,
hand-written frontend types, and high-use frontend fixtures in one place. They
catch field drift before browser E2E has to discover it.
"""

import json
import re
from pathlib import Path

from src.api.routers.gameplay.sse_helpers import make_sse_event
from src.api.schemas import GameStateResponse, RoundSceneResponse

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"
FRONTEND_TYPES = (FRONTEND / "lib" / "types.ts").read_text(encoding="utf-8")
FRONTEND_API = (FRONTEND / "lib" / "api.ts").read_text(encoding="utf-8")
API_BRIDGE = (FRONTEND / "types" / "api-bridge.ts").read_text(encoding="utf-8")
API_GENERATED = (FRONTEND / "types" / "api-generated.d.ts").read_text(encoding="utf-8")
OPENAPI_SCHEMA = json.loads(
    (FRONTEND / "types" / "openapi-schema.json").read_text(encoding="utf-8")
)


def _schema_properties(name: str) -> set[str]:
    return set(OPENAPI_SCHEMA["components"]["schemas"][name]["properties"].keys())


def _extract_fetch_json_contract(function_name: str) -> str:
    match = re.search(
        rf"{function_name}:\s*\([^)]*\)\s*=>\s*\n\s*fetchJson<\{{(?P<body>.*?)\}}>",
        FRONTEND_API,
        re.DOTALL,
    )
    assert match, f"Could not locate fetchJson contract for {function_name}"
    return match.group("body")


def _assert_source_has_fields(path: Path, fields: set[str]) -> None:
    source = path.read_text(encoding="utf-8")
    missing = [field for field in sorted(fields) if field not in source]
    assert not missing, f"{path.relative_to(ROOT)} is missing field tokens: {missing}"


def _assert_ts_field(source: str, field: str) -> None:
    assert re.search(rf"\b{re.escape(field)}\??:", source), f"Missing TS field {field}"


def test_game_state_fields_align_across_backend_openapi_and_frontend_types() -> None:
    required = {
        "game_id",
        "player_state",
        "progress",
        "round_info",
        "current_event",
        "constraint_level",
        "narrative_style_id",
        "narrative_style_name",
    }

    assert required <= set(GameStateResponse.model_fields)
    assert required <= _schema_properties("GameStateResponse")
    assert "export type ApiGameStateResponse = Schemas['GameStateResponse']" in API_BRIDGE

    for field in required:
        _assert_ts_field(FRONTEND_TYPES, field)
        _assert_ts_field(API_GENERATED, field)


def test_round_scene_fields_align_across_backend_openapi_and_frontend_types() -> None:
    required = {
        "scene_id",
        "game_id",
        "week",
        "round_number",
        "stage",
        "image_url",
        "scene_description",
        "created_at",
    }

    assert required <= set(RoundSceneResponse.model_fields)
    assert required <= _schema_properties("RoundSceneResponse")
    assert "export type ApiRoundSceneResponse = Schemas['RoundSceneResponse']" in API_BRIDGE

    # The frontend display type does not need game_id, but it must keep week/stage
    # so saved/history scene images refresh the correct visual state.
    for field in required - {"game_id"}:
        _assert_ts_field(FRONTEND_TYPES, field)
        _assert_ts_field(API_GENERATED, field)


def test_choice_sync_frontend_contract_uses_backend_field_names() -> None:
    for function_name in ("makeChoiceSync", "makeCustomChoiceSync"):
        contract = _extract_fetch_json_contract(function_name)
        assert "story_continuation:" in contract
        assert "effects_applied:" in contract
        assert "need_weekly_summary:" in contract
        assert "weekly_summary?:" in contract

        stale_fields = ("result:", "story:", "current_round:", "current_week:", "player_state:")
        for field in stale_fields:
            assert field not in contract, f"{function_name} exposes stale field {field}"


def test_character_setting_frontend_contract_does_not_claim_stale_era_shape() -> None:
    type_line = next(
        line for line in FRONTEND_API.splitlines() if line.startswith("type CharacterSettingResponse")
    )
    assert "Record<string, unknown>" in type_line
    assert "era_name" not in type_line

    api_test = (FRONTEND / "__tests__" / "lib" / "api.test.ts").read_text(encoding="utf-8")
    for field in ("year", "era_description", "world_context"):
        assert field in api_test
    assert "expect(result.era_name).toBeUndefined()" in api_test


def test_high_use_frontend_mocks_include_game_state_and_scene_image_contract_fields() -> None:
    _assert_source_has_fields(
        FRONTEND / "__tests__" / "preflight" / "browserExplorationRegressionPreflight.test.tsx",
        {"constraint_level", "narrative_style_id", "narrative_style_name"},
    )

    scene_fixture_files = [
        FRONTEND / "__tests__" / "pages" / "PlayPage.test.tsx",
        FRONTEND / "__tests__" / "components" / "RoundSceneImage.test.tsx",
        FRONTEND / "__tests__" / "stores" / "useGameStore.test.ts",
        FRONTEND / "__tests__" / "stores" / "useSceneImageStore.test.ts",
    ]
    for path in scene_fixture_files:
        _assert_source_has_fields(path, {"week", "stage", "round_number", "image_url"})


def test_gameplay_sse_payload_contract_keeps_parser_facing_keys_stable() -> None:
    status = make_sse_event("status", {"phase": "preparing"})
    story = make_sse_event("story", {"content": "故事片段"})
    complete = make_sse_event(
        "complete",
        {
            "event_description": "故事完成",
            "options": [{"text": "继续", "effects": {"energy": -1}}],
        },
    )
    error = make_sse_event("error", {"error": "Generation timeout", "message": "retry"})

    assert "event: status" in status and '"phase"' in status
    assert "event: story" in story and '"content"' in story
    assert "event: complete" in complete
    assert '"event_description"' in complete and '"options"' in complete
    assert "event: error" in error
    assert '"error"' in error and '"message"' in error


def test_scene_image_sse_payload_contract_is_documented_in_existing_gate() -> None:
    scene_sse_test = (ROOT / "tests" / "test_scene_image_sse_contract.py").read_text(
        encoding="utf-8"
    )
    for event_type in ("scene_image_ready", "scene_image_failed", "heartbeat"):
        assert event_type in scene_sse_test
    for field in (
        "game_id",
        "round_number",
        "week",
        "stage",
        "image_url",
        "scene_description",
        "timestamp",
        "error",
    ):
        assert f'"{field}"' in scene_sse_test
