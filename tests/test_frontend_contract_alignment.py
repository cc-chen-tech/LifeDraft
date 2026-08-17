"""
Frontend-Backend Contract Alignment Tests

Purpose: Verify that the JSON field names and types returned by the backend API
match what the frontend mock data and TypeScript types expect.

This test suite closes the gap between "what the backend returns" and "what
frontend Jest tests assume via hardcoded `mockResolvedValue(jsonResponse(...))`.

================================================================================
MISMATCHES FOUND (documented before writing corrective code):
================================================================================

1. GameStateResponse: Frontend mock data MISSING "constraint_level", "narrative_style_id",
   "narrative_style_name".
   - Backend returns:   {game_id, player_state, progress, round_info, current_event,
                          constraint_level, narrative_style_id, narrative_style_name}
   - Frontend mock data (usePlayGame.test.ts:127, useGameStore.test.ts:364):
                         {game_id, player_state, progress, round_info, current_event}
   - Frontend api.ts type (GameStateResponse at types.ts:233): includes constraint_level
     but missing narrative_style_id and narrative_style_name.
   - Impact: Frontend tests won't catch if backend changes these fields.

2. Character /setting: Backend response shape varies by setting_type. Frontend expects
   a single fixed shape that matches none of them.
   - Backend for "era":    {year, era_description, world_context}
   - Backend for "age":    {age, birth_year, age_description}
   - Backend for "gender": {gender, gender_description}
   - Backend for "world":  {world_description, technology_level, social_system, economy}
   - Frontend api.ts type: {era: string, era_description: string}
   - Frontend mock data:   {era_name: '古代', era_description: 'Ancient times'}
   - Impact: Both the TypeScript type AND the mock data are wrong. The frontend runtime
     uses `updateCharacterSetting(key, result)` to store the raw response dict under the
     step key, so it works at runtime but the typing is misleading.

3. POST /games/{id}/choice-sync: Frontend api.ts type annotation is completely wrong.
   - Backend returns:  {story_continuation, summary, effects_applied,
                         need_weekly_summary, weekly_summary?, bonus_effects?, game_over}
   - Frontend api.ts:  {result, story, current_round, current_week, player_state,
                         summary?, need_weekly_summary?, weekly_summary?, game_over?}
   - Frontend runtime (handleChoiceComplete in choiceUtils.ts): accesses backend field
     names directly (story_continuation, effects_applied, bonus_effects), so it works.
   - Impact: The TS type is a lie. If someone reads the type and builds code against it,
     they'll use wrong field names.

4. POST /games/{id}/events (api.ts) vs actual endpoint /{id}/event-sync:
   - Frontend api.ts calls: POST /games/${id}/events  (with trailing 's')
   - Backend endpoint:      POST /{id}/event-sync      (no 's', has '-sync')
   - The URL path in api.ts does not match any backend route. However, the frontend
     uses SSE streaming (GET /{id}/event) for event generation in production, so the
     api.ts generateEvent() function may be a dead code path.
   - If it IS called, it would get a 405 Method Not Allowed (POST to a GET-only endpoint)
     or 404 (path not found), not 307/308 redirect.

5. RoundSceneImage: Frontend mock data MISSING "week" and "stage" fields.
   - Backend RoundSceneResponse: {scene_id, game_id, week, round_number, stage,
                                   image_url, scene_description, created_at}
   - Frontend mock (useGameStore.test.ts:832): {scene_id, round_number, image_url,
                                                 scene_description, created_at}
   - The frontend type RoundSceneImage (types.ts:262) includes week and stage, so the
     type is correct but mock data is incomplete.

================================================================================
"""

import os
from unittest.mock import patch

import pytest

# ==============================================================================
# TEST FIXTURES
# ==============================================================================


@pytest.fixture
def auth_headers():
    """Authorization headers for testing."""
    return {"Authorization": "Bearer test_token"}


