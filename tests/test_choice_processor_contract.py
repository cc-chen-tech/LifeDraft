"""RoundChoiceProcessor contract tests.

No mocks. Uses stub/fake services to verify the input/output field
contracts of the main choice processing functions.
"""

from typing import Any, Dict

import pytest

from src.ai.models import EventOption, GameEvent
from src.game.round.choice_processor import RoundChoiceProcessor
from src.game.state import PlayerState

# ---------------------------------------------------------------------------
# Stub services -- no unittest.mock, just hand-rolled fakes
# ---------------------------------------------------------------------------


class FakeAIClient:
    """Stub AIClient returning valid JSON for the story analyzer."""

    def call(self, **kwargs) -> str:
        return '{"facts": []}'


class FakeEventGenerator:
    """Stub EventGenerator with a fake ai_client."""

    def __init__(self):
        self.ai_client = FakeAIClient()


class FakeStoryService:
    """Stub StoryService returning canned responses for the full pipeline."""

    def __init__(self, language: str = "zh"):
        self.language = language

    # -- methods called by _generate_story_continuation --
    def generate_story_continuation(
        self,
        event_description,
        chosen_option,
        effects,
        character_settings=None,
        player_state=None,
        stream_callback=None,
        status_callback=None,
        is_custom=False,
    ) -> str:
        return "The story continues in an interesting way."

    # -- methods called by _post_choice_pipeline --
    def compress_narrative(
        self, story: str, choice: str, pending_storylines=None
    ) -> Dict[str, Any]:
        return {
            "summary": "A brief summary of events.",
            "event_concluded": True,
            "storyline_updates": [],
            "fact_updates": [],
            "foreshadowing_seeds": [],
            "habit_updates": [],
            "location_updates": [],
            "career_updates": [],
            "commitment_updates": [],
            "causal_updates": [],
        }

    def extract_world_updates(
        self, story, choice, established_facts=None, character_habits=None
    ) -> Dict[str, Any]:
        return {
            "summary": "",  # merged with compress_narrative above
            "fact_updates": [],
            "location_updates": [],
            "career_updates": [],
            "commitment_updates": [],
            "causal_updates": [],
            "foreshadowing_seeds": [],
            "habit_updates": [],
        }

    # -- methods called by _generate_custom_choice_effects / _result --
    def generate_custom_choice_effects(
        self,
        event_description,
        custom_text,
        character_settings=None,
        current_state=None,
    ) -> Dict[str, Any]:
        return {"energy": -3, "mood": 2, "knowledge": 1, "wealth": 0}

    def generate_custom_choice_result(
        self,
        event_description,
        custom_text,
        character_settings=None,
        current_state=None,
    ) -> Dict[str, Any]:
        return {"energy": -3, "mood": 2, "knowledge": 1, "wealth": 0}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_processor(
    player_state=None,
    language="zh",
    story_service=None,
    current_event=None,
):
    """Build a RoundChoiceProcessor wired to the given state/event."""
    if story_service is None:
        story_service = FakeStoryService(language=language)

    _state = player_state
    _event = current_event

    return RoundChoiceProcessor(
        player_state_getter=lambda: _state,
        ai_generator=FakeEventGenerator(),
        language_getter=lambda: language,
        story_service=story_service,
        current_event_getter=lambda: _event,
        current_event_setter=lambda e: None,  # no-op for contract tests
    )


def _make_state(**kwargs) -> PlayerState:
    defaults = {
        "player_name": "TestHero",
        "week": 0,
        "age": 25,
        "current_round": 0,
        "rounds_per_week": 3,
        "energy": 70,
        "mood": 60,
        "knowledge": 50,
        "wealth": 10000,
        "relationships": {},
    }
    defaults.update(kwargs)
    return PlayerState(**defaults)


def _make_event() -> GameEvent:
    return GameEvent(
        event_description="You arrive at the bustling marketplace.",
        options=[
            EventOption(
                text="Browse the stalls",
                effects={"energy": -5, "mood": 5},
                likely_choice=False,
            ),
            EventOption(
                text="Head to the tavern",
                effects={"energy": 5, "mood": 10},
                likely_choice=True,
            ),
            EventOption(
                text="Visit the blacksmith",
                effects={"energy": -10, "mood": -5, "wealth": -200},
                likely_choice=False,
            ),
        ],
    )


# ===================================================================
# Contract tests
# ===================================================================


