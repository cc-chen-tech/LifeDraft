"""Tests for images router - simplified version."""

import asyncio
import threading

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# API tests - image endpoints
pytestmark = pytest.mark.api

from src.api.deps import get_current_user  # noqa: E402
from config.settings import Settings  # noqa: E402
from src.api.routers.images import get_session, verify_game_ownership  # noqa: E402
from src.api.routers.images import router, verify_image_ownership
from src.ai.image_exceptions import ImageProviderError  # noqa: E402
from src.services.image_service import (ImageContentError,  # noqa: E402
                                        ImageProviderServiceError)
from src.services.image_storage import ImageStorageError  # noqa: E402


@pytest.mark.asyncio
async def test_round_scene_generation_runs_outside_the_event_loop(
    monkeypatch: pytest.MonkeyPatch,
):
    """Long-running provider calls must not delay gameplay SSE and saves."""
    from src.api.routers import images
    from src.api.schemas import GenerateRoundSceneRequest

    service = MagicMock()
    service.storage_service.get_image_url.return_value = "/api/images/file/1/scene.jpg"
    service.generate_round_scene_image.return_value = SimpleNamespace(
        scene_id=7,
        game_id=1,
        week=2,
        round_number=1,
        story_date=None,
        day_index=None,
        stage="event",
        storage_path="/tmp/scene.jpg",
        storage_type="local",
        scene_description="雨夜的咖啡馆",
        created_at=None,
    )
    offloaded: list[object] = []

    async def run_in_test_threadpool(func, *args, **kwargs):
        offloaded.append(func)
        return func(*args, **kwargs)

    monkeypatch.setattr(images, "ImageService", lambda _db: service)
    monkeypatch.setattr(
        images,
        "run_in_threadpool",
        run_in_test_threadpool,
        raising=False,
    )
    monkeypatch.setattr(images, "verify_game_ownership", MagicMock())

    response = await images.generate_round_scene_image(
        GenerateRoundSceneRequest(
            game_id=1,
            week=2,
            round_number=1,
            story_text="沈言在雨夜的咖啡馆整理文稿。",
            character_settings={},
            player_name="沈言",
            stage="event",
        ),
        db=MagicMock(),
        user=1,
    )

    assert offloaded == [service.generate_round_scene_image]
    assert response.scene_id == 7


@pytest.mark.asyncio
async def test_opening_illustration_provider_wait_does_not_block_the_event_loop(
    monkeypatch: pytest.MonkeyPatch,
):
    """A slow synchronous provider must yield so unrelated async work can run."""
    from src.api.routers import images
    from src.api.schemas import GenerateOpeningIllustrationRequest

    release_provider = threading.Event()
    provider_timed_out = False

    class SlowImageService:
        def __init__(self, _db):
            pass

        def generate_opening_illustration(self, **_kwargs):
            nonlocal provider_timed_out
            if not release_provider.wait(timeout=0.2):
                provider_timed_out = True
            return SimpleNamespace(
                image_id=9,
                game_id=1,
                metadata_json={"scene_description": "窗边的第一幕"},
                prompt_text="opening prompt",
                created_at=None,
            )

        @staticmethod
        def get_image_url(_image):
            return "/api/images/file/1/opening/9.png"

    async def release_on_next_event_loop_turn() -> None:
        await asyncio.sleep(0.01)
        release_provider.set()

    monkeypatch.setattr(images, "ImageService", SlowImageService)
    monkeypatch.setattr(images, "verify_game_ownership", MagicMock())

    release_task = asyncio.create_task(release_on_next_event_loop_turn())
    response = await images.generate_opening_illustration(
        GenerateOpeningIllustrationRequest(
            game_id=1,
            story_text="沈言站在窗边，准备走进新的人生。",
            character_settings={},
            player_name="沈言",
        ),
        db=MagicMock(),
        user=1,
    )
    await release_task

    assert provider_timed_out is False
    assert response.image_id == 9


