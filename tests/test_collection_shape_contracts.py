"""No-provider collection response shape contracts."""

from src.game.state import PlayerState
from src.services.collection_service import CollectionService
import pytest

pytestmark = [pytest.mark.unit]



class _EmptyQuery:
    def filter(self, *_args):
        return self

    def order_by(self, *_args):
        return self

    def all(self):
        return []


class _EmptyDb:
    def query(self, *_args):
        return _EmptyQuery()


def test_collection_preserves_source_precedence_nested_fields_and_empty_image_state():
    state = PlayerState(
        player_name="林岚",
        character_settings={
            "age": {"age": 29},
            "gender": {"gender": "女"},
            "occupation": {"occupation": "建筑师"},
            "relationships": {
                "key_people": [
                    {"name": "陈舟", "role": "重复人物"},
                    {"name": "母亲", "role": "关键家人", "affinity": 66},
                ]
            },
            "family": {"family_members": [{"name": "母亲", "relationship": "母亲"}]},
        },
        characters={"陈舟": {"role": "同事", "relationship_desc": "项目搭档", "affinity": 72}},
    )

    response = CollectionService(_EmptyDb()).get_collection(18, state)

    assert [character.name for character in response.characters] == ["林岚", "陈舟", "母亲"]
    player, npc, key_person = response.characters
    assert (player.age, player.gender, player.occupation, player.description) == (
        29,
        "女",
        "建筑师",
        "29岁，女，建筑师",
    )
    assert (npc.role, npc.description, npc.affinity) == ("同事", "项目搭档", 72)
    assert (key_person.role, key_person.affinity) == ("关键家人", 66)
    assert all(character.image_url is None and not character.image_generated for character in response.characters)
    assert response.total_characters == 3


def test_collection_image_info_handles_player_key_person_family_and_unknown_shapes():
    service = CollectionService(_EmptyDb())
    state = PlayerState(
        player_name="林岚",
        character_settings={
            "age": {"age": 29},
            "gender": {"gender": "女"},
            "occupation": {"occupation": "建筑师"},
            "life_vision": "让旧城建筑重新被人使用",
            "era": {"era_description": "近未来城市"},
            "relationships": {"key_people": [{"name": "阿南", "age": 31, "relationship": "旧友"}]},
            "family": {"family_members": [{"name": "母亲", "age": 58, "gender": "女", "relationship": "母亲"}]},
        },
    )

    player = service.get_character_info_for_image("林岚", state)
    friend = service.get_character_info_for_image("阿南", state)
    family = service.get_character_info_for_image("母亲", state)
    unknown = service.get_character_info_for_image("陌生人", state)

    assert player.is_player is True
    assert player.description == "29岁，女，建筑师，让旧城建筑重新被人使用"
    assert player.era == "近未来城市"
    assert (friend.description, friend.is_player) == ("31岁，旧友", False)
    assert family.description == "58岁，女，母亲"
    assert unknown.description == "一个叫陌生人的人"


def test_collection_relationship_shapes_and_era_defaults_remain_backward_compatible():
    service = CollectionService(_EmptyDb())

    assert service._extract_key_people([{"name": "阿南"}, "invalid", {"name": "阿北"}]) == [
        {"name": "阿南"},
        {"name": "阿北"},
    ]
    assert service._extract_key_people("invalid") == []
    assert service._get_era_from_settings({"era": {"era_name": "民国"}}) == "民国"
    assert service._get_era_from_settings({"era": {"era_description": "近未来"}}) == "近未来"
    assert service._get_era_from_settings({"era": "legacy-string"}) == "现代"