class TestRoundChoiceProcessorInstantiation:
    """Verify the processor can be instantiated with valid callables."""

    def test_instantiation_with_minimal_args(self):
        proc = RoundChoiceProcessor(
            player_state_getter=lambda: None,
            ai_generator=FakeEventGenerator(),
            language_getter=lambda: "zh",
            story_service=FakeStoryService(),
            current_event_getter=lambda: None,
            current_event_setter=lambda e: None,
        )
        assert proc is not None
        assert proc.player_state is None
        assert proc.language == "zh"

    def test_instantiation_result_callback_optional(self):
        """Result callback should be optional (defaults to None)."""
        proc = RoundChoiceProcessor(
            player_state_getter=lambda: None,
            ai_generator=FakeEventGenerator(),
            language_getter=lambda: "en",
            story_service=FakeStoryService(language="en"),
            current_event_getter=lambda: None,
            current_event_setter=lambda e: None,
        )
        assert proc.result_callback is None

    def test_instantiation_with_result_callback(self):
        results = []

        def cb(result, state):
            results.append(result)

        proc = RoundChoiceProcessor(
            player_state_getter=lambda: None,
            ai_generator=FakeEventGenerator(),
            language_getter=lambda: "zh",
            story_service=FakeStoryService(),
            current_event_getter=lambda: None,
            current_event_setter=lambda e: None,
            result_callback=cb,
        )
        assert proc.result_callback is cb


class TestMakeRoundChoiceContract:
    """Contract tests for make_round_choice."""

    def test_returns_dict_with_required_keys(self):
        """The return dict must contain the expected top-level keys."""
        state = _make_state()
        event = _make_event()
        proc = _make_processor(player_state=state, current_event=event)

        result = proc.make_round_choice(option_index=0)

        assert isinstance(result, dict)
        required_keys = {
            "story_continuation",
            "summary",
            "effects_applied",
            "need_weekly_summary",
            "game_over",
        }
        for key in required_keys:
            assert key in result, f"Missing key '{key}' in result: {list(result.keys())}"

    def test_story_continuation_is_string(self):
        state = _make_state()
        event = _make_event()
        proc = _make_processor(player_state=state, current_event=event)

        result = proc.make_round_choice(option_index=0)
        assert isinstance(result["story_continuation"], str)

    def test_summary_is_string(self):
        state = _make_state()
        event = _make_event()
        proc = _make_processor(player_state=state, current_event=event)

        result = proc.make_round_choice(option_index=0)
        assert isinstance(result["summary"], str)

    def test_effects_applied_is_dict(self):
        state = _make_state()
        event = _make_event()
        proc = _make_processor(player_state=state, current_event=event)

        result = proc.make_round_choice(option_index=0)
        assert isinstance(result["effects_applied"], dict)

    def test_effects_applied_matches_chosen_option(self):
        """The effects_applied dict should match the chosen option's effects."""
        state = _make_state()
        event = _make_event()
        proc = _make_processor(player_state=state, current_event=event)

        # Choose option 0: {"energy": -5, "mood": 5}
        result = proc.make_round_choice(option_index=0)
        assert result["effects_applied"]["energy"] == -5
        assert result["effects_applied"]["mood"] == 5

    def test_need_weekly_summary_is_boolean(self):
        state = _make_state()
        event = _make_event()
        proc = _make_processor(player_state=state, current_event=event)

        result = proc.make_round_choice(option_index=0)
        assert isinstance(result["need_weekly_summary"], bool)

    def test_game_over_is_boolean(self):
        state = _make_state()
        event = _make_event()
        proc = _make_processor(player_state=state, current_event=event)

        result = proc.make_round_choice(option_index=0)
        assert isinstance(result["game_over"], bool)

    def test_game_over_false_early_game(self):
        """game_over should be False when week < TOTAL_WEEKS."""
        state = _make_state(week=0)
        event = _make_event()
        proc = _make_processor(player_state=state, current_event=event)

        result = proc.make_round_choice(option_index=0)
        assert result["game_over"] is False

    def test_need_weekly_summary_true_on_last_round(self):
        """need_weekly_summary should be True when the round is the last in the week."""
        state = _make_state(current_round=2, rounds_per_week=3)  # last round
        event = _make_event()
        proc = _make_processor(player_state=state, current_event=event)

        result = proc.make_round_choice(option_index=0)
        assert result["need_weekly_summary"] is True

    def test_need_weekly_summary_false_not_last_round(self):
        """need_weekly_summary should be False when more rounds remain."""
        state = _make_state(current_round=0, rounds_per_week=3)
        event = _make_event()
        proc = _make_processor(player_state=state, current_event=event)

        result = proc.make_round_choice(option_index=0)
        assert result["need_weekly_summary"] is False

    def test_choice_persists_exact_result_view_after_authoritative_round_advances(self):
        state = _make_state(week=3, current_round=0, rounds_per_week=3)
        event = _make_event()
        proc = _make_processor(player_state=state, current_event=event)

        result = proc.make_round_choice(option_index=0)

        assert state.current_round == 1
        assert state.week == 3
        assert state.resume_view == {
            "phase": "result",
            "story_text": (
                "You arrive at the bustling marketplace.\n\n"
                "The story continues in an interesting way."
            ),
            "round_summary": result["summary"],
            "summary_text": "",
            "resource_warnings": [],
            "completed_week": 3,
            "completed_round": 0,
        }

    def test_last_round_persists_summary_view_instead_of_next_week_event(self):
        state = _make_state(week=3, current_round=2, rounds_per_week=3)
        event = _make_event()
        proc = _make_processor(player_state=state, current_event=event)

        def finalize_week(result, status_callback=None):
            del status_callback
            result["weekly_summary"] = "第4周完整总结"

        proc.make_round_choice(option_index=0, finalize_week_callback=finalize_week)

        # The lightweight processor advances the round; the full GameLoop's
        # finalize callback performs the week rollover after this point.
        assert state.week == 3
        assert state.current_round == 3
        assert state.resume_view["phase"] == "summary"
        assert state.resume_view["summary_text"] == "第4周完整总结"
        assert state.resume_view["completed_week"] == 3
        assert state.resume_view["completed_round"] == 2

    def test_option_index_zero_valid(self):
        """Option index 0 should be valid (first option)."""
        state = _make_state()
        event = _make_event()
        proc = _make_processor(player_state=state, current_event=event)

        result = proc.make_round_choice(option_index=0)
        assert isinstance(result, dict)

    def test_option_index_last_valid(self):
        """The last option index should be valid."""
        state = _make_state()
        event = _make_event()  # 3 options: indices 0, 1, 2
        proc = _make_processor(player_state=state, current_event=event)

        result = proc.make_round_choice(option_index=2)
        assert isinstance(result, dict)

    def test_option_index_negative_raises(self):
        """Negative option index should raise ValueError."""
        state = _make_state()
        event = _make_event()
        proc = _make_processor(player_state=state, current_event=event)

        with pytest.raises(ValueError, match="Invalid option index"):
            proc.make_round_choice(option_index=-1)

    def test_option_index_out_of_range_raises(self):
        """Option index >= len(options) should raise ValueError."""
        state = _make_state()
        event = _make_event()  # 3 options
        proc = _make_processor(player_state=state, current_event=event)

        with pytest.raises(ValueError, match="Invalid option index"):
            proc.make_round_choice(option_index=3)

    def test_none_player_state_raises(self):
        """None player_state should raise ValueError."""
        event = _make_event()
        proc = _make_processor(player_state=None, current_event=event)

        with pytest.raises(ValueError, match="Game not started"):
            proc.make_round_choice(option_index=0)

    def test_none_current_event_raises(self):
        """None current_event should raise ValueError."""
        state = _make_state()
        proc = _make_processor(player_state=state, current_event=None)

        with pytest.raises(ValueError, match="No current event"):
            proc.make_round_choice(option_index=0)


