from src.game.state import PlayerState
from src.services.collection_service import CollectionService
import pytest

pytestmark = [pytest.mark.unit]



def _service() -> CollectionService:
    return CollectionService.__new__(CollectionService)


def test_collection_character_builders_preserve_first_seen_identity_and_cached_images() -> None:
    service = _service()
    state = PlayerState(
        player_name="林见微",
        character_settings={
            "age": {"age": 28},
            "gender": {"gender": "女"},
            "occupation": {"occupation": "记者"},
        },
    )
    cache = {"林见微": ("/player.png", True), "沈砚": ("/shen.png", True)}
    added: set[str] = set()

    player = service._build_player_character(1, state, state.character_settings, added, cache)
    npc = service._build_key_person(1, {"name": "沈砚", "relationship": "同事"}, added, cache)
    duplicate = service._build_key_person(1, {"name": "沈砚"}, added, cache)

    assert player is not None
    assert player.description == "28岁，女，记者"
    assert player.image_url == "/player.png"
    assert npc is not None and npc.image_generated is True
    assert duplicate is None


def test_collection_settings_helpers_accept_legacy_shapes_and_default_era() -> None:
    service = _service()

    assert service._extract_key_people([{"name": "旧结构"}, "忽略"]) == [{"name": "旧结构"}]
    assert service._extract_key_people({"key_people": [{"name": "新结构"}]}) == [{"name": "新结构"}]
    assert service._extract_nested_value({"age": 31}, "age") == 31
    assert service._get_era_from_settings({"era": {"era_description": "民国"}}) == "民国"
    assert service._get_era_from_settings({}) == "现代"
