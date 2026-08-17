"""Provider-free contracts for relationship-person normalization and recovery."""

from typing import Any

from src.game.character_creation import CharacterCreator
import pytest

pytestmark = [pytest.mark.unit]



class _ScriptedRelationshipGenerator:
    def __init__(self, responses: list[dict[str, Any]]):
        self.responses = list(responses)
        self.call_count = 0

    def generate_completion_json(self, **_kwargs: object) -> dict[str, Any]:
        self.call_count += 1
        return self.responses.pop(0)


def _generate_person(
    generator: _ScriptedRelationshipGenerator, person_index: int = 0
) -> dict[str, Any]:
    creator = CharacterCreator(ai_generator=generator, language="zh")
    return creator.generate_single_relationship_person(
        player_name="林岚",
        life_vision="成为独立游戏叙事设计师",
        previous_settings={"era": {"year": 2026}},
        existing_people=[],
        person_index=person_index,
        total_needed=3,
    )


def test_relationship_description_is_mapped_and_social_defaults_are_supplied() -> None:
    person = _generate_person(
        _ScriptedRelationshipGenerator(
            [
                {
                    "name": "顾言",
                    "role": "大学同学",
                    "relationship_desc": "大学时期共同完成过多个游戏原型项目。",
                    "affinity": 72,
                }
            ]
        )
    )

    assert person["relationship"] == "大学时期共同完成过多个游戏原型项目。"
    assert person["relationship_desc"] == person["relationship"]
    assert person["age"] == 25
    assert person["affinity"] == 72
    assert person["peak_affinity"] == 72
    assert person["trust"] == 50
    assert person["triggered_events"] == []


def test_vague_relationship_description_is_retried_before_returning_valid_person() -> None:
    generator = _ScriptedRelationshipGenerator(
        [
            {
                "name": "顾言",
                "role": "大学同学",
                "relationship_desc": "some friends from university",
            },
            {
                "name": "沈宁",
                "role": "制作人",
                "relationship": "共同负责独立游戏项目的发行节奏。",
            },
        ]
    )

    person = _generate_person(generator)

    assert generator.call_count == 2
    assert person["name"] == "沈宁"
    assert person["relationship_desc"] == "共同负责独立游戏项目的发行节奏。"


def test_repeated_missing_identity_fields_return_indexed_chinese_fallback() -> None:
    person = _generate_person(
        _ScriptedRelationshipGenerator([{}, {}, {}]), person_index=2
    )

    assert person["name"] == "人物3"
    assert person["role"] == "朋友"
    assert person["relationship"] == "与玩家关系密切，经常交流互动。"
    assert person["age"] == 25
    assert person["affinity"] == 55
    assert person["peak_affinity"] == 55
    assert person["has_external_obstacle"] is False