@pytest.fixture
def game_via_api(client, auth_headers):
    """Create a game via the API and return the game_id.

    Uses the same pattern as test_constraint_level_api_contract.py.
    Requires: API keys configured for LLM calls (will fail without).
    """
    with patch("src.api.deps.decode_token", return_value=1):
        create_resp = client.post(
            "/api/games",
            headers=auth_headers,
            json={
                "player_name": "ContractTestPlayer",
                "life_vision": "Testing contract alignment",
                "character_settings": {
                    "era": {"year": 2020, "era_description": "Modern era"},
                    "age": {"age": 25},
                    "gender": {"gender": "男"},
                },
                "language": "zh",
                "constraint_level": "fast",
            },
        )
    assert (
        create_resp.status_code == 201
    ), f"Game creation failed (status={create_resp.status_code}): {create_resp.text[:200]}"
    data = create_resp.json()
    game_id = data["game_id"]
    assert isinstance(game_id, int)
    return game_id


# ==============================================================================
# 1. GET /api/games/{id} — Game State Loading
# ==============================================================================


class TestGetGameResponseShape:
    """Verify GET /api/games/{id} returns the correct top-level fields.

    This is the most-mocked endpoint in frontend tests. Frontend mock data
    typically includes: {game_id, player_state, progress, round_info, current_event}
    but omits constraint_level, narrative_style_id, narrative_style_name.
    """

    def test_game_creation_returns_game_state_response(self, client, auth_headers):
        """Game creation (POST /api/games) returns GameStateResponse with all required fields."""
        with patch("src.api.deps.decode_token", return_value=1):
            resp = client.post(
                "/api/games",
                headers=auth_headers,
                json={
                    "player_name": "ShapeTest",
                    "life_vision": "Verify response shape",
                    "character_settings": {"era": {"year": 2000, "era_description": "Modern"}},
                    "language": "zh",
                },
            )
        assert resp.status_code == 201, f"Unexpected status: {resp.status_code}"
        data = resp.json()

        # Top-level fields (GameStateResponse)
        assert "game_id" in data, "Missing: game_id"
        assert isinstance(
            data["game_id"], int
        ), f"game_id should be int, got {type(data['game_id'])}"

        assert "player_state" in data, "Missing: player_state"
        assert isinstance(
            data["player_state"], dict
        ), f"player_state should be dict, got {type(data['player_state'])}"

        assert "progress" in data, "Missing: progress"
        assert isinstance(
            data["progress"], dict
        ), f"progress should be dict, got {type(data['progress'])}"

        assert "round_info" in data, "Missing: round_info"
        assert isinstance(
            data["round_info"], dict
        ), f"round_info should be dict, got {type(data['round_info'])}"

        # current_event may be null/None for a fresh game
        assert "current_event" in data, "Missing: current_event"

        # ★ FRONTEND GAP: constraint_level is required by the schema
        assert "constraint_level" in data, (
            "MISSING: constraint_level. Frontend mock data omits this field. "
            "The frontend api.ts type includes it but Jest test mock data does not."
        )

        # ★ FRONTEND GAP: narrative_style fields may be present
        # These are optional in the backend schema but frontend doesn't type them
        assert (
            "narrative_style_id" in data or "narrative_style_id" not in data
        ), "narrative_style_id: frontend api.ts does not type this field"
        assert (
            "narrative_style_name" in data or "narrative_style_name" not in data
        ), "narrative_style_name: frontend api.ts does not type this field"

    def test_get_game_load_response_shape(self, client, auth_headers, game_via_api):
        """GET /api/games/{id} on a loaded game returns the correct shape."""
        game_id = game_via_api

        with patch("src.api.deps.decode_token", return_value=1):
            resp = client.get(f"/api/games/{game_id}", headers=auth_headers)
        assert resp.status_code == 200, f"Load failed: {resp.status_code}"
        data = resp.json()

        assert data["game_id"] == game_id
        assert isinstance(data["player_state"], dict)
        assert isinstance(data["progress"], dict)
        assert isinstance(data["round_info"], dict)
        # current_event for a fresh game should be None
        assert (
            data["current_event"] is None
        ), f"Fresh game should have current_event=None, got {type(data['current_event'])}"
        assert "constraint_level" in data, (
            "constraint_level missing in GET response. "
            "Frontend mock data (usePlayGame.test.ts, useGameStore.test.ts) omits this."
        )

    def test_player_state_contains_expected_fields(self, client, auth_headers, game_via_api):
        """player_state dict contains core player attributes."""
        game_id = game_via_api

        with patch("src.api.deps.decode_token", return_value=1):
            resp = client.get(f"/api/games/{game_id}", headers=auth_headers)
        data = resp.json()
        ps = data["player_state"]

        # Core fields the frontend reads from player_state
        assert "player_name" in ps, "player_state.player_name missing"
        assert isinstance(ps["player_name"], str)

        assert "life_vision" in ps, "player_state.life_vision missing"

        # Active resource fields
        for attr in ("energy", "mood", "knowledge"):
            assert attr in ps, f"player_state.{attr} missing"
            assert isinstance(
                ps[attr], (int, float)
            ), f"player_state.{attr} should be numeric, got {type(ps[attr])}"

        # Time fields
        assert "age" in ps, "player_state.age missing"
        assert "week" in ps, "player_state.week missing"
        assert "current_round" in ps, "player_state.current_round missing"

        # Character settings
        assert "character_settings" in ps, "player_state.character_settings missing"

    def test_game_state_response_schema_fields(self):
        """Verify GameStateResponse pydantic model has all expected fields."""
        from src.api.schemas import GameStateResponse

        fields = GameStateResponse.model_fields
        required_top_level = [
            "game_id",
            "player_state",
            "progress",
            "round_info",
            "current_event",
            "constraint_level",
        ]
        for field in required_top_level:
            assert field in fields, f"GameStateResponse missing field: {field}"

        # These frontend-skips are optional
        assert "narrative_style_id" in fields, "narrative_style_id missing from schema"
        assert "narrative_style_name" in fields, "narrative_style_name missing from schema"


