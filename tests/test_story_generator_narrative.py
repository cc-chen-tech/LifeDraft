"""Tests for StoryGenerator narrative system initialization with empty/default style."""

import os
from unittest.mock import MagicMock, patch

from src.ai.story_generator import StoryGenerator


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
                        with patch("src.ai.story_generator.get_story_only_prompt", return_value="prompt"):
                            with patch("src.ai.story_generator.get_system_prompt", return_value="sys"):
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
                        with patch("src.ai.story_generator.get_story_only_prompt", return_value="prompt"):
                            with patch("src.ai.story_generator.get_system_prompt", return_value="sys"):
                                with patch.object(gen, "_log_constraint_completeness"):
                                    gen.generate_event(player_state, option_generator=mock_opt_gen)

                mock_init.assert_called_once()
                call_args = mock_init.call_args
                # None gets coerced to "" by the `or ...get("narrative_style_id", "")` fallback
                assert call_args[0][0] == ""