@pytest.mark.asyncio
async def test_character_image_provider_wait_does_not_block_the_event_loop(
    monkeypatch: pytest.MonkeyPatch,
):
    """The general image route must not run a provider on the event loop."""
    from src.api.routers import images
    from src.api.schemas import GenerateImageRequest

    release_provider = threading.Event()
    provider_timed_out = False

    class SlowImageService:
        def __init__(self, _db):
            pass

        def generate_character_image(self, **_kwargs):
            nonlocal provider_timed_out
            if not release_provider.wait(timeout=0.2):
                provider_timed_out = True
            return [
                SimpleNamespace(
                    image_id=10,
                    game_id=1,
                    image_type="character",
                    entity_name="沈言",
                    entity_key="player",
                    prompt_text="portrait prompt",
                    version=1,
                    created_at=None,
                )
            ]

        @staticmethod
        def get_image_url(_image):
            return "/api/images/file/1/character/10.png"

    async def release_on_next_event_loop_turn() -> None:
        await asyncio.sleep(0.01)
        release_provider.set()

    monkeypatch.setattr(images, "ImageService", SlowImageService)
    monkeypatch.setattr(images, "verify_game_ownership", MagicMock())

    release_task = asyncio.create_task(release_on_next_event_loop_turn())
    response = await images.generate_image(
        GenerateImageRequest(
            game_id=1,
            image_type="character",
            entity_name="沈言",
            description="调查记者",
        ),
        db=MagicMock(),
        user=1,
    )
    await release_task

    assert provider_timed_out is False
    assert response.total == 1


@pytest.mark.asyncio
async def test_batch_character_provider_wait_does_not_block_the_event_loop(
    monkeypatch: pytest.MonkeyPatch,
):
    """Batch generation must offload each synchronous provider request."""
    from src.api.routers import images
    from src.api.schemas import BatchGenerateCharactersRequest

    release_provider = threading.Event()
    provider_timed_out = False

    class SlowImageService:
        def __init__(self, _db):
            pass

        def generate_character_image(self, **_kwargs):
            nonlocal provider_timed_out
            if not release_provider.wait(timeout=0.2):
                provider_timed_out = True
            return [
                SimpleNamespace(
                    image_id=11,
                    game_id=1,
                    image_type="character",
                    entity_name="林岚",
                    entity_key="npc_林岚",
                    prompt_text="family portrait prompt",
                    version=1,
                    created_at=None,
                )
            ]

        @staticmethod
        def get_image_url(_image):
            return "/api/images/file/1/character/11.png"

    async def release_on_next_event_loop_turn() -> None:
        await asyncio.sleep(0.01)
        release_provider.set()

    monkeypatch.setattr(images, "ImageService", SlowImageService)
    monkeypatch.setattr(images, "verify_game_ownership", MagicMock())

    release_task = asyncio.create_task(release_on_next_event_loop_turn())
    response = await images.batch_generate_character_images(
        BatchGenerateCharactersRequest(
            game_id=1,
            character_settings={
                "family": {"family_members": [{"name": "林岚", "role": "姐姐"}]}
            },
        ),
        db=MagicMock(),
        user=1,
    )
    await release_task

    assert provider_timed_out is False
    assert response.total == 1


@pytest.mark.asyncio
async def test_round_scene_regeneration_wait_does_not_block_the_event_loop(
    monkeypatch: pytest.MonkeyPatch,
):
    """Scene regeneration must use the same non-blocking provider boundary."""
    from src.api.routers import images
    from src.api.schemas import RegenerateRoundSceneRequest

    release_provider = threading.Event()
    provider_timed_out = False

    class SlowImageService:
        def __init__(self, _db):
            self.storage_service = SimpleNamespace(
                get_image_url=lambda _path, _storage_type: "/api/images/file/1/scene/12.png"
            )

        def regenerate_round_scene_image(self, **_kwargs):
            nonlocal provider_timed_out
            if not release_provider.wait(timeout=0.2):
                provider_timed_out = True
            return SimpleNamespace(
                scene_id=12,
                game_id=1,
                week=0,
                round_number=1,
                stage="event",
                storage_path="/tmp/scene-12.png",
                storage_type="local",
                scene_description="窗边的采访",
                created_at=None,
            )

    async def release_on_next_event_loop_turn() -> None:
        await asyncio.sleep(0.01)
        release_provider.set()

    monkeypatch.setattr(images, "ImageService", SlowImageService)
    monkeypatch.setattr(images, "verify_game_ownership", MagicMock())

    release_task = asyncio.create_task(release_on_next_event_loop_turn())
    response = await images.regenerate_round_scene_image(
        RegenerateRoundSceneRequest(
            game_id=1,
            round_number=1,
            story_text="沈言完成了采访。",
            player_name="沈言",
            user_prompt="改成黄昏",
            current_scene_id=2,
        ),
        db=MagicMock(),
        user=1,
    )
    await release_task

    assert provider_timed_out is False
    assert response.scene_id == 12


