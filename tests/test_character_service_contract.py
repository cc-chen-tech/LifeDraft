"""CharacterImageService contract tests.

No mocks. Uses real DB session with stub image client and storage service
to verify request/response contract, error handling, and required fields.
"""

import pytest

from src.database.models import Image as ImageModel
from src.services.image import ImageContentError, ImageServiceError
from src.services.image.character_service import CharacterImageService
from src.services.image_storage import ImageStorageService

# ---------------------------------------------------------------------------
# Stub classes -- hand-rolled fakes, NOT unittest.mock
# ---------------------------------------------------------------------------


class StubImageClient:
    """Stub ImageClient that returns preset data without real API calls."""

    def __init__(self, anchor_data=None, images_data=None):
        self.anchor_data = anchor_data or {
            "hair": "黑色短发",
            "eyes": "棕色",
            "face_shape": "瓜子脸",
            "build": "中等身材",
            "skin_tone": "偏白",
            "distinctive_features": [],
            "anchor_summary_sn": "黑色短发，棕色眼睛，中等身材",
        }
        self.images_data = (
            images_data
            if images_data is not None
            else [(b"\x89PNG\r\n\x1a\nfake_image", "test character prompt")]
        )
        self.primary_url = (
            "https://example.com/primary.png"
            if images_data is not None and len(images_data) > 0
            else None
        )
        self.last_generate_call = None
        self.last_anchor_call = None

    def generate_appearance_anchor(self, name, description, era="现代", character_settings=None):
        self.last_anchor_call = {
            "name": name,
            "description": description,
            "era": era,
            "character_settings": character_settings,
        }
        return self.anchor_data

    def generate_character_images(
        self,
        name,
        description,
        era="现代",
        style_hint=None,
        num_images=1,
        size=None,
        reference_image_url=None,
        feedback=None,
        extra_params=None,
    ):
        self.last_generate_call = {
            "name": name,
            "description": description,
            "era": era,
            "style_hint": style_hint,
            "num_images": num_images,
            "reference_image_url": reference_image_url,
            "feedback": feedback,
            "extra_params": extra_params,
        }
        return self.images_data, self.primary_url


class FailingImageClient(StubImageClient):
    """ImageClient stub that raises on generate."""

    def generate_character_images(self, **kwargs):
        from src.ai.image_exceptions import ImageGenerationError

        raise ImageGenerationError("API unavailable")


class ContentFailingImageClient(StubImageClient):
    """ImageClient stub that raises ContentInspectionError."""

    def generate_character_images(self, **kwargs):
        from src.ai.image_exceptions import ContentInspectionError

        raise ContentInspectionError("Content inspection failed", original_prompt="bad prompt")


class StubImageStorage:
    """Stub ImageStorageService that returns preset paths."""

    def __init__(self, save_path="local/test/path.png", save_type="local"):
        self.save_path = save_path
        self.save_type = save_type
        self.last_save_call = None
        self.deleted_paths: list = []
        self.get_image_data_returns = b"\x89PNG\r\n\x1a\nstored_data"

    def save_image(self, image_data, game_id, image_type, entity_name):
        self.last_save_call = {
            "image_data": image_data,
            "game_id": game_id,
            "image_type": image_type,
            "entity_name": entity_name,
        }
        return (self.save_path, self.save_type)

    def delete_image(self, storage_path, storage_type=None):
        self.deleted_paths.append(storage_path)
        return True

    def get_image_data(self, storage_path, storage_type=None):
        return self.get_image_data_returns

    def get_image_url(self, storage_path, storage_type=None):
        return f"https://example.com/{storage_path}"


# ============================================================
# CharacterImageService construction
# ============================================================


class TestCharacterServiceConstruction:
    """Contract tests for CharacterImageService.__init__."""

    def test_construct_with_db_and_stubs(self, db_session):
        client = StubImageClient()
        storage = StubImageStorage()
        service = CharacterImageService(db_session, image_client=client, storage_service=storage)
        assert service.db is db_session
        assert service.image_client is client
        assert service.storage_service is storage

    def test_construct_with_defaults_creates_clients(self, db_session):
        """When no clients provided, defaults are created."""
        service = CharacterImageService(db_session)
        assert service.db is db_session
        # When no image_client passed, a real ImageClient is created
        from src.ai.image_client import ImageClient

        assert isinstance(service.image_client, ImageClient)
        assert isinstance(service.storage_service, ImageStorageService)

    def test_construct_with_custom_storage(self, db_session):
        storage = StubImageStorage()
        service = CharacterImageService(db_session, storage_service=storage)
        assert service.storage_service is storage


