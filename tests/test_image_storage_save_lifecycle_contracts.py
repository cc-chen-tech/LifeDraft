"""Provider-free local image storage save lifecycle contracts."""

from pathlib import Path

from src.services.image_storage import ImageStorageService


def test_round_scene_save_preserves_bytes_and_encodes_visible_time_coordinates(
    tmp_path: Path,
) -> None:
    service = ImageStorageService(storage_type="local", local_path=tmp_path)
    original_data = b"not-a-valid-image-but-a-recoverable-upload"

    storage_path, storage_type = service.save_image(
        image_data=original_data,
        game_id=17,
        image_type="round_scene",
        entity_name="林岚在雨夜寻找青玉剑",
        week=2,
        round_number=1,
        stage="event",
    )

    assert storage_type == "local"
    assert storage_path.startswith("17/round_scene/week_3_round_1_event_")
    assert storage_path.endswith(".png")
    assert service.get_full_path(storage_path).is_file()
    assert service.get_image_data(storage_path) == original_data
    assert service.image_exists(storage_path) is True


def test_entity_filename_uses_short_artifact_name_and_local_delete_round_trip(
    tmp_path: Path,
) -> None:
    service = ImageStorageService(storage_type="local", local_path=tmp_path)
    original_data = b"recoverable-local-item"

    storage_path, storage_type = service.save_image(
        image_data=original_data,
        game_id=18,
        image_type="item",
        entity_name="青玉剑（旧书院传家宝）",
    )

    assert storage_type == "local"
    assert "_青玉剑_" in storage_path
    assert service.get_image_data(storage_path) == original_data
    assert service.delete_image(storage_path) is True
    assert service.image_exists(storage_path) is False