@pytest.fixture
def app():
    """Create test app with images router."""
    app = FastAPI()
    app.include_router(router, prefix="/images")
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestVerifyGameOwnership:
    """Test verify_game_ownership function."""

    def test_verify_game_ownership_success(self):
        """Test successful game ownership verification."""
        mock_db = MagicMock()
        mock_game = MagicMock()
        mock_game.user_id = 1
        mock_db.query.return_value.filter.return_value.first.return_value = mock_game

        result = verify_game_ownership(mock_db, 1, 1)
        assert result == mock_game

    def test_verify_game_ownership_game_not_found(self):
        """Test when game is not found."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            verify_game_ownership(mock_db, 999, 1)
        assert exc.value.status_code == 404

    def test_verify_game_ownership_wrong_user(self):
        """Test when game belongs to different user."""
        mock_db = MagicMock()
        mock_game = MagicMock()
        mock_game.user_id = 2
        mock_db.query.return_value.filter.return_value.first.return_value = mock_game

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            verify_game_ownership(mock_db, 1, 1)
        assert exc.value.status_code == 404

    def test_verify_game_ownership_no_user_id_backward_compat(self):
        """Test backward compatibility when game has no user_id."""
        mock_db = MagicMock()
        mock_game = MagicMock()
        mock_game.user_id = None
        mock_db.query.return_value.filter.return_value.first.return_value = mock_game

        result = verify_game_ownership(mock_db, 1, 1)
        assert result == mock_game


class TestVerifyImageOwnership:
    """Test verify_image_ownership function."""

    def test_verify_image_ownership_success(self):
        """Test successful image ownership verification."""
        mock_db = MagicMock()
        mock_image = MagicMock()
        mock_image.game_id = 1
        mock_image.image_id = 1
        mock_db.query.return_value.filter.return_value.first.return_value = mock_image

        with patch("src.api.routers.images.verify_game_ownership") as mock_verify:
            verify_image_ownership(mock_db, 1, 1)
            mock_verify.assert_called_once()

    def test_verify_image_ownership_not_found(self):
        """Test when image is not found."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc:
            verify_image_ownership(mock_db, 999, 1)
        assert exc.value.status_code == 404


class TestGetImageFileEndpoint:
    """Test /file/{game_id}/{image_type}/{filename} endpoint."""

    @patch("src.api.routers.images.ImageStorageService")
    def test_get_image_file_success(self, mock_storage_class, app, client):
        """Test getting image file."""
        from pathlib import Path

        # Mock auth dependency
        app.dependency_overrides[get_current_user] = lambda: 1

        mock_storage = MagicMock()
        mock_storage.image_exists.return_value = True
        mock_storage.get_image_data.return_value = b"fake_image_data"
        mock_storage.local_path = Path("/data/images")
        mock_storage_class.return_value = mock_storage

        # P0-IDOR 修复后，端点先做归属校验：mock 一个属于 user_id=1 的游戏
        mock_db = MagicMock()
        mock_game = MagicMock()
        mock_game.user_id = 1
        mock_db.query.return_value.filter.return_value.first.return_value = mock_game

        def override_get_session():
            yield mock_db

        app.dependency_overrides[get_session] = override_get_session
        try:
            response = client.get("/images/file/1/character/test.png")

            assert response.status_code == 200
            assert response.content == b"fake_image_data"
        finally:
            app.dependency_overrides.clear()

    @patch("src.api.routers.images.ImageStorageService")
    def test_get_image_file_storage_error(self, mock_storage_class, app, client):
        """Test handling storage error."""
        from pathlib import Path

        # Mock auth dependency
        app.dependency_overrides[get_current_user] = lambda: 1

        mock_storage = MagicMock()
        mock_storage.image_exists.return_value = True
        mock_storage.get_image_data.side_effect = ImageStorageError("Storage error")
        mock_storage.local_path = Path("/data/images")
        mock_storage_class.return_value = mock_storage

        mock_db = MagicMock()
        mock_game = MagicMock()
        mock_game.user_id = 1
        mock_db.query.return_value.filter.return_value.first.return_value = mock_game

        def override_get_session():
            yield mock_db

        app.dependency_overrides[get_session] = override_get_session
        try:
            response = client.get("/images/file/1/character/test.png")

            assert response.status_code == 500
        finally:
            app.dependency_overrides.clear()

    @patch("src.api.routers.images.ImageStorageService")
    def test_get_image_file_rejects_unowned_game(self, mock_storage_class, app, client):
        """P0-IDOR：图片文件属于他人游戏时返回 404，而不是返回图片内容。"""
        from pathlib import Path

        # Mock auth dependency
        app.dependency_overrides[get_current_user] = lambda: 1

        mock_storage = MagicMock()
        mock_storage.image_exists.return_value = True
        mock_storage.get_image_data.return_value = b"fake_image_data"
        mock_storage.local_path = Path("/data/images")
        mock_storage_class.return_value = mock_storage

        # 游戏属于 user_id=999，当前用户是 1 → 归属校验必须拦截
        mock_db = MagicMock()
        mock_game = MagicMock()
        mock_game.user_id = 999
        mock_db.query.return_value.filter.return_value.first.return_value = mock_game

        def override_get_session():
            yield mock_db

        app.dependency_overrides[get_session] = override_get_session
        try:
            response = client.get("/images/file/1/character/test.png")

            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