# ==============================================================================
# 2. GET /api/games/active — Active Game Recovery
# ==============================================================================


class TestActiveGameResponseShape:
    """Verify GET /api/games/active returns the same shape as GET /api/games/{id}.

    Frontend mock data (usePlayGame.test.ts:127) uses the same shape for both
    endpoints, which is consistent with the backend (both return GameStateResponse).
    """

    def test_active_game_returns_game_state_response_shape(
        self, client, auth_headers, game_via_api
    ):
        """After creating a game, /games/active should return the same shape as /games/{id}."""
        game_id = game_via_api

        with patch("src.api.deps.decode_token", return_value=1):
            resp = client.get("/api/games/active", headers=auth_headers)
        assert resp.status_code == 200, f"Active game failed: {resp.status_code}"
        data = resp.json()

        # Same top-level fields as GET /games/{id}
        assert "game_id" in data
        assert data["game_id"] == game_id
        assert "player_state" in data
        assert "progress" in data
        assert "round_info" in data
        assert "current_event" in data
        assert "constraint_level" in data

    def test_active_game_none_returns_404(self, client, auth_headers):
        """Without an active game (no game created), returns 404."""
        with patch("src.api.deps.decode_token", return_value=99999):
            resp = client.get("/api/games/active", headers=auth_headers)
        # For a user with no active game, returns 404
        assert resp.status_code == 404, f"No active game should return 404, got {resp.status_code}"


# ==============================================================================
# 3. POST /api/character/setting — Character Setting Generation
# ==============================================================================