# ============================================================
# generate_character_image contract tests
# ============================================================


class TestGenerateCharacterImage:
    """Contract tests for generate_character_image using stubs."""

    def _make_service(self, db_session, client=None, storage=None):
        return CharacterImageService(
            db_session,
            image_client=client or StubImageClient(),
            storage_service=storage or StubImageStorage(),
        )

    def test_returns_list_of_image_models(self, db_session):
        service = self._make_service(db_session)
        result = service.generate_character_image(
            game_id=1,
            name="张三",
            description="一个年轻的书生",
            era="现代",
        )
        assert isinstance(result, list)
        assert len(result) > 0
        for model in result:
            assert isinstance(model, ImageModel)

    def test_output_has_required_fields(self, db_session):
        service = self._make_service(db_session)
        result = service.generate_character_image(
            game_id=1,
            name="李四",
            description="一个侠客",
            era="现代",
        )
        model = result[0]
        # Required fields that should be set
        assert model.game_id == 1
        assert model.image_type == "character"
        assert model.entity_name == "李四"
        assert model.is_active is True
        assert model.storage_path is not None
        assert model.storage_type is not None

    def test_default_is_primary(self, db_session):
        service = self._make_service(db_session)
        result = service.generate_character_image(
            game_id=1,
            name="王五",
            description="一个商人",
        )
        assert result[0].is_primary is True

    def test_entity_key_set_correctly(self, db_session):
        service = self._make_service(db_session)
        result = service.generate_character_image(
            game_id=1,
            name="赵六",
            description="一个学者",
            entity_key="custom_key",
        )
        assert result[0].entity_key == "custom_key"

    def test_entity_key_default_from_name(self, db_session):
        service = self._make_service(db_session)
        result = service.generate_character_image(
            game_id=1,
            name="孙七",
            description="一个医生",
        )
        assert result[0].entity_key == "character_孙七"

    def test_passes_parameters_to_image_client(self, db_session):
        client = StubImageClient()
        service = self._make_service(db_session, client=client)
        service.generate_character_image(
            game_id=1,
            name="周八",
            description="一个程序员",
            era="古代",
            style_hint="水墨画风格",
            num_images=1,
            feedback="请更年轻一些",
        )
        assert client.last_anchor_call is not None
        assert client.last_anchor_call["name"] == "周八"
        assert client.last_anchor_call["description"] == "一个程序员"
        assert client.last_anchor_call["era"] == "古代"

        assert client.last_generate_call is not None
        assert client.last_generate_call["name"] == "周八"
        assert client.last_generate_call["era"] == "古代"
        assert client.last_generate_call["num_images"] == 1
        assert client.last_generate_call["feedback"] == "请更年轻一些"

    def test_num_images_generates_correct_count(self, db_session):
        client = StubImageClient(
            images_data=[
                (b"img1", "prompt1"),
                (b"img2", "prompt2"),
                (b"img3", "prompt3"),
            ]
        )
        service = self._make_service(db_session, client=client)
        result = service.generate_character_image(
            game_id=1,
            name="Test",
            description="test",
            num_images=3,
        )
        assert len(result) == 3

    def test_first_image_is_primary_without_reference(self, db_session):
        client = StubImageClient(
            images_data=[
                (b"img1", "p1"),
                (b"img2", "p2"),
            ]
        )
        service = self._make_service(db_session, client=client)
        result = service.generate_character_image(
            game_id=1,
            name="Test",
            description="test",
            num_images=2,
        )
        assert result[0].is_primary is True
        assert result[1].is_primary is False

    def test_reference_image_sets_is_primary_false(self, db_session):
        client = StubImageClient(images_data=[(b"img1", "p1")])
        service = self._make_service(db_session, client=client)
        result = service.generate_character_image(
            game_id=1,
            name="Test",
            description="test",
            reference_image_url="https://example.com/ref.png",
        )
        assert result[0].is_primary is False

    def test_metadata_stored_in_image_model(self, db_session):
        service = self._make_service(db_session)
        result = service.generate_character_image(
            game_id=1,
            name="Test",
            description="test",
            metadata={"test_key": "test_value"},
        )
        assert result[0].metadata_json is not None
        assert "test_key" in result[0].metadata_json

    def test_appearance_anchor_in_metadata(self, db_session):
        service = self._make_service(db_session)
        result = service.generate_character_image(
            game_id=1,
            name="Test",
            description="test",
        )
        metadata = result[0].metadata_json or {}
        assert "appearance_anchor" in metadata
        assert isinstance(metadata["appearance_anchor"], dict)

    def test_empty_images_raises_service_error(self, db_session):
        client = StubImageClient(images_data=[])
        service = self._make_service(db_session, client=client)
        with pytest.raises(ImageServiceError, match="没有成功生成任何图片"):
            service.generate_character_image(game_id=1, name="Test", description="test")

    def test_image_generation_error_raises_service_error(self, db_session):
        client = FailingImageClient()
        service = self._make_service(db_session, client=client)
        with pytest.raises(ImageServiceError, match="图像生成失败"):
            service.generate_character_image(game_id=1, name="Test", description="test")

    def test_content_inspection_error_raises_content_error(self, db_session):
        client = ContentFailingImageClient()
        service = self._make_service(db_session, client=client)
        with pytest.raises(ImageContentError):
            service.generate_character_image(game_id=1, name="Test", description="test")

    def test_images_persisted_in_db(self, db_session):
        service = self._make_service(db_session)
        result = service.generate_character_image(
            game_id=1,
            name="db_test",
            description="test",
        )
        # Query back from DB
        saved = (
            db_session.query(ImageModel).filter(ImageModel.image_id == result[0].image_id).first()
        )
        assert saved is not None
        assert saved.entity_name == "db_test"

    def test_old_images_deactivated(self, db_session):
        """When keep_old_active=False, previous active images should be deactivated."""
        service = self._make_service(db_session)
        # Generate first image
        first_result = service.generate_character_image(
            game_id=1,
            name="deactivate_test",
            description="test",
            entity_key="deactivate_key",
        )
        first_id = first_result[0].image_id
        assert first_result[0].is_active is True

        # Generate second image with same entity_key
        second_result = service.generate_character_image(
            game_id=1,
            name="deactivate_test",
            description="test",
            entity_key="deactivate_key",
        )
        # First image should be deactivated
        db_session.refresh(first_result[0])
        assert first_result[0].is_active is False
        assert second_result[0].is_active is True

    def test_keep_old_active_preserves_previous(self, db_session):
        """When keep_old_active=True, old images stay active."""
        service = self._make_service(db_session)
        first_result = service.generate_character_image(
            game_id=1,
            name="keep_test",
            description="test",
            entity_key="keep_key",
        )
        second_result = service.generate_character_image(
            game_id=1,
            name="keep_test",
            description="test",
            entity_key="keep_key",
            keep_old_active=True,
        )
        db_session.refresh(first_result[0])
        assert first_result[0].is_active is True
        assert second_result[0].is_active is True

    def test_storage_save_called(self, db_session):
        storage = StubImageStorage()
        service = self._make_service(db_session, storage=storage)
        service.generate_character_image(game_id=1, name="Test", description="test")
        assert storage.last_save_call is not None
        assert storage.last_save_call["game_id"] == 1
        assert storage.last_save_call["image_type"] == "character"

    def test_modern_era_adds_negative_prompt(self, db_session):
        """现代背景应该加入反科幻 negative_prompt。"""
        client = StubImageClient()
        service = self._make_service(db_session, client=client)
        service.generate_character_image(
            game_id=1,
            name="Test",
            description="test",
            era="现代",
        )
        extra = client.last_generate_call.get("extra_params")
        assert extra is not None
        assert "negative_prompt" in extra
        assert "赛博朋克" in extra["negative_prompt"]