class TestGetImageEndpoint:
    """Test /{image_id} endpoint."""

    @patch("src.api.routers.images.ImageService")
    def test_get_image_success(self, mock_service_class, client):
        """Test getting image by ID."""
        mock_service = MagicMock()
        mock_image = MagicMock()
        mock_image.image_id = 1
        mock_image.game_id = 1
        mock_image.image_type = "character"
        mock_image.entity_name = "Test"
        mock_image.entity_key = "player"
        mock_image.prompt_text = "prompt"
        mock_image.version = 1
        mock_image.created_at = None
        mock_service.get_image.return_value = mock_image
        mock_service.get_image_url.return_value = "/images/file/1/character/test.png"
        mock_service_class.return_value = mock_service

        with patch("src.api.routers.images.get_session") as mock_session_gen:
            mock_session_gen.return_value = iter([MagicMock()])
            response = client.get("/images/1")

        assert response.status_code == 200
        data = response.json()
        assert data["image_id"] == 1

    @patch("src.api.routers.images.ImageService")
    def test_get_image_not_found(self, mock_service_class, client):
        """Test getting non-existent image."""
        mock_service = MagicMock()
        mock_service.get_image.return_value = None
        mock_service_class.return_value = mock_service

        with patch("src.api.routers.images.get_session") as mock_session_gen:
            mock_session_gen.return_value = iter([MagicMock()])
            response = client.get("/images/999")

        assert response.status_code == 404


class TestDeleteImageEndpoint:
    """Test DELETE /{image_id} endpoint."""

    @patch("src.api.routers.images.ImageService")
    def test_delete_image_not_found(self, mock_service_class, client):
        """Test deleting non-existent image."""
        mock_service = MagicMock()
        mock_service.get_image.return_value = None
        mock_service_class.return_value = mock_service

        with patch("src.api.routers.images.get_session") as mock_session_gen:
            mock_session_gen.return_value = iter([MagicMock()])
            response = client.delete("/images/999")

        assert response.status_code == 404


class TestImageMetadataEndpointsWithoutProviderConfig:
    """Image metadata lookups should not require image generation credentials."""

    def test_get_missing_image_returns_404_without_image_api_key(self, app, monkeypatch):
        monkeypatch.setattr(Settings, "IMAGE_API_KEY", None)
        monkeypatch.setattr(Settings, "OPENAI_API_KEY", None)

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        def override_get_session():
            yield mock_db

        app.dependency_overrides[get_session] = override_get_session
        try:
            response = TestClient(app, raise_server_exceptions=False).get("/images/999999")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 404

    def test_delete_missing_image_returns_404_without_image_api_key(self, app, monkeypatch):
        monkeypatch.setattr(Settings, "IMAGE_API_KEY", None)
        monkeypatch.setattr(Settings, "OPENAI_API_KEY", None)

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        def override_get_session():
            yield mock_db

        app.dependency_overrides[get_session] = override_get_session
        try:
            response = TestClient(app, raise_server_exceptions=False).delete("/images/999999")
        finally:
            app.dependency_overrides.clear()

        assert response.status_code == 404


# ==================== Path Traversal Security Tests ====================


