"""Tests for StoryGenerator narrative system initialization with empty/default style."""

import os
from unittest.mock import MagicMock, patch

from src.ai.story_generator import StoryGenerator
from src.game.state.player_state import PlayerState


class TestNarrativeSystemInitialization:
    """Test that narrative systems initialize regardless of style_id presence."""

    def test_style_engine_initializes_with_default_when_no_style_id(self):
        """When style_id is empty but env var is enabled, default style should be used."""
        with patch.dict(os.environ, {"ENABLE_NARRATIVE_STYLE_ENGINE": "true"}):
            client = MagicMock()
            gen = StoryGenerator(client)

            player_state = {
                "narrative_style_id": "",
                "player_name": "Test",
                "decision_history": [],
            }
            gen._init_narrative_systems("", player_state)

            assert gen._narrative_systems_initialized is True
            assert gen._style_manifest is not None

    def test_generate_event_calls_init_with_empty_style_id(self):
        """generate_event should call _init_narrative_systems even when style_id is empty."""
        with patch.dict(os.environ, {"ENABLE_NARRATIVE_STYLE_ENGINE": "true"}):
            client = MagicMock()
            gen = StoryGenerator(client)

            with patch.object(gen, "_init_narrative_systems") as mock_init:
                player_state = {
                    "narrative_style_id": "",
                    "player_name": "Test",
                    "decision_history": [],
                    "week": 1,
                }
                mock_opt_gen = MagicMock()
                mock_event = MagicMock()
                mock_event.options = []
                mock_opt_gen.generate_options_only.return_value = mock_event
                with patch.object(gen, "_gather_narrative_hints", return_value={}):
                    with patch.object(gen.client, "call", return_value="test story"):
                        with patch(
                            "src.ai.story_generator.get_story_only_prompt",
                            return_value="prompt",
                        ):
                            with patch(
                                "src.ai.story_generator.get_system_prompt",
                                return_value="sys",
                            ):
                                with patch.object(gen, "_log_constraint_completeness"):
                                    gen.generate_event(player_state, option_generator=mock_opt_gen)

                mock_init.assert_called_once()
                call_args = mock_init.call_args
                assert call_args[0][0] == ""

    def test_narrative_systems_initialized_with_none_style_id(self):
        """generate_event should call _init_narrative_systems with None converted to empty string."""
        with patch.dict(os.environ, {"ENABLE_NARRATIVE_STYLE_ENGINE": "true"}):
            client = MagicMock()
            gen = StoryGenerator(client)

            with patch.object(gen, "_init_narrative_systems") as mock_init:
                player_state = {
                    "narrative_style_id": None,
                    "player_name": "Test",
                    "decision_history": [],
                    "week": 1,
                }
                mock_opt_gen = MagicMock()
                mock_event = MagicMock()
                mock_event.options = []
                mock_opt_gen.generate_options_only.return_value = mock_event
                with patch.object(gen, "_gather_narrative_hints", return_value={}):
                    with patch.object(gen.client, "call", return_value="test story"):
                        with patch(
                            "src.ai.story_generator.get_story_only_prompt",
                            return_value="prompt",
                        ):
                            with patch(
                                "src.ai.story_generator.get_system_prompt",
                                return_value="sys",
                            ):
                                with patch.object(gen, "_log_constraint_completeness"):
                                    gen.generate_event(player_state, option_generator=mock_opt_gen)

                mock_init.assert_called_once()
                call_args = mock_init.call_args
                # None gets coerced to "" by the `or ...get("narrative_style_id", "")` fallback
                assert call_args[0][0] == ""

    def test_round_prompt_refreshes_constraints_when_selected_style_changes(self):
        """The active style must reach the round prompt and refresh after a switch."""
        client = MagicMock()
        client.call.return_value = "这是一个足够长的测试故事，用于验证风格约束会进入实际生成提示词。"
        generator = StoryGenerator(client)
        option_generator = MagicMock()
        event = MagicMock()
        event.options = []
        option_generator.generate_options_only.return_value = event
        quick_result = MagicMock(passed=True, warnings=[], issues=[])

        style_constraints = []

        def capture_prompt(*args, **kwargs):
            style_constraints.append(kwargs.get("style_constraints"))
            return "prompt"

        base_state = {
            "player_name": "测试者",
            "decision_history": [],
            "character_settings": {},
        }

        with patch.dict(os.environ, {"ENABLE_NARRATIVE_STYLE_ENGINE": "false"}):
            with patch("src.ai.story_generator.get_round_event_prompt", side_effect=capture_prompt):
                with patch("src.ai.story_generator.validate_narrative_quality", return_value=[]):
                    with patch("src.ai.quick_validator.quick_validate_story", return_value=quick_result):
                        for style_id in ("chinese_wuxia", "cyberpunk"):
                            generator.generate_round_event(
                                player_state={**base_state, "narrative_style_id": style_id},
                                language="zh",
                                round_number=0,
                                round_context="",
                                character_settings={},
                                option_generator=option_generator,
                            )

        assert len(style_constraints) == 2
        assert all(style_constraints)
        assert style_constraints[0] != style_constraints[1]

    def test_selected_narrative_style_survives_player_state_serialization(self):
        """A selected style must remain available after save/load before regeneration."""
        state = PlayerState.from_dict({"narrative_style_id": "cyberpunk"})

        assert state.narrative_style_id == "cyberpunk"
        assert state.to_dict()["narrative_style_id"] == "cyberpunk"