# ============================================================
# regenerate_image error handling
# ============================================================


class TestRegenerateImageErrorHandling:
    """Contract tests for regenerate_image error flows."""

    def test_invalid_image_id_raises(self, db_session):
        service = CharacterImageService(db_session)
        with pytest.raises(ImageServiceError, match="图片不存在"):
            service.regenerate_image(image_id=99999)


# ============================================================
# regenerate_fresh_image error handling
# ============================================================


class TestRegenerateFreshImageErrorHandling:
    """Contract tests for regenerate_fresh_image error flows."""

    def test_invalid_image_id_raises(self, db_session):
        service = CharacterImageService(db_session)
        with pytest.raises(ImageServiceError, match="图片不存在"):
            service.regenerate_fresh_image(image_id=99999)


# ============================================================
# Exception hierarchy
# ============================================================


class TestImageServiceExceptions:
    """Contract tests for image service exception hierarchy."""

    def test_image_service_error_is_exception(self):
        err = ImageServiceError("test")
        assert isinstance(err, Exception)

    def test_image_service_error_message(self):
        err = ImageServiceError("something failed")
        assert str(err) == "something failed"

    def test_image_content_error_is_image_service_error(self):
        err = ImageContentError("content failed")
        assert isinstance(err, ImageServiceError)

    def test_image_content_error_has_original_prompt(self):
        err = ImageContentError("msg", original_prompt="original prompt text")
        assert err.original_prompt == "original prompt text"

    def test_image_content_error_original_prompt_default(self):
        err = ImageContentError("msg")
        assert err.original_prompt is None

    def test_image_content_error_caught_as_service_error(self):
        with pytest.raises(ImageServiceError):
            raise ImageContentError("test")


