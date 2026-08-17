from __future__ import annotations

from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.game.character_creation import CharacterCreator

pytestmark = [pytest.mark.unit]



class DeterministicOriginGenerator:
    def __init__(self, results: List[Dict[str, Any]]) -> None:
        self.results = list(results)
        self.calls = 0
        self.prompts: List[str] = []

    def generate_completion_json(self, *, prompt: str, **_: Any) -> Dict[str, Any]:
        self.calls += 1
        self.prompts.append(prompt)
        return self.results.pop(0)


class FailingOriginGenerator:
    def __init__(self) -> None:
        self.calls = 0

    def generate_completion_json(self, **_: Any) -> Dict[str, Any]:
        self.calls += 1
        raise ValueError("OpenAI API key is required")


def _candidate(**overrides: object) -> Dict[str, Any]:
    value: Dict[str, Any] = {
        "start_date": "2026-08-13",
        "starting_age": 28,
        "era_description": "2020年代中期的上海数字内容行业",
        "life_stage_description": "职业发展逐渐进入稳定探索期",
        "world_context": "人工智能工具与数字内容产业快速变化",
    }
    value.update(overrides)
    return value


def test_story_origin_generator_returns_one_normalized_candidate() -> None:
    generator = DeterministicOriginGenerator([_candidate()])
    creator = CharacterCreator(ai_generator=generator)

    result = creator.generate_story_origin(
        player_name="林舟",
        life_vision="在2026年的上海从事数字内容工作",
        previous_settings={},
    )

    assert result == {"revision": 1, **_candidate()}
    assert generator.calls == 1
    assert "birth_year" not in result


def test_story_origin_generator_retries_until_feedback_anchor_matches() -> None:
    generator = DeterministicOriginGenerator(
        [
            _candidate(start_date="2026-08-12", starting_age=27),
            _candidate(start_date="2026-08-13", starting_age=28),
        ]
    )
    creator = CharacterCreator(ai_generator=generator)

    result = creator.generate_story_origin(
        player_name="林舟",
        life_vision="在上海认真生活",
        previous_settings={"story_origin": {"revision": 3, **_candidate()}},
        feedback="改成2026年8月13日，28岁",
    )

    assert result["revision"] == 4
    assert result["start_date"] == "2026-08-13"
    assert result["starting_age"] == 28
    assert generator.calls == 2


def test_story_origin_generator_does_not_return_partial_candidate() -> None:
    generator = DeterministicOriginGenerator(
        [
            _candidate(world_context=""),
            _candidate(world_context=""),
            _candidate(world_context=""),
        ]
    )
    creator = CharacterCreator(ai_generator=generator)

    with pytest.raises(ValueError, match="story_origin_generation_failed"):
        creator.generate_story_origin(
            player_name="林舟",
            life_vision="认真生活",
            previous_settings={},
        )

    assert generator.calls == 3


def test_story_origin_generator_uses_valid_candidate_in_deterministic_e2e_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("E2E_DETERMINISTIC_STORY", "1")
    generator = FailingOriginGenerator()
    creator = CharacterCreator(ai_generator=generator)

    result = creator.generate_story_origin(
        player_name="持久化测试",
        life_vision="",
        previous_settings={},
    )

    assert result == {
        "revision": 1,
        "start_date": "2026-01-01",
        "starting_age": 25,
        "era_description": "2020年代中期的现代都市",
        "life_stage_description": "正在探索职业方向与稳定生活的青年阶段",
        "world_context": "数字工具、城市工作与日常关系持续变化",
    }
    # Explicit deterministic E2E mode must not contact the provider.  CI uses
    # a dummy key, so falling through to the fixture only after provider calls
    # would turn a local contract test into an external-network dependency.
    assert generator.calls == 0


def test_story_origin_generator_does_not_ignore_hard_constraints_in_e2e_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("E2E_DETERMINISTIC_STORY", "1")
    generator = FailingOriginGenerator()
    creator = CharacterCreator(ai_generator=generator)

    with pytest.raises(ValueError, match="story_origin_generation_failed"):
        creator.generate_story_origin(
            player_name="持久化测试",
            life_vision="960 年、20 岁",
            previous_settings={},
        )

    assert generator.calls == 3


def test_story_origin_route_validates_its_request_shape() -> None:
    response = TestClient(app).post("/api/character/story-origin", json={})

    assert response.status_code == 422
