from __future__ import annotations

import asyncio
import threading
import time
from typing import Any, Dict, List

import httpx
import openai
import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException

from src.api.main import app
from src.api.routers import character as character_router
from src.api.schemas import GenerateStoryOriginRequest
from src.game.character_creation import CharacterCreator
from src.game import character_creation as character_creation_module

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


def test_story_origin_short_json_does_not_consume_thinking_tokens() -> None:
    class ThinkingSensitiveGenerator:
        def generate_completion_json(self, **kwargs: Any) -> Dict[str, Any]:
            if kwargs.get("thinking") is not False:
                raise ValueError("response truncated before JSON completed")
            return _candidate()

    creator = CharacterCreator(ai_generator=ThinkingSensitiveGenerator())

    result = creator.generate_story_origin(
        player_name="林舟",
        life_vision="在2026年的上海从事数字内容工作",
        previous_settings={},
    )

    assert result == {"revision": 1, **_candidate()}


def test_story_origin_provider_call_has_timeout_without_truncation_recovery() -> None:
    calls: List[Dict[str, Any]] = []

    class RecordingGenerator:
        def generate_completion_json(self, **kwargs: Any) -> Dict[str, Any]:
            calls.append(kwargs)
            return _candidate()

    CharacterCreator(ai_generator=RecordingGenerator()).generate_story_origin(
        player_name="林舟", life_vision="认真生活", previous_settings={}
    )

    assert len(calls) == 1
    assert 40 < calls[0]["request_timeout"] <= 45
    assert time.monotonic() < calls[0]["request_deadline"] <= time.monotonic() + 45
    assert calls[0]["allow_truncation_recovery"] is False


def test_story_origin_does_not_retry_a_provider_timeout() -> None:
    class TimingOutGenerator:
        calls = 0

        def generate_completion_json(self, **_: Any) -> Dict[str, Any]:
            self.calls += 1
            raise TimeoutError("provider took too long")

    generator = TimingOutGenerator()
    with pytest.raises(TimeoutError):
        CharacterCreator(ai_generator=generator).generate_story_origin(
            player_name="林舟", life_vision="认真生活", previous_settings={}
        )
    assert generator.calls == 1


def test_story_origin_exhausted_deadline_is_a_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        character_creation_module, "_STORY_ORIGIN_DEADLINE_SECONDS", 0.01,
        raising=False,
    )

    class SlowInvalidGenerator:
        calls = 0

        def generate_completion_json(self, **_: Any) -> None:
            self.calls += 1
            time.sleep(0.02)

    generator = SlowInvalidGenerator()
    with pytest.raises(TimeoutError):
        CharacterCreator(ai_generator=generator).generate_story_origin(
            player_name="林舟", life_vision="认真生活", previous_settings={}
        )
    assert generator.calls == 1


@pytest.mark.asyncio
async def test_story_origin_route_reports_provider_timeout_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class TimingOutCreator:
        calls = 0

        def __init__(self, language: str) -> None:
            self.language = language

        def generate_story_origin(self, **_: Any) -> Dict[str, Any]:
            type(self).calls += 1
            raise openai.APITimeoutError(
                request=httpx.Request("POST", "https://provider.test/v1/chat/completions")
            )

    monkeypatch.setattr(character_router, "CharacterCreator", TimingOutCreator)
    with pytest.raises(HTTPException) as exc_info:
        await character_router.generate_story_origin(
            GenerateStoryOriginRequest(player_name="林舟", life_vision="")
        )
    assert exc_info.value.status_code == 504
    assert TimingOutCreator.calls == 1


@pytest.mark.asyncio
async def test_story_origin_route_rejects_when_generation_slots_are_full(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    semaphore = threading.BoundedSemaphore(1)
    semaphore.acquire()
    monkeypatch.setattr(character_router, "_story_origin_slots", semaphore)
    try:
        with pytest.raises(HTTPException) as exc_info:
            await character_router.generate_story_origin(
                GenerateStoryOriginRequest(player_name="林舟", life_vision="")
            )
        assert exc_info.value.status_code == 503
    finally:
        semaphore.release()


@pytest.mark.asyncio
async def test_story_origin_route_returns_timeout_while_worker_holds_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = threading.Event()
    release = threading.Event()
    semaphore = threading.BoundedSemaphore(1)

    class BlockingCreator:
        def __init__(self, language: str) -> None:
            self.language = language

        def generate_story_origin(self, **_: Any) -> Dict[str, Any]:
            started.set()
            release.wait(timeout=2)
            return _candidate()

    monkeypatch.setattr(character_router, "CharacterCreator", BlockingCreator)
    monkeypatch.setattr(character_router, "_story_origin_slots", semaphore)
    monkeypatch.setattr(character_router, "_STORY_ORIGIN_ROUTE_TIMEOUT_SECONDS", 0.05)
    try:
        with pytest.raises(HTTPException) as exc_info:
            await character_router.generate_story_origin(
                GenerateStoryOriginRequest(player_name="林舟", life_vision="")
            )
        assert started.is_set()
        assert exc_info.value.status_code == 504
        assert not semaphore.acquire(blocking=False)
    finally:
        release.set()
    assert await asyncio.to_thread(semaphore.acquire, True, 1)
    semaphore.release()


@pytest.mark.asyncio
async def test_story_origin_generation_keeps_event_loop_responsive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = threading.Event()
    release = threading.Event()
    release_guard = threading.Timer(1.0, release.set)

    class BlockingCreator:
        def __init__(self, language: str) -> None:
            self.language = language

        def generate_story_origin(self, **_: Any) -> Dict[str, Any]:
            started.set()
            release.wait()
            return _candidate()

    monkeypatch.setattr(character_router, "CharacterCreator", BlockingCreator)
    request = GenerateStoryOriginRequest(player_name="林舟", life_vision="")
    task = asyncio.create_task(character_router.generate_story_origin(request))
    release_guard.start()

    try:
        await asyncio.to_thread(started.wait, 0.8)
        assert started.is_set()
        assert not task.done(), "a model call must not block other API requests"
    finally:
        release.set()
        await task
        release_guard.cancel()


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
