"""Real-DB contracts for deterministic scene image delivery and failure rollback."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.ai.image_exceptions import ImageProviderError
from src.database.models import Game, SceneImage
from src.services.image import ImageProviderServiceError
from src.services.image.scene_service import SceneImageService
from src.services.image_storage import ImageStorageService


class _SceneProvider:
    def analyze_story_for_illustration(self, *, story_text, character_info):
        assert story_text
        assert character_info["name"] == "林见微"
        return "雨夜的产品发布会现场", "cinematic rainy product launch"

    def generate_image(self, *, prompt, size, extra_params):
        assert "cinematic" in prompt
        assert size == "1664*928"
        assert extra_params == {"prompt_extend": True}
        return b"local-scene-image", prompt


class _CapacityProvider(_SceneProvider):
    def generate_image(self, **_kwargs):
        raise ImageProviderError(
            code="minimax_2056",
            category="capacity",
            retryable=False,
            public_message="图片生成额度暂时不可用，请稍后再试",
        )


def _game(db_session) -> Game:
    game = Game(language="zh", initial_state={"week": 4})
    db_session.add(game)
    db_session.commit()
    return game


@pytest.mark.integration
def test_scene_provider_fake_persists_readable_local_delivery(db_session, tmp_path: Path) -> None:
    game = _game(db_session)
    storage = ImageStorageService(local_path=tmp_path)
    service = SceneImageService(db_session, image_client=_SceneProvider(), storage_service=storage)

    scene = service.generate_round_scene_image(
        game_id=game.game_id,
        round_number=2,
        story_text="林见微在雨夜发布会上发现了数据异常。",
        character_settings={"era": {"era_description": "现代都市"}},
        player_name="林见微",
        week=4,
        stage="event",
    )

    persisted = db_session.query(SceneImage).filter(SceneImage.scene_id == scene.scene_id).one()
    assert persisted.game_id == game.game_id
    assert (persisted.week, persisted.round_number, persisted.stage) == (4, 2, "event")
    assert persisted.scene_description == "雨夜的产品发布会现场"
    assert "cinematic rainy product launch" in persisted.final_prompt
    assert "雨夜的产品发布会现场" in persisted.final_prompt
    assert persisted.storage_type == "local"
    assert storage.get_full_path(str(persisted.storage_path)).read_bytes() == b"local-scene-image"


@pytest.mark.integration
def test_provider_failure_rolls_back_scene_slot_and_preserves_safe_metadata(db_session, tmp_path: Path) -> None:
    game = _game(db_session)
    service = SceneImageService(
        db_session,
        image_client=_CapacityProvider(),
        storage_service=ImageStorageService(local_path=tmp_path),
    )

    with pytest.raises(ImageProviderServiceError) as raised:
        service.generate_round_scene_image(
            game_id=game.game_id,
            round_number=3,
            story_text="林见微等待供应商恢复。",
            character_settings={},
            player_name="林见微",
            week=4,
            stage="result",
        )

    assert raised.value.code == "minimax_2056"
    assert raised.value.category == "capacity"
    assert raised.value.retryable is False
    assert (
        db_session.query(SceneImage)
        .filter(
            SceneImage.game_id == game.game_id,
            SceneImage.week == 4,
            SceneImage.round_number == 3,
            SceneImage.stage == "result",
        )
        .count()
        == 0
    )