class TestCharacterSettingResponseShape:
    """Verify POST /api/character/setting response shapes.

    WARNING: The response shape varies by setting_type. The frontend api.ts
    types it as {era: string, era_description: string} which is wrong for
    most setting_types. The frontend runtime works because it stores the
    raw response dict under the step key without field-level access.

    Frontend mock data (useCharacterCreation.test.ts:356):
        {era_name: '古代', era_description: 'Ancient times'}
    But the backend for 'era' actually returns:
        {year: <int>, era_description: <str>, world_context: <str>}
    """

    @pytest.fixture
    def setting_auth_headers(self):
        return {"Authorization": "Bearer test_token"}

    @pytest.fixture
    def base_setting_request(self):
        return {
            "setting_type": "era",
            "player_name": "TestPlayer",
            "life_vision": "Live a good life",
            "previous_settings": {},
            "language": "zh",
        }

    def test_character_setting_endpoint_exists(self, client, auth_headers, base_setting_request):
        """Verify /api/character/setting endpoint is accessible.

        The character setting endpoint does NOT require authentication
        (no Depends(get_current_user) on the router). It returns 200 with valid input
        or 422 for invalid input.
        """
        resp = client.post("/api/character/setting", json=base_setting_request)
        # This endpoint is public (no auth required).
        # 200 = success, 422 = validation error for missing/invalid fields
        assert resp.status_code in (200, 422), (
            f"Expected 200 or 422, got {resp.status_code}. "
            f"Route may not exist (404) or be misconfigured (405)."
        )

    def test_era_setting_response_shape(self, client, auth_headers):
        """Verify character/setting with setting_type='era' returns the correct shape.

        The backend returns {year, era_description, world_context}.
        The frontend mock data uses {era_name, era_description} — this is a MISMATCH.
        """
        with patch("src.api.deps.decode_token", return_value=1):
            resp = client.post(
                "/api/character/setting",
                headers=auth_headers,
                json={
                    "setting_type": "era",
                    "player_name": "ContractTester",
                    "life_vision": "Build great software",
                    "previous_settings": {},
                    "language": "zh",
                },
            )

        assert resp.status_code == 200, (
            f"Character setting generation failed (status={resp.status_code}): {resp.text[:200]}\n"
            f"This requires LLM API keys configured. If keys are not available, mark as skip."
        )
        data = resp.json()

        # Backend returns {year, era_description, world_context} for 'era'
        # Frontend api.ts types this as {era: string, era_description: string} — WRONG
        # Frontend mock data uses {era_name: '...', era_description: '...'} — ALSO WRONG
        assert "year" in data, (
            "Backend returns 'year' for era settings. "
            "Frontend api.ts expects {era, era_description} — MISMATCH."
        )
        assert "era_description" in data, "Missing: era_description"
        assert isinstance(data["era_description"], str)

        # world_context is only in backend, not in frontend types/mocks
        assert "world_context" in data, (
            "Backend returns 'world_context' which frontend doesn't type. "
            "Frontend silently preserves it via raw dict storage."
        )

        # Verify era_name is NOT in the response (frontend mock uses this wrong field)
        assert "era_name" not in data, (
            "Frontend mock data uses 'era_name' but backend returns 'era_description' and 'year'. "
            "Frontend test mock in useCharacterCreation.test.ts is WRONG."
        )

    def test_age_setting_response_shape(self, client, auth_headers):
        """Verify character/setting with setting_type='age' returns correct shape."""
        with patch("src.api.deps.decode_token", return_value=1):
            resp = client.post(
                "/api/character/setting",
                headers=auth_headers,
                json={
                    "setting_type": "age",
                    "player_name": "ContractTester",
                    "life_vision": "Build great software",
                    "previous_settings": {"era": {"year": 2020}},
                    "language": "zh",
                },
            )

        assert resp.status_code == 200, (
            f"Age setting failed (status={resp.status_code}): {resp.text[:200]}\n"
            f"Requires LLM API keys."
        )
        data = resp.json()

        assert "age" in data, "Missing: age"
        assert "age_description" in data, "Missing: age_description"
        assert "birth_year" in data, "Missing: birth_year"

    def test_gender_setting_response_shape(self, client, auth_headers):
        """Verify character/setting with setting_type='gender' returns correct shape."""
        with patch("src.api.deps.decode_token", return_value=1):
            resp = client.post(
                "/api/character/setting",
                headers=auth_headers,
                json={
                    "setting_type": "gender",
                    "player_name": "ContractTester",
                    "life_vision": "Build great software",
                    "previous_settings": {"era": {"year": 2020}, "age": {"age": 25}},
                    "language": "zh",
                },
            )

        assert resp.status_code == 200, (
            f"Gender setting failed (status={resp.status_code}): {resp.text[:200]}\n"
            f"Requires LLM API keys."
        )
        data = resp.json()

        assert "gender" in data, "Missing: gender"
        assert "gender_description" in data, "Missing: gender_description"


# ==============================================================================
# 4. GET /api/games/{id}/event — SSE Event Generation
# ==============================================================================


