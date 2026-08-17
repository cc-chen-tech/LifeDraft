"""Database-backed contracts for opening illustration lifecycle behavior."""

from __future__ import annotations

from src.database.models import Game, Image
from src.services.image.scene_service import SceneImageService
import pytest

pytestmark = [pytest.mark.unit]



class _RecordingImageClient:
    def __init__(self) -> None:
        self.opening_calls: list[dict[str, object]] = []
        self.analysis_calls: list[tuple[str, dict[str, object]]] = []
        self.edit_calls: list[dict[str, object]] = []

    def generate_opening_illustration(self, **kwargs: object) -> tuple[bytes, str, str]:
        self.opening_calls.append(kwargs)
        return b"opening-bytes", "opening prompt", "opening scene"

    def analyze_story_for_illustration(
        self, story_text: str, character_info: dict[str, object]
    ) -> tuple[str, str]:
        self.analysis_calls.append((story_text, character_info))
        return "rainy station", "cinematic station"

    def edit_image(self, **kwargs: object) -> list[tuple[bytes, str]]:
        self.edit_calls.append(kwargs)
        return [(b"regenerated-bytes", "ignored-provider-url")]


class _RecordingStorage:
    def __init__(self) -> None:
        self.saved: list[dict[str, object]] = []

    def save_image(self, **kwargs: object) -> tuple[str, str]:
        self.saved.append(kwargs)
        game_id = kwargs["game_id"]
        return f"generated/{game_id}/opening.png", "local"


def _game(db_session) -> Game:
    game = Game(language="zh", initial_state={"player_name": "林岚"})
    db_session.add(game)
    db_session.commit()
    return game


def _old_opening(game_id: int) -> Image:
    return Image(
        game_id=game_id,
        image_type="opening_illustration",
        entity_name="林岚的开场插画",
        entity_key="opening_illustration",
        prompt_text="old prompt",
        storage_path="old/opening.jpg",
        storage_type="local",
        metadata_json={"scene_description": "old scene"},
        version=1,
        is_active=True,
        is_primary=True,
    )


def test_generate_opening_illustration_replaces_old_record_and_persists_generation_metadata(
    db_session,
) -> None:
    game = _game(db_session)
    old_image = _old_opening(game.game_id)
    db_session.add(old_image)
    db_session.commit()
    client = _RecordingImageClient()
    storage = _RecordingStorage()

    result = SceneImageService(
        db_session, image_client=client, storage_service=storage
    ).generate_opening_illustration(
        game_id=game.game_id,
        story_text="林岚抵达雨夜车站。",
        character_settings={"era": {"era_name": "1990年代"}, "age": {"age": 26}},
        player_name="林岚",
        player_image_id=17,
        get_player_image_func=lambda _game_id, _image_id: ("https://img/player.png", 17),
    )

    db_session.refresh(old_image)
    assert old_image.is_active is False
    assert result.is_active is True
    assert result.is_primary is True
    assert result.prompt_text == "opening prompt"
    assert result.storage_path == f"generated/{game.game_id}/opening.png"
    assert result.metadata_json == {
        "scene_description": "opening scene",
        "character_settings": {"era": {"era_name": "1990年代"}, "age": {"age": 26}},
        "player_name": "林岚",
        "reference_image_id": 17,
    }
    assert len(client.opening_calls) == 1
    request = client.opening_calls[0]
    assert request["story_text"] == "林岚抵达雨夜车站。"
    assert request["character_info"] == {"name": "林岚", "era": "1990年代", "age": 26}
    assert request["reference_image_url"] == "https://img/player.png"
    assert request["size"] == "1664*928"
    assert "时代一致性" in str(request["era_constraints"])
    assert storage.saved == [
        {
            "image_data": b"opening-bytes",
            "game_id": game.game_id,
            "image_type": "opening_illustration",
            "entity_name": "林岚的开场插画",
        }
    ]


def test_regenerate_opening_illustration_prioritizes_current_image_data_url(
    db_session,
) -> None:
    game = _game(db_session)
    current = _old_opening(game.game_id)
    current.storage_path = "old/current.png"
    db_session.add(current)
    db_session.commit()
    client = _RecordingImageClient()
    storage = _RecordingStorage()
    player_image_calls: list[tuple[int, int | None]] = []

    result = SceneImageService(
        db_session, image_client=client, storage_service=storage
    ).regenerate_opening_illustration(
        game_id=game.game_id,
        story_text="林岚在车站寻找旧友。",
        character_settings={"gender": {"gender": "女"}},
        player_name="林岚",
        player_image_id=23,
        user_prompt="把雨夜改成清晨",
        current_illustration_id=current.image_id,
        get_image_data_func=lambda _image: b"current-image-bytes",
        get_player_image_func=lambda game_id, image_id: (
            player_image_calls.append((game_id, image_id)) or "https://img/player.png",
            image_id,
        ),
    )

    assert player_image_calls == []
    assert client.edit_calls[0]["reference_image"] == "data:image/png;base64,Y3VycmVudC1pbWFnZS1ieXRlcw=="
    assert client.edit_calls[0]["size"] == "1664*928"
    assert client.edit_calls[0]["extra_params"] == {
        "negative_prompt": SceneImageService.SCENE_EDIT_NEGATIVE_PROMPT
    }
    assert "把雨夜改成清晨" in str(client.edit_calls[0]["prompt"])
    assert result.metadata_json["regenerated_from"] == current.image_id
    assert result.metadata_json["user_prompt"] == "把雨夜改成清晨"
    assert result.metadata_json["reference_image_id"] == 23


def test_regenerate_opening_illustration_uses_player_image_when_current_record_is_missing(
    db_session,
) -> None:
    game = _game(db_session)
    client = _RecordingImageClient()
    storage = _RecordingStorage()
    player_image_calls: list[tuple[int, int | None]] = []

    result = SceneImageService(
        db_session, image_client=client, storage_service=storage
    ).regenerate_opening_illustration(
        game_id=game.game_id,
        story_text="林岚进入安静的书店。",
        character_settings={},
        player_name="林岚",
        player_image_id=31,
        user_prompt="保留木质书架",
        current_illustration_id=999,
        get_player_image_func=lambda game_id, image_id: (
            player_image_calls.append((game_id, image_id)) or "https://img/player-fallback.png",
            image_id,
        ),
    )

    assert player_image_calls == [(game.game_id, 31)]
    assert client.edit_calls[0]["reference_image"] == "https://img/player-fallback.png"
    assert result.metadata_json["regenerated_from"] == 999
    assert result.metadata_json["reference_image_id"] == 31
