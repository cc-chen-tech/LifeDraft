"""Import reachability for fast-generation production paths."""
import pytest

pytestmark = [pytest.mark.unit]



def test_fast_generation_budget_paths_are_reachable() -> None:
    from config.prompts.story_prompts import get_round_event_prompt
    from src.ai.generation_budget import get_generation_budget
    from src.ai.story_generator import StoryGenerator

    assert callable(get_round_event_prompt)
    assert callable(get_generation_budget)
    assert callable(StoryGenerator.generate_round_event)