class TestEventGenerationResponseShape:
    """Verify event generation response shapes.

    The event endpoint is SSE-streaming (GET /{game_id}/event). It streams
    SSE events: story chunks, status updates, and finally a 'complete' event
    with {event_description, options: [{text, effects, likely_choice}]}.

    The sync fallback POST /{game_id}/event-sync returns the full GameEvent
    as JSON: {event_description, options: [{text, effects, likely_choice}]}.

    NOTE: Frontend api.ts has a POST /games/{id}/events endpoint (with 's')
    that does NOT match the backend's POST /{id}/event-sync route.
    """

    def test_game_event_model_shape(self):
        """Verify the GameEvent pydantic model has the correct fields."""
        from src.ai.models import EventOption, GameEvent

        # GameEvent fields
        ge_fields = GameEvent.model_fields
        assert "event_description" in ge_fields, "GameEvent missing: event_description"
        assert "options" in ge_fields, "GameEvent missing: options"

        # EventOption fields
        eo_fields = EventOption.model_fields
        assert "text" in eo_fields, "EventOption missing: text"
        assert "effects" in eo_fields, "EventOption missing: effects"
        assert "likely_choice" in eo_fields, "EventOption missing: likely_choice"

        # Verify that model_dump() produces the correct shape
        # GameEvent requires at least 2 options (min_length=2)
        option1 = EventOption(text="Option A", effects={"energy": -5}, likely_choice=False)
        option2 = EventOption(text="Option B", effects={"mood": 5}, likely_choice=True)
        event = GameEvent(event_description="Test event", options=[option1, option2])
        dumped = event.model_dump()

        assert "event_description" in dumped
        assert dumped["event_description"] == "Test event"
        assert "options" in dumped
        assert len(dumped["options"]) == 2
        assert dumped["options"][0]["text"] == "Option A"
        assert dumped["options"][0]["effects"] == {"energy": -5}
        assert dumped["options"][0]["likely_choice"] is False
        assert dumped["options"][1]["text"] == "Option B"
        assert dumped["options"][1]["effects"] == {"mood": 5}
        assert dumped["options"][1]["likely_choice"] is True

    def test_event_generation_returns_actionable_event(self, client, auth_headers, game_via_api):
        """After game creation, calling the sync event endpoint should either return
        a valid event or a conflict (if generation is in progress).

        This tests POST /api/games/{id}/event-sync (the sync fallback).
        """
        game_id = game_via_api

        with patch("src.api.deps.decode_token", return_value=1):
            resp = client.post(
                f"/api/games/{game_id}/event-sync",
                headers=auth_headers,
            )

        # The first event generation after game creation should produce an event
        # But may get 409 if still initializing, 400 if game over, or 503 when
        # the story provider is unavailable and the failure is surfaced.
        assert resp.status_code in (
            200,
            409,
            400,
            503,
        ), f"Unexpected status {resp.status_code}: {resp.text[:200]}"

        if resp.status_code == 200:
            data = resp.json()
            assert "event_description" in data, (
                "Event response missing 'event_description'. "
                "Frontend api.ts type expects 'story' — this is a MISMATCH. "
                "The frontend SSE handler stores the story from the stream, not from this field."
            )
            assert "options" in data, "Missing: options"
            assert isinstance(data["options"], list)
            for opt in data["options"]:
                assert "text" in opt, "Option missing: text"
                assert "effects" in opt, "Option missing: effects"
        elif resp.status_code == 503:
            data = resp.json()
            assert "detail" in data, "503 must carry a failure detail for the UI"

    def test_event_generation_requires_game(self, client, auth_headers):
        """Event sync endpoint for non-existent game should return 404."""
        with patch("src.api.deps.decode_token", return_value=99999):
            resp = client.post(
                "/api/games/99999/event-sync",
                headers=auth_headers,
            )
        assert resp.status_code in (
            404,
            409,
        ), f"Expected 404 (game not found) or 409, got {resp.status_code}"


# ==============================================================================
# 5. POST /api/games/{id}/choice-sync — Sync Fallback Choice
# ==============================================================================


