"""Contracts for cache-stable, append-only story context."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

from src.ai.long_story_context import DeepSeekTokenCounter, LongStoryContextBuilder, StoryContextSettings
from src.ai.option_generator import OptionGenerator
from src.ai.story_generator import StoryGenerator
from src.game.round.event_generator import RoundEventGenerator
from src.game.state.player_state import PlayerState


class CharacterCounter:
    """Deterministic test token counter: one character is one token."""

    def count(self, text: str) -> int:
        return len(text)


def _round(week: int, round_number: int, story: str, choice: str = "继续") -> dict:
    return {
        "week": week,
        "round": round_number,
        "event_description": story,
        "story_continuation": f"{story} 的后续",
        "choice": choice,
        "date_info": {"date_string": f"第{week + 1}周"},
    }


def _builder(*, budget: int = 800_000) -> LongStoryContextBuilder:
    return LongStoryContextBuilder(
        token_counter=CharacterCounter(),
        settings=StoryContextSettings(input_token_budget=budget, snapshot_target_tokens=12),
    )


def test_build_orders_and_deduplicates_committed_rounds_into_append_only_event_log():
    state = {
        "round_history": [
            _round(1, 1, "第二周第二回合"),
            _round(0, 1, "第一周第二回合"),
            _round(0, 0, "第一周第一回合"),
            _round(0, 0, "重复的旧记录"),
        ],
        "long_context_snapshots": [],
    }

    context = _builder().build(state)

    assert context.history_prefix.startswith("EVENT_LOG_V1\n")
    assert context.history_prefix.index("第一周第一回合") < context.history_prefix.index("第一周第二回合")
    assert context.history_prefix.index("第一周第二回合") < context.history_prefix.index("第二周第二回合")
    assert "重复的旧记录" not in context.history_prefix


def test_prior_history_prefix_is_byte_stable_when_a_new_committed_round_is_appended():
    state = {"round_history": [_round(0, 0, "第一回合")], "long_context_snapshots": []}
    first = _builder().build(state)

    state["round_history"].append(_round(0, 1, "第二回合"))
    second = _builder().build(state)

    assert second.history_prefix.startswith(first.history_prefix)


def test_over_budget_creates_snapshot_without_mutating_raw_history():
    state = {
        "round_history": [
            _round(0, 0, "A" * 35),
            _round(0, 1, "B" * 35),
            _round(0, 2, "C" * 35),
        ],
        "long_context_snapshots": [],
    }
    raw_history = list(state["round_history"])

    context = _builder(budget=145).build(state)

    assert context.input_tokens <= 145
    assert state["round_history"] == raw_history
    assert len(state["long_context_snapshots"]) == 1
    snapshot = state["long_context_snapshots"][0]
    assert snapshot["schema_version"] == 1
    assert snapshot["source_digest"]
    assert "[SNAPSHOT" in context.history_prefix


def test_changed_snapshot_source_is_rebuilt_instead_of_using_stale_text():
    state = {
        "round_history": [_round(0, 0, "A" * 35), _round(0, 1, "B" * 35)],
        "long_context_snapshots": [
            {
                "schema_version": 1,
                "snapshot_id": "epoch:w0r0-w0r0",
                "start_event_id": "w0-r0",
                "end_event_id": "w0-r0",
                "source_digest": "stale",
                "content": "stale snapshot",
                "token_count": 2,
            }
        ],
    }

    _builder(budget=90).build(state)

    assert state["long_context_snapshots"][0]["source_digest"] != "stale"
    assert "stale snapshot" not in state["long_context_snapshots"][0]["content"]


def test_player_state_round_trips_derived_long_context_snapshots_without_changing_history():
    raw_history = [_round(0, 0, "已提交的故事")]
    state = PlayerState.from_dict({"round_history": raw_history})
    state.long_context_snapshots.append({"snapshot_id": "epoch:w0-r0"})

    restored = PlayerState.from_dict(state.to_dict())

    assert restored.round_history == raw_history
    assert restored.long_context_snapshots == [{"snapshot_id": "epoch:w0-r0"}]


def test_option_generation_sends_the_same_history_prefix_before_its_dynamic_request():
    client = Mock(model="deepseek-v4-flash")
    client.call.return_value = json.dumps(
        {
            "options": [
                {"text": "选项一", "effects": {}},
                {"text": "选项二", "effects": {}},
                {"text": "选项三", "effects": {}},
            ]
        }
    )
    history_prefix = "EVENT_LOG_V1\n[EVENT w0-r0]\n已提交的故事\n"

    OptionGenerator(client).generate_options_only(
        story_description="当前故事结尾出现了选择。",
        player_state={},
        history_prefix=history_prefix,
    )

    assert client.call.call_args.kwargs["user_prompt"].startswith(history_prefix)


def test_story_generator_builds_full_history_only_for_deepseek_v4_models():
    state = {"round_history": [_round(0, 0, "第一段已提交故事")]}
    deepseek_client = Mock(model="deepseek-v4-pro")
    fallback_client = Mock(model="gpt-4o-mini")

    assert StoryGenerator(deepseek_client)._long_history_prefix(state).startswith("EVENT_LOG_V1")
    assert StoryGenerator(fallback_client)._long_history_prefix(state) == ""


def test_story_pipeline_has_no_chroma_rag_dependency():
    root = Path(__file__).resolve().parents[1]
    tracked_sources = [
        root / "src/ai/story_generator.py",
        root / "src/game/round/choice_processor.py",
        root / "requirements.txt",
        root / ".env.example",
    ]

    combined = "\n".join(path.read_text() for path in tracked_sources)

    assert "chromadb" not in combined.lower()
    assert "vector_store" not in combined
    assert "ENABLE_VECTOR_SEARCH" not in combined


def test_round_generator_persists_snapshots_created_on_its_state_copy():
    player = PlayerState()
    generated_state = {"long_context_snapshots": [{"snapshot_id": "epoch:w0-r0"}]}

    RoundEventGenerator._persist_long_context_snapshots(player, generated_state)

    assert player.long_context_snapshots == generated_state["long_context_snapshots"]


def test_request_budget_counts_dynamic_tail_before_rendering_history():
    state = {
        "round_history": [_round(0, 0, "A" * 80), _round(0, 1, "B" * 80)],
        "long_context_snapshots": [],
    }
    builder = LongStoryContextBuilder(
        token_counter=CharacterCounter(),
        settings=StoryContextSettings(input_token_budget=145, snapshot_target_tokens=12),
    )

    context = builder.build_for_request(state, "D" * 30)

    assert context.input_tokens + 30 <= 145


def test_default_counter_loads_the_vendored_official_deepseek_tokenizer():
    counter = DeepSeekTokenCounter()

    assert counter._tokenizer is not None
    assert counter.count("故事 memory 101") > 0