class TestMakeCustomChoiceContract:
    """Contract tests for make_custom_choice."""

    def test_returns_dict_with_required_keys(self):
        """Custom choice result must contain the expected keys."""
        state = _make_state()
        event = _make_event()
        proc = _make_processor(player_state=state, current_event=event)

        result = proc.make_custom_choice(custom_text="I want to explore the alley.")

        assert isinstance(result, dict)
        required_keys = {
            "story_continuation",
            "summary",
            "effects_applied",
            "need_weekly_summary",
            "game_over",
        }
        for key in required_keys:
            assert key in result, f"Missing key '{key}' in custom choice result"

    def test_custom_choice_story_continuation_is_string(self):
        state = _make_state()
        event = _make_event()
        proc = _make_processor(player_state=state, current_event=event)

        result = proc.make_custom_choice(custom_text="Look for hidden passage.")
        assert isinstance(result["story_continuation"], str)

    def test_custom_choice_effects_applied_is_dict(self):
        state = _make_state()
        event = _make_event()
        proc = _make_processor(player_state=state, current_event=event)

        result = proc.make_custom_choice(custom_text="Talk to the stranger.")
        assert isinstance(result["effects_applied"], dict)

    def test_custom_choice_game_over_is_bool(self):
        state = _make_state()
        event = _make_event()
        proc = _make_processor(player_state=state, current_event=event)

        result = proc.make_custom_choice(custom_text="Observe the crowd.")
        assert isinstance(result["game_over"], bool)

    def test_none_player_state_raises(self):
        """None player_state should raise ValueError for custom choice."""
        event = _make_event()
        proc = _make_processor(player_state=None, current_event=event)

        with pytest.raises(ValueError, match="Game not started"):
            proc.make_custom_choice(custom_text="Do something.")

    def test_none_current_event_raises(self):
        """None current_event should raise ValueError for custom choice."""
        state = _make_state()
        proc = _make_processor(player_state=state, current_event=None)

        with pytest.raises(ValueError, match="No current event"):
            proc.make_custom_choice(custom_text="Do something.")