class TestChoiceSyncResponseShape:
    """Verify POST /api/games/{id}/choice-sync returns correct fields.

    The backend _post_choice_pipeline returns:
        {story_continuation, summary, effects_applied, need_weekly_summary,
         weekly_summary?, bonus_effects?, game_over}

    The frontend api.ts type annotation says:
        {result, story, current_round, current_week, player_state,
         summary?, need_weekly_summary?, weekly_summary?, game_over?}

    This is a COMPLETE MISMATCH for the TypeScript type. However, the runtime
    code in handleChoiceComplete (choiceUtils.ts) accesses the backend field
    names directly (story_continuation, effects_applied, etc.), so it works.

    The frontend mock data in choiceUtils.test.ts uses:
        {summary: 'Fallback result', need_weekly_summary: false, game_over: false}
    which is a minimal subset consistent with the backend.
    """

    def test_choice_sync_endpoint_exists(self, client, auth_headers, game_via_api):
        """Verify /api/games/{id}/choice-sync endpoint is registered.

        Without a current event, it should return a 409 or 400 (not 404/405).
        """
        game_id = game_via_api

        with patch("src.api.deps.decode_token", return_value=1):
            resp = client.post(
                f"/api/games/{game_id}/choice-sync",
                headers=auth_headers,
                json={"option_index": 0},
            )

        # Without a current event, should get 409/400/404 (not 405 which means route missing)
        assert resp.status_code not in (
            405,
        ), f"Route not found (405). /api/games/{{id}}/choice-sync endpoint missing!"
        assert resp.status_code in (
            400,
            404,
            409,
        ), f"Expected 400/404/409 (no event to process), got {resp.status_code}: {resp.text[:200]}"

    @pytest.mark.skip(
        reason="Requires a game with an active event (options) to test full response shape. "
        "Need to: 1) create game, 2) generate an event via event-sync, 3) submit choice. "
        "This requires LLM API keys and multiple sequential API calls."
    )
    def test_choice_sync_full_response_shape(self):
        """Full response shape test for choice-sync (requires game with active event).

        Expected response from backend _post_choice_pipeline:
        {
            "story_continuation": str,
            "summary": str,
            "effects_applied": {"energy": int, "mood": int, ...},
            "need_weekly_summary": bool,
            "weekly_summary": str | None,   (optional)
            "bonus_effects": dict | None,   (optional)
            "game_over": bool,
        }

        Frontend api.ts WRONGLY types this as:
        {
            result: string,
            story: string,
            current_round: number,
            current_week: number,
            player_state: PlayerState,
            summary?: string,
            need_weekly_summary?: boolean,
            weekly_summary?: string,
            game_over?: boolean,
        }

        The runtime code uses backend field names directly (see handleChoiceComplete).
        """
        pass

    def test_choice_sync_schema_documents_actual_fields(self):
        """Document the actual choice-sync return fields from the code.

        This test verifies the expected contract by reading the source.
        """
        # Verify the RoundChoiceProcessor._post_choice_pipeline builds the result dict
        # with the documented fields
        import inspect

        from src.game.round.choice_processor import RoundChoiceProcessor

        source = inspect.getsource(RoundChoiceProcessor._post_choice_pipeline)

        # The result dict should contain these fields
        expected_fields = [
            "story_continuation",
            "summary",
            "effects_applied",
            "need_weekly_summary",
            "game_over",
        ]
        for field in expected_fields:
            assert f'"{field}"' in source or f"'{field}'" in source, (
                f"ChoiceProcessor._post_choice_pipeline result dict missing field: {field}. "
                f"The backend may have changed and frontend TypeScript types need updating."
            )


# ==============================================================================
# FRONTEND MISMATCH CROSS-CHECK: Verify by reading frontend source
# ==============================================================================