# ============================================================
# Edge cases with invalid inputs
# ============================================================


class TestCharacterServiceEdgeCases:
    """Edge case contract tests for CharacterImageService."""

    def test_generate_with_empty_name(self, db_session):
        service = CharacterImageService(
            db_session,
            image_client=StubImageClient(),
            storage_service=StubImageStorage(),
        )
        result = service.generate_character_image(
            game_id=1,
            name="",
            description="test description",
        )
        assert len(result) > 0
        assert result[0].entity_name == ""

    def test_generate_with_empty_description(self, db_session):
        service = CharacterImageService(
            db_session,
            image_client=StubImageClient(),
            storage_service=StubImageStorage(),
        )
        result = service.generate_character_image(
            game_id=1,
            name="Test",
            description="",
        )
        assert len(result) > 0
        assert result[0].is_active is True

    def test_generate_with_style_hint(self, db_session):
        client = StubImageClient()
        service = CharacterImageService(
            db_session, image_client=client, storage_service=StubImageStorage()
        )
        result = service.generate_character_image(
            game_id=1,
            name="Test",
            description="test",
            style_hint="watercolor painting",
        )
        assert len(result) > 0
        assert client.last_generate_call is not None

    def test_multiple_generations(self, db_session):
        service = CharacterImageService(
            db_session,
            image_client=StubImageClient(),
            storage_service=StubImageStorage(),
        )
        r1 = service.generate_character_image(game_id=1, name="A", description="a")
        r2 = service.generate_character_image(game_id=1, name="B", description="b")
        r3 = service.generate_character_image(game_id=1, name="C", description="c")

        assert r1[0].entity_name == "A"
        assert r2[0].entity_name == "B"
        assert r3[0].entity_name == "C"
        # Each should have unique image IDs
        all_ids = [r1[0].image_id, r2[0].image_id, r3[0].image_id]
        assert len(set(all_ids)) == 3


class TestRegenerateDeletesDeactivatedFiles:
    """P3-存储修复：重生成后，停用的旧图片文件必须被删除。"""

    def test_regenerate_image_deletes_old_files(self, db_session):
        storage = StubImageStorage()
        service = CharacterImageService(
            db_session,
            image_client=StubImageClient(),
            storage_service=storage,
        )
        first = service.generate_character_image(
            game_id=1,
            name="del_test",
            description="test",
            entity_key="del_key",
        )
        service.regenerate_image(image_id=first[0].image_id)

        assert storage.deleted_paths == [storage.save_path]

    def test_regenerate_file_deletion_failure_does_not_fail_regeneration(self, db_session):
        storage = StubImageStorage()
        storage.delete_image = lambda *a, **k: (_ for _ in ()).throw(OSError("disk gone"))
        service = CharacterImageService(
            db_session,
            image_client=StubImageClient(),
            storage_service=storage,
        )
        first = service.generate_character_image(
            game_id=1,
            name="del_fail_test",
            description="test",
            entity_key="del_fail_key",
        )
        # 删除失败只记日志，重生成仍应成功返回新图片
        result = service.regenerate_image(image_id=first[0].image_id)
        assert len(result) == 1
        assert result[0].is_active is True
