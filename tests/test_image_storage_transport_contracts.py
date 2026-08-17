"""Provider-free object-storage lifecycle contracts."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from src.services.image_storage import ImageStorageService
import pytest

pytestmark = [pytest.mark.unit]



class _ObjectClient:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.upload: tuple[object, str, bytes, object] | None = None

    def put_object(self, _bucket: str, key: str, data: bytes, metadata=None) -> None:
        self.objects[key] = data
        self.upload = (_bucket, key, data, metadata)

    def get_object(self, key: str):
        return BytesIO(self.objects[key])

    def delete_object(self, key: str) -> None:
        del self.objects[key]

    def object_exists(self, key: str) -> bool:
        return key in self.objects

    def sign_url(self, _method: str, key: str, _expires: int) -> str:
        return f"https://objects.example/{key}"


class _Storage(ImageStorageService):
    def __init__(self, client: _ObjectClient, path: Path) -> None:
        super().__init__(storage_type="oss", local_path=path)
        self.client = client

    def _get_oss_client(self):
        return self.client


def test_object_storage_save_read_url_exists_and_delete_lifecycle(tmp_path: Path) -> None:
    service = _Storage(_ObjectClient(), tmp_path)
    storage_path, storage_type = service._save_oss(
        b"image-bytes",
        "9/item/token.png",
        metadata={"content-type": "image/png"},
    )

    assert storage_path.endswith("/9/item/token.png")
    assert storage_type == "oss"
    assert service.client.upload[1:] == (
        "9/item/token.png",
        b"image-bytes",
        {"content-type": "image/png"},
    )
    assert service.get_image_data(storage_path) == b"image-bytes"
    assert service.get_image_url(storage_path) == "https://objects.example/9/item/token.png"
    assert service.get_image_data("9/item/token.png") == b"image-bytes"
    assert service.get_image_url("9/item/token.png") == "https://objects.example/9/item/token.png"
    assert service.image_exists(storage_path) is True
    assert service.delete_image(storage_path) is True
    assert service.image_exists(storage_path) is False