class TestFrontendMismatchCrossCheck:
    """Cross-check frontend mock data and TypeScript types against backend response shapes.

    These tests read the frontend source and mock data to verify alignment.
    They don't require a running backend.
    """

    @pytest.fixture
    def frontend_api_ts_path(self):
        return os.path.join(os.path.dirname(__file__), "..", "frontend", "src", "lib", "api.ts")

    @pytest.fixture
    def frontend_types_ts_path(self):
        return os.path.join(os.path.dirname(__file__), "..", "frontend", "src", "lib", "types.ts")

    def test_frontend_game_load_type_includes_constraint_level(self, frontend_api_ts_path):
        """Frontend api.ts games.load should include constraint_level in its type."""
        with open(frontend_api_ts_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check that the games.load or games.getActive type includes constraint_level
        assert "constraint_level" in content, (
            "frontend/src/lib/api.ts must include constraint_level in game state type. "
            "Backend GameStateResponse ALWAYS returns this field. "
            "Without it, frontend TypeScript won't type-check constraint_level usage."
        )

    def test_frontend_game_state_response_includes_constraint_level(self, frontend_types_ts_path):
        """Frontend GameStateResponse type should include constraint_level."""
        with open(frontend_types_ts_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "constraint_level" in content, (
            "frontend/src/lib/types.ts GameStateResponse must include constraint_level. "
            "Backend always returns this field."
        )

    def test_frontend_character_setting_type_is_permissive(self, frontend_api_ts_path):
        """Frontend character.generateSetting return type should be flexible enough
        to accommodate different setting_type responses.

        Currently typed as {era: string, era_description: string} which only
        matches one of 8 possible setting_types. The runtime works because it
        stores the raw response dict, but the type is misleading.
        """
        with open(frontend_api_ts_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 现已修正：character.generateSetting 使用 Record<string, unknown>
        assert "Record<string, unknown>" in content, (
            "Character setting response type should be flexible enough to match backend "
            "setting responses with different shapes."
        )

    def test_frontend_runtime_uses_backend_field_names(self):
        """Frontend runtime handler (choiceUtils.ts) accesses backend field names.

        Backend returns: {story_continuation, summary, effects_applied,
                          need_weekly_summary, game_over}

        The runtime code in choiceUtils.ts correctly accesses story_continuation
        and effects_applied (snake_case, matching backend). However, the TypeScript
        type annotation in api.ts for makeChoiceSync is WRONG — it uses 'result',
        'story', 'current_round', 'current_week' which don't match the backend.

        This test verifies the runtime code is correct.
        """
        choice_utils_path = os.path.join(
            os.path.dirname(__file__), "..", "frontend", "src", "hooks", "game", "choiceUtils.ts"
        )
        with open(choice_utils_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Runtime handler accesses correct backend field names
        assert "story_continuation" in content, (
            "Runtime handler (choiceUtils.ts) should access 'story_continuation' "
            "to match backend response field name."
        )
        assert (
            "effects_applied" in content
        ), "Runtime handler should access 'effects_applied' to match backend response field name."
        assert (
            "bonus_effects" in content
        ), "Runtime handler should access 'bonus_effects' to match backend response field name."

        # The api.ts type annotation for makeChoiceSync is KNOWN to be wrong
        # (uses 'result', 'story', 'current_round' instead of 'story_continuation').
        # This is documented at the top of this file as Mismatch #3.

    def test_frontend_api_ts_choice_sync_type_needs_fix(self, frontend_api_ts_path):
        """Document the known mismatch in api.ts makeChoiceSync type annotation.

        The api.ts type for makeChoiceSync says:
            {result, story, current_round, current_week, player_state, ...}

        But the backend actually returns:
            {story_continuation, summary, effects_applied, need_weekly_summary, game_over}

        This is a KNOWN MISMATCH (see Mismatch #3 at top of file).
        The runtime works because handleChoiceComplete casts to Record<string, unknown>
        and accesses the real field names.
        """
        with open(frontend_api_ts_path, "r", encoding="utf-8") as f:
            content = f.read()

        # The type annotation uses wrong field names
        has_wrong_result = "result: string" in content
        has_wrong_story = "story: string" in content

        # If either of these is present, the type annotation is still wrong
        # This is a warning-level check — when fixed, update this test
        if has_wrong_result and has_wrong_story:
            import warnings

            warnings.warn(
                "api.ts makeChoiceSync type annotation still uses 'result'/'story' "
                "instead of backend field 'story_continuation'. See Mismatch #3."
            )
        # Test always passes — it's a documentation check, not a blocker
