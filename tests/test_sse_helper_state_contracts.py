"""Provider-free SSE event and round-identity contracts."""

import json

from src.api.routers.gameplay.sse_helpers import (
    build_event_generation_key,
    clear_sse_cache_if_retry,
    make_sse_event,
)
from src.game.state import PlayerState


class _CacheSession:
    def __init__(self):
        self.clear_count = 0

    def clear_sse_cache(self):
        self.clear_count += 1


class _GameLoop:
    def __init__(self, player_state):
        self.player_state = player_state


def test_sse_event_preserves_optional_id_and_unicode_payload_as_json():
    payload = {"phase": "generating", "message": "林岚正在整理旧档案"}

    event = make_sse_event("status", payload, event_id=42)

    lines = event.strip().splitlines()
    assert lines[:2] == ["id: 42", "event: status"]
    assert json.loads(lines[2].removeprefix("data: ")) == payload


def test_sse_retry_only_clears_cache_for_the_retry_phase():
    session = _CacheSession()

    clear_sse_cache_if_retry({"phase": "generating"}, session)
    clear_sse_cache_if_retry({"phase": "retry"}, session)
    clear_sse_cache_if_retry({"phase": "retrying"}, session)
    clear_sse_cache_if_retry({"phase": "retry"}, None)

    assert session.clear_count == 1


def test_event_generation_key_uses_current_week_round_and_fixed_event_stage():
    loop = _GameLoop(PlayerState(week=9, current_round=2))

    key = build_event_generation_key(17, loop)

    assert (key.game_id, key.week, key.round_number, key.stage) == (17, 9, 2, "event")
