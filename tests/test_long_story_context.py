"""Contracts for cache-stable, append-only story context."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from config.feature_flags import reset_features, set_feature
from src.ai.long_story_context import (
    EVENT_LOG_HEADER,
    DeepSeekTokenCounter,
    DynamicContextParts,
    LongContextBudgetError,
    LongStoryContextBuilder,
    StoryContextSettings,
)
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


def _builder(
    *, budget: int = 800_000, snapshot_target: int = 12
) -> LongStoryContextBuilder:
    return LongStoryContextBuilder(
        token_counter=CharacterCounter(),
        settings=StoryContextSettings(
            input_token_budget=budget,
            snapshot_target_tokens=snapshot_target,
        ),
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
    assert context.history_prefix.index(
        "第一周第一回合"
    ) < context.history_prefix.index("第一周第二回合")
    assert context.history_prefix.index(
        "第一周第二回合"
    ) < context.history_prefix.index("第二周第二回合")
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

    state["continuity_ledger"] = {
        "timeline": [
            {
                "event_id": "w0-r0",
                "summary": "A发生。",
                "choice": "继续",
                "effects": {},
            },
            {
                "event_id": "w0-r1",
                "summary": "B发生。",
                "choice": "继续",
                "effects": {},
            },
            {
                "event_id": "w0-r2",
                "summary": "C发生。",
                "choice": "继续",
                "effects": {},
            },
        ]
    }
    set_feature("structured_story_memory", True)
    try:
        context = _builder(budget=300, snapshot_target=240).build(state)
    finally:
        reset_features()

    assert context.input_tokens <= 300
    assert state["round_history"] == raw_history
    assert len(state["long_context_snapshots"]) == 1
    snapshot = state["long_context_snapshots"][0]
    assert snapshot["schema_version"] == 2
    assert snapshot["covered_event_ids"]
    assert snapshot["end_event_id"] == snapshot["covered_event_ids"][-1]
    assert snapshot["source_digest"]
    assert "[SNAPSHOT" in context.history_prefix


def test_snapshot_v2_never_claims_an_event_without_a_complete_entry():
    state = {
        "round_history": [
            _round(0, 0, "原始故事A" * 15, "选择A"),
            _round(0, 1, "原始故事B" * 15, "选择B"),
            _round(0, 2, "原始故事C" * 15, "选择C"),
        ],
        "continuity_ledger": {
            "timeline": [
                {
                    "event_id": f"w0-r{index}",
                    "summary": f"第{index + 1}件事完整结束。",
                    "choice": f"选择{index + 1}",
                    "effects": {"energy": -index},
                }
                for index in range(3)
            ]
        },
        "long_context_snapshots": [],
    }
    set_feature("structured_story_memory", True)
    try:
        context = _builder(budget=260, snapshot_target=150).build(state)
    finally:
        reset_features()

    snapshot = state["long_context_snapshots"][0]
    covered = snapshot["covered_event_ids"]
    assert covered == [event["event_id"] for event in snapshot["entries"]]
    assert snapshot["end_event_id"] == covered[-1]
    assert all(entry["summary"].endswith("。") for entry in snapshot["entries"])
    snapshot_lines = snapshot["content"].splitlines()
    assert len(snapshot_lines) == len(covered)
    assert [line.split("\t", 1)[0] for line in snapshot_lines] == covered
    assert all(len(line.split("\t")) == 4 for line in snapshot_lines)
    assert all(line in context.history_prefix for line in snapshot_lines)


def test_event_that_does_not_fit_snapshot_remains_raw_without_false_coverage():
    state = {
        "round_history": [
            _round(0, 0, "短事件原文"),
            _round(0, 1, "X" * 180),
        ],
        "continuity_ledger": {
            "timeline": [
                {
                    "event_id": "w0-r0",
                    "summary": "短事件结束。",
                    "choice": "继续",
                    "effects": {},
                },
                {
                    "event_id": "w0-r1",
                    "summary": "Y" * 180 + "。",
                    "choice": "继续",
                    "effects": {},
                },
            ]
        },
        "long_context_snapshots": [],
    }
    set_feature("structured_story_memory", True)
    try:
        context = _builder(budget=230, snapshot_target=100).build(state)
    finally:
        reset_features()

    snapshot = state["long_context_snapshots"][0]
    assert snapshot["covered_event_ids"] == ["w0-r0"]
    assert snapshot["end_event_id"] == "w0-r0"
    assert "[EVENT w0-r1" in context.history_prefix
    assert "X" * 180 in context.history_prefix


def test_no_complete_snapshot_entry_fit_keeps_raw_history_instead_of_header_only():
    state = {
        "round_history": [_round(0, 0, "不可截断的完整事件。" * 20)],
        "long_context_snapshots": [],
    }

    context = _builder(budget=60, snapshot_target=10).build(state)

    assert context.history_prefix != EVENT_LOG_HEADER
    assert "不可截断的完整事件。" * 20 in context.history_prefix
    assert state["long_context_snapshots"] == []


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

    _builder(budget=90, snapshot_target=60).build(state)

    assert not state["long_context_snapshots"] or (
        state["long_context_snapshots"][0]["source_digest"] != "stale"
        and "stale snapshot" not in state["long_context_snapshots"][0]["content"]
    )


def test_valid_v1_snapshot_is_lazily_rebuilt_to_v2_from_unchanged_raw_history():
    raw_history = [_round(0, 0, "A" * 80), _round(0, 1, "B" * 80)]
    state = {"round_history": raw_history, "long_context_snapshots": []}
    canonical = _builder()._canonical_events(raw_history)
    state["long_context_snapshots"] = [
        {
            "schema_version": 1,
            "snapshot_id": "epoch:w0-r0-w0-r0",
            "start_event_id": "w0-r0",
            "end_event_id": "w0-r0",
            "source_digest": _builder()._digest(canonical[:1]),
            "content": "legacy possibly partial content",
            "token_count": 31,
        }
    ]
    original = json.loads(json.dumps(raw_history, ensure_ascii=False))

    _builder(budget=300, snapshot_target=200).build(state)

    assert state["round_history"] == original
    assert state["long_context_snapshots"][0]["schema_version"] == 2
    assert state["long_context_snapshots"][0]["covered_event_ids"]


def test_player_state_round_trips_derived_long_context_snapshots_without_changing_history():
    raw_history = [_round(0, 0, "已提交的故事")]
    state = PlayerState.from_dict({"round_history": raw_history})
    state.long_context_snapshots.append({"snapshot_id": "epoch:w0-r0"})

    restored = PlayerState.from_dict(state.to_dict())

    assert restored.round_history == raw_history
    assert restored.long_context_snapshots == [{"snapshot_id": "epoch:w0-r0"}]


@pytest.mark.parametrize("schema_version", [1, 2])
def test_v1_and_v2_saves_restore_and_continue_without_losing_raw_events(
    schema_version: int,
):
    raw_history = [_round(0, 0, "A" * 80), _round(0, 1, "B" * 80)]
    builder = _builder(budget=300, snapshot_target=200)
    seed: dict = {"round_history": raw_history, "long_context_snapshots": []}
    if schema_version == 1:
        canonical = builder._canonical_events(raw_history)
        seed["long_context_snapshots"] = [
            {
                "schema_version": 1,
                "snapshot_id": "epoch:w0-r0-w0-r0",
                "start_event_id": "w0-r0",
                "end_event_id": "w0-r0",
                "source_digest": builder._digest(canonical[:1]),
                "content": "legacy derived data",
                "token_count": 19,
            }
        ]
    else:
        builder.build(seed)

    restored = PlayerState.from_dict(
        json.loads(json.dumps(PlayerState.from_dict(seed).to_dict()))
    )
    restored.round_history.append(_round(0, 2, "C" * 20))
    context = builder.build(restored)

    assert len(restored.round_history) == 3
    assert [item["event_description"] for item in restored.round_history] == [
        "A" * 80,
        "B" * 80,
        "C" * 20,
    ]
    assert restored.long_context_snapshots[0]["schema_version"] == 2
    covered = set(restored.long_context_snapshots[0]["covered_event_ids"])
    raw_ids = {
        event_id
        for event_id in ("w0-r0", "w0-r1", "w0-r2")
        if f"[EVENT {event_id}" in context.history_prefix
    }
    assert covered | raw_ids == {"w0-r0", "w0-r1", "w0-r2"}


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


def test_option_generation_builds_request_budgeted_history_when_prefix_is_not_supplied():
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
    state = {
        "round_history": [_round(0, 0, "已提交的完整故事。")],
        "long_context_snapshots": [],
    }

    OptionGenerator(client).generate_options_only(
        story_description="当前故事结尾出现了选择。",
        player_state=state,
    )

    prompt = client.call.call_args.kwargs["user_prompt"]
    assert prompt.startswith(EVENT_LOG_HEADER)
    assert "已提交的完整故事。" in prompt


def test_story_generator_builds_full_history_only_for_deepseek_v4_models():
    state = {"round_history": [_round(0, 0, "第一段已提交故事")]}
    deepseek_client = Mock(model="deepseek-v4-pro")
    fallback_client = Mock(model="gpt-4o-mini")

    assert (
        StoryGenerator(deepseek_client)
        ._long_history_prefix(state)
        .startswith("EVENT_LOG_V1")
    )
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
        "continuity_ledger": {
            "timeline": [
                {
                    "event_id": "w0-r0",
                    "summary": "A结束。",
                    "choice": "继续",
                    "effects": {},
                },
                {
                    "event_id": "w0-r1",
                    "summary": "B结束。",
                    "choice": "继续",
                    "effects": {},
                },
            ]
        },
        "long_context_snapshots": [],
    }
    builder = LongStoryContextBuilder(
        token_counter=CharacterCounter(),
        settings=StoryContextSettings(
            input_token_budget=250, snapshot_target_tokens=180
        ),
    )

    set_feature("structured_story_memory", True)
    try:
        context = builder.build_for_request(state, "D" * 30)
    finally:
        reset_features()

    assert context.input_tokens + 30 <= 250


def test_dynamic_context_admits_complete_units_in_priority_order():
    builder = _builder(budget=145)
    parts = DynamicContextParts(
        current_request="现在要做什么？",
        character_authority="角色权威。",
        ledger_facts="账本事实。",
        recent_events=("最近事件一。", "最近事件二。"),
        old_history=("O" * 100, "更旧事件。"),
    )

    rendered = builder.fit_dynamic_context(parts)

    assert "现在要做什么？" in rendered
    assert "角色权威。" in rendered
    assert "账本事实。" in rendered
    assert "最近事件一。" in rendered
    assert "最近事件二。" in rendered
    assert "O" * 100 not in rendered
    assert "更旧事件。" in rendered
    assert "O" * 20 not in rendered


def test_required_dynamic_context_overflow_raises_explicit_technical_error():
    builder = _builder(budget=40)

    with pytest.raises(LongContextBudgetError, match="[Rr]equired dynamic context"):
        builder.fit_dynamic_context(
            DynamicContextParts(
                current_request="R" * 41,
                character_authority="",
                ledger_facts="",
            )
        )


def test_six_hundred_events_fit_production_absolute_context_without_false_coverage():
    state = {
        "round_history": [
            _round(index // 3, index % 3, f"事件{index}。" + "叙事细节" * 700)
            for index in range(600)
        ],
        "continuity_ledger": {
            "timeline": [
                {
                    "event_id": f"w{index // 3}-r{index % 3}",
                    "summary": f"事件{index}完整结束。",
                    "choice": "继续",
                    "effects": {"sequence": index},
                }
                for index in range(600)
            ]
        },
        "long_context_snapshots": [],
    }
    set_feature("structured_story_memory", True)
    try:
        context = LongStoryContextBuilder().build(state)
    finally:
        reset_features()

    assert context.input_tokens < 800_000
    snapshot = state["long_context_snapshots"][0]
    assert snapshot["schema_version"] == 2
    assert len(snapshot["covered_event_ids"]) == 600
    assert snapshot["covered_event_ids"] == [
        entry["event_id"] for entry in snapshot["entries"]
    ]


def test_default_counter_loads_the_vendored_official_deepseek_tokenizer():
    counter = DeepSeekTokenCounter()

    assert counter._tokenizer is not None
    assert counter.count("故事 memory 101") > 0