class TestPathTraversalSecurity:
    """Test path traversal attack prevention."""

    @patch("src.api.routers.images.ImageStorageService")
    def test_path_traversal_rejected_dot_dot(self, mock_storage_class, app, client):
        """Test that path traversal with .. is rejected."""
        from pathlib import Path

        app.dependency_overrides[get_current_user] = lambda: 1

        mock_storage = MagicMock()
        mock_storage.image_exists.return_value = False
        mock_storage.local_path = Path("/data/images")
        mock_storage_class.return_value = mock_storage

        try:
            with patch("src.api.routers.images.get_session") as mock_session_gen:
                mock_session_gen.return_value = iter([MagicMock()])
                response = client.get("/images/file/1/character/../../../etc/passwd")

            # Should return 400 or 404, not actual file content
            assert response.status_code in (400, 404)
        finally:
            app.dependency_overrides.clear()

    @patch("src.api.routers.images.ImageStorageService")
    def test_path_traversal_rejected_encoded(self, mock_storage_class, app, client):
        """Test that URL-encoded path traversal is rejected."""
        from pathlib import Path

        app.dependency_overrides[get_current_user] = lambda: 1

        mock_storage = MagicMock()
        mock_storage.image_exists.return_value = False
        mock_storage.local_path = Path("/data/images")
        mock_storage_class.return_value = mock_storage

        try:
            with patch("src.api.routers.images.get_session") as mock_session_gen:
                mock_session_gen.return_value = iter([MagicMock()])
                response = client.get("/images/file/1/character/%2e%2e%2fetc%2fpasswd")

            assert response.status_code in (400, 404)
        finally:
            app.dependency_overrides.clear()


# ==================== POST Generate Image Tests ====================


class TestGenerateImageEndpoint:
    """Test POST /generate endpoint."""

    @patch("src.api.routers.images.ImageService")
    def test_generate_image_unauthorized(self, mock_service_class, app, client):
        """Test that unauthenticated requests return 401."""

        # Don't override auth - should be None
        with patch("src.api.routers.images.get_session") as mock_session_gen:
            mock_session_gen.return_value = iter([MagicMock()])
            response = client.post(
                "/images/generate",
                json={
                    "game_id": 1,
                    "image_type": "character",
                    "entity_name": "Test",
                    "description": "Test description",
                },
            )

        assert response.status_code == 401

    @patch("src.api.routers.images.ImageService")
    @patch("src.api.routers.images.verify_game_ownership")
    def test_generate_image_capacity_failure_returns_structured_503(
        self,
        mock_verify,
        mock_service_class,
        app,
        client,
    ):
        from src.api.deps import get_current_user_optional

        mock_user = MagicMock()
        mock_user.user_id = 1
        app.dependency_overrides[get_current_user_optional] = lambda: mock_user
        mock_verify.return_value = MagicMock()
        mock_service_class.return_value.generate_character_image.side_effect = (
            ImageProviderServiceError.from_provider(
                ImageProviderError(
                    code="minimax_2056",
                    category="capacity",
                    retryable=False,
                    public_message="图片生成额度暂时不可用，请稍后再试",
                )
            )
        )

        try:
            with patch("src.api.routers.images.get_session") as mock_session_gen:
                mock_session_gen.return_value = iter([MagicMock()])
                response = client.post(
                    "/images/generate",
                    json={
                        "game_id": 1,
                        "image_type": "character",
                        "entity_name": "林见微",
                        "description": "现代职场人物",
                    },
                )

            assert response.status_code == 503
            assert response.json()["detail"] == {
                "code": "minimax_2056",
                "message": "图片生成额度暂时不可用，请稍后再试",
                "retryable": False,
            }
        finally:
            app.dependency_overrides.clear()

    @patch("src.api.routers.images.ImageService")
    @patch("src.api.routers.images.verify_game_ownership")
    def test_generate_image_success(self, mock_verify, mock_service_class, app, client):
        """Test successful image generation."""
        from src.api.deps import get_current_user_optional

        mock_user = MagicMock()
        mock_user.user_id = 1
        app.dependency_overrides[get_current_user_optional] = lambda: mock_user

        mock_service = MagicMock()
        mock_image = MagicMock()
        mock_image.image_id = 1
        mock_image.game_id = 1
        mock_image.image_type = "character"
        mock_image.entity_name = "Test"
        mock_image.entity_key = "player"
        mock_image.prompt_text = "test prompt"
        mock_image.version = 1
        mock_image.created_at = None
        mock_service.generate_character_image.return_value = [mock_image]
        mock_service.get_image_url.return_value = "/images/file/1/character/test.png"
        mock_service_class.return_value = mock_service

        mock_verify.return_value = MagicMock()

        try:
            with patch("src.api.routers.images.get_session") as mock_session_gen:
                mock_session_gen.return_value = iter([MagicMock()])
                response = client.post(
                    "/images/generate",
                    json={
                        "game_id": 1,
                        "image_type": "character",
                        "entity_name": "Test",
                        "description": "Test description",
                    },
                )

            assert response.status_code == 200
            data = response.json()
            assert "images" in data
            assert data["total"] >= 0
        finally:
            app.dependency_overrides.clear()

    @patch("src.api.routers.images.ImageService")
    @patch("src.api.routers.images.verify_game_ownership")
    def test_generate_image_invalid_type(self, mock_verify, mock_service_class, app, client):
        """Test generating image with invalid type."""
        from src.api.deps import get_current_user_optional

        mock_user = MagicMock()
        mock_user.user_id = 1
        app.dependency_overrides[get_current_user_optional] = lambda: mock_user

        mock_verify.return_value = MagicMock()

        try:
            with patch("src.api.routers.images.get_session") as mock_session_gen:
                mock_session_gen.return_value = iter([MagicMock()])
                response = client.post(
                    "/images/generate",
                    json={
                        "game_id": 1,
                        "image_type": "invalid_type",
                        "entity_name": "Test",
                        "description": "Test",
                    },
                )

            # Invalid type should return 400 or 500 (depending on error handling)
            assert response.status_code in (400, 500)
        finally:
            app.dependency_overrides.clear()

    @patch("src.api.routers.images.ImageService")
    @patch("src.api.routers.images.verify_game_ownership")
    def test_generate_image_content_error(self, mock_verify, mock_service_class, app, client):
        """Test handling content moderation error."""
        from src.api.deps import get_current_user_optional

        mock_user = MagicMock()
        mock_user.user_id = 1
        app.dependency_overrides[get_current_user_optional] = lambda: mock_user

        mock_service = MagicMock()
        mock_service.generate_character_image.side_effect = ImageContentError(
            "Content moderation failed"
        )
        mock_service_class.return_value = mock_service

        mock_verify.return_value = MagicMock()

        try:
            with patch("src.api.routers.images.get_session") as mock_session_gen:
                mock_session_gen.return_value = iter([MagicMock()])
                response = client.post(
                    "/images/generate",
                    json={
                        "game_id": 1,
                        "image_type": "character",
                        "entity_name": "Test",
                        "description": "Test",
                    },
                )

            assert response.status_code == 400
            assert "敏感内容" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()


