"""Import reachability for world fact-safety production paths."""
import pytest

pytestmark = [pytest.mark.unit]



def test_world_fact_safety_lazy_paths_are_reachable() -> None:
    from config.prompts.character_prompts import get_character_setting_prompt
    from src.game.character_creation import CharacterCreator
    from src.game.world_fact_safety import qualify_generated_world_facts

    assert callable(get_character_setting_prompt)
    assert callable(qualify_generated_world_facts)
    assert callable(CharacterCreator.generate_setting)

