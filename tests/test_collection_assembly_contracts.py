from __future__ import annotations

from typing import Optional

from src.game.state import PlayerState
from src.services.collection_service import CollectionService


class _CachedCollectionService(CollectionService):
    def __init__(self, image_cache: dict[str, dict[str, tuple[Optional[str], bool]]]):
        self.image_cache = image_cache

    def _get_entity_images_batch(
        self, _game_id: int, image_type: str
    ) -> dict[str, tuple[Optional[str], bool]]:
        return self.image_cache.get(image_type, {})


def _service() -> _CachedCollectionService:
    return _CachedCollectionService(
        {
            "character": {
                "Lin": ("/images/lin.png", True),
                "Noah": ("/images/noah.png", True),
                "Mira": ("/images/mira.png", True),
                "Rae": ("/images/rae.png", True),
            },
            "item": {"Notebook": ("/images/notebook.png", True)},
            "landmark": {"Studio": ("/images/studio.png", True)},
        }
    )


def test_collection_assembly_merges_entity_sources_cached_images_and_defaults() -> None:
    state = PlayerState(
        player_name="Lin",
        character_settings={
            "age": {"age": 28},
            "gender": {"gender": "nonbinary"},
            "occupation": {"occupation": "architect"},
            "personality_traits": ["observant"],
            "relationships": {
                "key_people": [
                    {"name": "Mira", "role": "mentor", "relationship": "advisor"},
                    {"name": "Noah", "role": "duplicate source"},
                ]
            },
            "family": {
                "family_members": [
                    {"name": "Rae", "relationship": "sibling", "age": 25},
                    {"name": "Mira", "relationship": "duplicate source"},
                ]
            },
        },
    )
    state.characters = {
        "Noah": {
            "role": "colleague",
            "relationship_desc": "project partner",
            "affinity": 72,
            "age": 31,
            "personality_traits": ["calm"],
        }
    }
    state.items = {
        "Notebook": {
            "description": "A weathered field notebook",
            "importance": "high",
            "category": "document",
            "acquired_week": 4,
            "is_key_item": True,
            "metadata": {"source": "archive"},
        }
    }
    state.landmarks = {
        "Studio": {
            "description": "A bright shared studio",
            "category": "workplace",
            "importance": "high",
            "first_appear_week": 2,
            "appear_count": 3,
            "last_appear_week": 6,
            "is_key_location": True,
        }
    }

    collection = _service().get_collection(42, state)

    assert (collection.game_id, collection.total_characters, collection.total_items, collection.total_landmarks) == (
        42,
        4,
        1,
        1,
    )
    characters = {character.name: character for character in collection.characters}
    assert set(characters) == {"Lin", "Noah", "Mira", "Rae"}
    assert characters["Lin"].model_dump() == {
        "name": "Lin",
        "role": "主角",
        "description": "28岁，nonbinary，architect",
        "affinity": 100,
        "age": 28,
        "gender": "nonbinary",
        "occupation": "architect",
        "personality_traits": ["observant"],
        "image_url": "/images/lin.png",
        "image_generated": True,
        "description_generated": True,
    }
    assert characters["Noah"].role == "colleague"
    assert characters["Noah"].description == "project partner"
    assert characters["Mira"].personality_traits == []
    assert characters["Rae"].role == "家庭成员"
    assert characters["Rae"].affinity == 80

    item = collection.items[0]
    assert item.image_url == "/images/notebook.png"
    assert item.image_generated is True
    assert item.description_generated is False
    assert item.metadata == {"source": "archive"}
    landmark = collection.landmarks[0]
    assert landmark.image_url == "/images/studio.png"
    assert landmark.image_generated is True
    assert landmark.context == ""
    assert landmark.is_key_location is True


def test_collection_assembly_keeps_player_only_response_shape_for_empty_sources() -> None:
    state = PlayerState(player_name="Lin", character_settings={"player_name": "Ignored"})

    collection = _service().get_collection(7, state)

    assert collection.game_id == 7
    assert collection.total_characters == 1
    assert collection.total_items == 0
    assert collection.total_landmarks == 0
    assert [character.name for character in collection.characters] == ["Lin"]
    assert collection.characters[0].image_url == "/images/lin.png"
    assert collection.items == []
    assert collection.landmarks == []