class TestGenerateCustomChoiceEffectsContract:
    """Contract tests for _generate_custom_choice_effects."""

    def test_returns_dict_with_effect_keys(self):
        """Should return a dict with energy, mood, knowledge, wealth keys."""
        state = _make_state()
        proc = _make_processor(player_state=state)

        result = proc._generate_custom_choice_effects(
            event_description="A dark alley.",
            custom_text="Search for clues.",
        )

        assert isinstance(result, dict)
        for key in ("energy", "mood", "knowledge", "wealth"):
            assert key in result, f"Missing key '{key}' in effects"
            assert isinstance(result[key], int), f"Key '{key}' should be int"

    def test_effects_values_are_integers(self):
        """All effect values must be integers."""
        state = _make_state()
        proc = _make_processor(player_state=state)

        result = proc._generate_custom_choice_effects(
            event_description="Market scene.",
            custom_text="Buy rare artifacts.",
        )

        assert all(isinstance(v, int) for v in result.values())


class TestGenerateCustomChoiceResultContract:
    """Contract tests for _generate_custom_choice_result."""

    def test_returns_dict(self):
        state = _make_state()
        proc = _make_processor(player_state=state)

        result = proc._generate_custom_choice_result(
            event_description="At the crossroads.",
            custom_text="Take the left path.",
        )

        assert isinstance(result, dict)

    def test_result_has_effects(self):
        state = _make_state()
        proc = _make_processor(player_state=state)

        result = proc._generate_custom_choice_result(
            event_description="A fork in the road.",
            custom_text="Go right.",
        )

        # The result from FakeStoryService should have effect keys
        assert isinstance(result, dict)


class TestEffectsAppliedIntegrity:
    """Verify effects_applied is a faithful copy of the chosen effects."""

    def test_standard_choice_effects(self):
        state = _make_state()
        event = _make_event()
        proc = _make_processor(player_state=state, current_event=event)

        result = proc.make_round_choice(option_index=1)
        # option 1: {"energy": 5, "mood": 10}
        assert result["effects_applied"]["energy"] == 5
        assert result["effects_applied"]["mood"] == 10
        assert result["effects_applied"].get("wealth", 0) == 0

    def test_standard_choice_effects_with_wealth(self):
        state = _make_state()
        event = _make_event()
        proc = _make_processor(player_state=state, current_event=event)

        result = proc.make_round_choice(option_index=2)
        # option 2: {"energy": -10, "mood": -5, "wealth": -200}
        assert result["effects_applied"]["energy"] == -10
        assert result["effects_applied"]["mood"] == -5
        assert result["effects_applied"]["wealth"] == -200

    def test_exhausting_choice_reports_actual_applied_energy_and_warning(self):
        """When energy is too low, effects_applied should reflect the actual clamped delta."""
        state = _make_state(energy=5)
        event = GameEvent(
            event_description="你已经连续熬夜三天，但团队还在等你推进上线。",
            options=[
                EventOption(
                    text="继续高强度通宵排查所有数据问题",
                    effects={"energy": -20, "mood": -5, "knowledge": 5},
                ),
                EventOption(text="先停下来补觉恢复状态", effects={"energy": 10, "mood": 2}),
            ],
        )
        proc = _make_processor(player_state=state, current_event=event)

        result = proc.make_round_choice(option_index=0)

        assert state.energy == 0
        assert result["effects_applied"]["energy"] == -5
        assert result["effects_requested"]["energy"] == -20
        assert result["resource_warnings"][0]["resource"] == "energy"
        assert result["resource_warnings"][0]["reason"] == "insufficient_resource"

    def test_zero_energy_exhausting_choice_applies_no_extra_energy_loss(self):
        """At zero energy, another exhausting choice should not pretend to spend energy."""
        state = _make_state(energy=0)
        event = GameEvent(
            event_description="你已经精疲力尽，仍有人要求你立刻继续。",
            options=[
                EventOption(
                    text="硬撑着继续处理所有复杂任务",
                    effects={"energy": -12, "mood": -4, "knowledge": 3},
                ),
                EventOption(text="暂停任务并说明自己需要休息", effects={"energy": 8, "mood": 1}),
            ],
        )
        proc = _make_processor(player_state=state, current_event=event)

        result = proc.make_round_choice(option_index=0)

        assert state.energy == 0
        assert result["effects_applied"]["energy"] == 0
        assert result["effects_requested"]["energy"] == -12
        assert result["resource_warnings"][0]["message"]


class TestRoundChoiceProcessorLanguage:
    """Verify language getter is called correctly."""

    def test_language_property_en(self):
        proc = _make_processor(language="en")
        assert proc.language == "en"

    def test_language_property_zh(self):
        proc = _make_processor(language="zh")
        assert proc.language == "zh"
