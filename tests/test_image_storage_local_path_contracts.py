from pathlib import Path

import pytest

from src.services.image_storage import ImageStorageError, ImageStorageService

pytestmark = [pytest.mark.unit]



def test_local_storage_resolves_relative_and_absolute_paths_and_encodes_urls(tmp_path: Path):
    service = ImageStorageService(storage_type="local", local_path=tmp_path)
    relative_path = "7/character/青玉剑.png"
    full_path = tmp_path / relative_path
    full_path.parent.mkdir(parents=True)
    full_path.write_bytes(b"image-bytes")

    assert service.get_full_path(relative_path) == full_path
    assert service.get_full_path(str(full_path)) == full_path
    assert service.get_image_data(relative_path) == b"image-bytes"
    assert service.get_image_data(str(full_path)) == b"image-bytes"
    assert service.get_image_url(relative_path) == "/api/images/file/7/character/%E9%9D%92%E7%8E%89%E5%89%91.png"
    assert service.get_image_url(str(full_path)) == "/api/images/file/7/character/%E9%9D%92%E7%8E%89%E5%89%91.png"


def test_local_storage_recovers_migrated_legacy_image_api_path(tmp_path: Path):
    service = ImageStorageService(storage_type="local", local_path=tmp_path)

    legacy_path = "/Users/legacy/story2/data/images/9/location/长安.png"

    assert service.get_image_url(legacy_path) == "/api/images/file/9/location/%E9%95%BF%E5%AE%89.png"


def test_local_storage_lifecycle_reports_missing_file_and_idempotent_delete(tmp_path: Path):
    service = ImageStorageService(storage_type="local", local_path=tmp_path)
    relative_path = "12/item/token.png"
    target = tmp_path / relative_path
    target.parent.mkdir(parents=True)
    target.write_bytes(b"token")

    assert service.image_exists(relative_path) is True
    assert service.delete_image(relative_path) is True
    assert service.image_exists(relative_path) is False
    assert service.delete_image(relative_path) is False
    with pytest.raises(ImageStorageError, match="文件不存在"):
        service.get_image_data(relative_path)


def test_local_storage_hashes_fixed_image_bytes(tmp_path: Path):
    service = ImageStorageService(storage_type="local", local_path=tmp_path)

    assert service.compute_hash(b"image-bytes") == (
        "2c8648d103e3dd7ad87660da0f126a1443b6d21ac1bd3ec000c5e24e2373a90c"
    )
