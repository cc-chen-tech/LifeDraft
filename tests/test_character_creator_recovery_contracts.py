"""Deterministic contracts for character-creation recovery rules."""

import json
from typing import Any

from src.game.character_creation import CharacterCreator


class _DeterministicCreatorGenerator:
    def __init__(self, completions: list[dict[str, Any]], attributes: dict[str, Any]):
        self.completions = completions
        self.attributes = attributes
        self.completion_calls = 0

    def generate_completion(self, **_kwargs: object) -> str:
        self.completion_calls += 1
        return json.dumps(self.completions.pop(0))

    def generate_completion_json(self, **_kwargs: object) -> dict[str, Any]:
        return self.attributes


def test_era_generation_aligns_historical_response_to_explicit_modern_vision() -> None:
    generator = _DeterministicCreatorGenerator(
        [
            {
                "year": 713,
                "era_name": "唐代长安",
                "era_description": "唐代长安与科举制度",
                "world_context": "王朝与门第",
            }
        ],
        {},
    )
    creator = CharacterCreator(ai_generator=generator, language="zh")

    setting = creator.generate_setting(
        "era",
        "林岚",
        "2026年在上海从事独立游戏叙事设计，不要古代",
        previous_settings={},
    )

    assert setting["year"] == 2026
    assert setting["_aligned_to_life_vision"] is True
    assert "独立游戏行业" in setting["era_name"]


def test_wealth_generation_retries_zero_then_enforces_minimum_and_age_birth_year() -> None:
    wealth_generator = _DeterministicCreatorGenerator(
        [{"wealth": 0}, {"wealth": 500}], {}
    )
    creator = CharacterCreator(ai_generator=wealth_generator, language="zh")

    wealth = creator.generate_setting(
        "wealth", "林岚", "成为产品经理", previous_settings={}
    )

    assert wealth_generator.completion_calls == 2
    assert wealth["wealth"] == 1000

    age_generator = _DeterministicCreatorGenerator(
        [{"age": 29, "birth_year": 1990}], {}
    )
    age_creator = CharacterCreator(ai_generator=age_generator, language="zh")
    age = age_creator.generate_setting(
        "age", "林岚", "成为产品经理", previous_settings={"era": {"year": 2026}}
    )

    assert age == {"age": 29, "birth_year": 1997}


def test_initial_attribute_generation_clamps_ai_values_to_supported_range() -> None:
    generator = _DeterministicCreatorGenerator(
        [], {"energy": 150, "mood": -3, "knowledge": 101, "wealth": 2_000_000}
    )
    creator = CharacterCreator(ai_generator=generator, language="zh")

    attributes = creator.generate_initial_attributes(
        {"age": {"age": 30}, "family": {"family_economy": "富裕"}}, language="zh"
    )

    assert attributes == {"energy": 100, "mood": 0, "knowledge": 100, "wealth": 1_000_000}