# ==================== Image File Not Found Tests ====================


class TestImageFileNotFound:
    """Test image file not found scenarios."""

    @patch("src.api.routers.images.ImageStorageService")
    def test_get_image_file_not_exists(self, mock_storage_class, app, client):
        """Test getting non-existent image file returns 404 or 500."""
        from pathlib import Path

        app.dependency_overrides[get_current_user] = lambda: 1

        mock_storage = MagicMock()
        mock_storage.image_exists.return_value = False
        mock_storage.local_path = Path("/data/images")
        mock_storage_class.return_value = mock_storage

        # 归属校验通过的 mock 会话（避免依赖真实 DB 状态）
        mock_db = MagicMock()
        mock_game = MagicMock()
        mock_game.user_id = 1
        mock_db.query.return_value.filter.return_value.first.return_value = mock_game

        def override_get_session():
            yield mock_db

        app.dependency_overrides[get_session] = override_get_session
        try:
            response = client.get("/images/file/1/character/nonexistent.png")

            # Not found should return 404 or 500 (depending on error handling)
            assert response.status_code in (404, 500)
        finally:
            app.dependency_overrides.clear()


# ==================== Invalid Parameter Tests ====================


class TestInvalidParameters:
    """Test invalid parameter handling."""

    def test_get_image_invalid_id(self, client):
        """Test getting image with invalid ID format."""
        response = client.get("/images/invalid")
        assert response.status_code == 422

    def test_generate_image_missing_fields(self, client):
        """Test generating image with missing required fields."""
        response = client.post("/images/generate", json={})
        assert response.status_code == 422


# ==================== Round Scene Image Tests ====================


class TestRoundSceneImage:
    """Test round scene image endpoint with week parameter."""

    def test_get_round_scene_image_requires_week(self, client):
        """Test that week parameter is required to prevent returning wrong week images.

        This is a regression test for the issue where not passing week parameter
        would return images from other weeks with the same round number.
        """
        # Without week parameter - should fail with 422 validation error
        # because week is now a required parameter
        response = client.get("/images/scene/1/0")
        assert response.status_code == 422, (
            "Week parameter should be required to prevent returning wrong week images. "
            "This prevents the bug where images from different weeks but same round were returned."
        )
