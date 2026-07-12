"""Durable event-generation integration tests (Layer 4)."""

import asyncio
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from src.ai.models import EventOption, GameEvent
from src.api.routers.gameplay.sse_helpers import stream_round_event
from src.api.session_store import GameLoopSession


def _event(story: str = "同一个后台任务完成的故事") -> GameEvent:
    return GameEvent(
        event_description=story,
        options=[
            EventOption(text="继续", effects={}),
            EventOption(text="等待", effects={}),
        ],
    )


async def _collect_stream(stream) -> str:
    return "".join([chunk async for chunk in stream])


class TestDurableGenerationLifecycle:
    """SSE subscribers never own or duplicate the background worker."""

    @pytest.mark.asyncio
    async def test_disconnect_does_not_start_a_second_generation(self):
        release = threading.Event()
        started = threading.Event()
        game_loop = MagicMock()
        game_loop.player_state.week = 3
        game_loop.player_state.current_round = 1
        game_loop.current_event = None
        event = _event()

        def generate_round_event(*, stream_callback, status_callback, session):
            started.set()
            status_callback("generating_story")
            stream_callback("同一个后台任务")
            release.wait(timeout=2)
            stream_callback("完成的故事")
            game_loop.current_event = event
            return event

        game_loop.generate_round_event.side_effect = generate_round_event
        session = GameLoopSession(game_loop=game_loop, game_id=91)

        with (
            patch("src.api.routers.gameplay.sse_helpers._persist_generated_event_state"),
            patch("src.api.routers.gameplay.sse_helpers._trigger_round_illustration_generation"),
        ):
            first = stream_round_event(game_loop, 91, session=session)
            await anext(first)
            next_chunk = asyncio.create_task(anext(first))
            assert await asyncio.to_thread(started.wait, 1)
            chunk = await asyncio.wait_for(next_chunk, timeout=1)
            if "同一个后台任务" not in chunk:
                chunk = await asyncio.wait_for(anext(first), timeout=1)
            assert "同一个后台任务" in chunk
            await first.aclose()

            second = stream_round_event(
                game_loop, 91, session=session, last_event_id=0
            )
            release.set()
            payload = await asyncio.wait_for(_collect_stream(second), timeout=2)

        assert game_loop.generate_round_event.call_count == 1
        assert "完成的故事" in payload
        assert "event: complete" in payload

    @pytest.mark.asyncio
    async def test_simultaneous_subscribers_share_one_generation(self):
        release = threading.Event()
        started = threading.Event()
        game_loop = MagicMock()
        game_loop.player_state.week = 3
        game_loop.player_state.current_round = 1
        game_loop.current_event = None
        event = _event("共享任务结果")

        def generate_round_event(*, stream_callback, status_callback, session):
            started.set()
            status_callback("generating_story")
            stream_callback("共享片段")
            release.wait(timeout=2)
            game_loop.current_event = event
            return event

        game_loop.generate_round_event.side_effect = generate_round_event
        session = GameLoopSession(game_loop=game_loop, game_id=92)

        with (
            patch("src.api.routers.gameplay.sse_helpers._persist_generated_event_state"),
            patch("src.api.routers.gameplay.sse_helpers._trigger_round_illustration_generation"),
        ):
            first = stream_round_event(game_loop, 92, session=session)
            second = stream_round_event(game_loop, 92, session=session)
            first_task = asyncio.create_task(_collect_stream(first))
            second_task = asyncio.create_task(_collect_stream(second))
            assert await asyncio.to_thread(started.wait, 1)
            release.set()
            first_payload, second_payload = await asyncio.wait_for(
                asyncio.gather(first_task, second_task), timeout=2
            )

        assert game_loop.generate_round_event.call_count == 1
        assert "共享任务结果" in first_payload
        assert "共享任务结果" in second_payload


class TestGeneratorOwnershipFallback:
    """Direct callers cannot use elapsed time to steal generation ownership."""

    def test_old_start_time_does_not_auto_reset_active_generator(self):
        from src.game.round.event_generator import RoundEventGenerator

        player_state = MagicMock()
        player_state.week = 3
        player_state.current_round = 1
        player_state.round_history = []
        player_state.last_round_full_story = ""
        player_state.current_event_data = None

        generator = RoundEventGenerator(
            player_state_getter=lambda: player_state,
            ai_generator=MagicMock(),
            language_getter=lambda: "zh",
            character_introduction_service=MagicMock(),
            summary_selector=MagicMock(),
            relationship_service=MagicMock(),
        )
        generator._generating = True
        generator._generating_start_time = time.time() - 10_000

        with pytest.raises(ValueError, match="generation in progress"):
            generator.generate_round_event()

        assert generator._generating is True
