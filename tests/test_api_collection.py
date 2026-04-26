"""Tests for collection API endpoints.

This module provides comprehensive API endpoint tests for the collection router,
including authentication, authorization, and error handling scenarios.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# API tests - collection endpoints
pytestmark = pytest.mark.api

from src.api.deps import get_current_user_optional  # noqa: E402
from src.api.routers.collection import router  # noqa: E402
from src.services.collection_service import (EntityNotFoundError,  # noqa: E402
                                             PermissionDeniedError)


@pytest.fixture
def app():
    """Create test app with collection router."""
    app = FastAPI()
    app.include_router(router, prefix="/collection")
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


# ==================== GET /{game_id} Tests ====================


class TestGetCollection:
    """Tests for GET /{game_id} - get collection list endpoint."""

    def test_get_collection_unauthorized(self, client):
        """Test that unauthenticated requests return 401."""
        response = client.get("/collection/1")
        assert response.status_code == 401
        assert "未登录" in response.json()["detail"]

    @patch("src.api.routers.collection.session_service")
    @patch("src.api.routers.collection.SessionLocal")
    @patch("src.api.routers.collection.CollectionService")
    def test_get_collection_success(
        self, mock_cs_class, mock_session_local, mock_session_service, app, client
    ):
        """Test successful collection retrieval."""
        mock_user = MagicMock()
        mock_user.user_id = 1

        mock_game_loop = MagicMock()
        mock_player_state = MagicMock()
        mock_player_state.characters = {}
        mock_player_state.items = {}
        mock_player_state.landmarks = {}
        mock_player_state.player_name = "TestPlayer"
        mock_player_state.character_settings = {
            "relationships": {"key_people": []},
            "family": {"family_members": []},
        }
        mock_game_loop.get_state.return_value = mock_player_state

        mock_session = MagicMock()
        mock_session.game_loop = mock_game_loop
        mock_session_service.get_or_restore.return_value = mock_session

        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_service = MagicMock()
        mock_service.get_collection.return_value = {
            "game_id": 1,
            "characters": [],
            "items": [],
            "landmarks": [],
            "total_characters": 0,
            "total_items": 0,
            "total_landmarks": 0,
        }
        mock_cs_class.return_value = mock_service

        app.dependency_overrides[get_current_user_optional] = lambda: mock_user
        try:
            response = client.get("/collection/1")
            assert response.status_code == 200
            data = response.json()
            assert "characters" in data
            assert "items" in data
            assert "landmarks" in data
        finally:
            app.dependency_overrides.clear()

    @patch("src.api.routers.collection.session_service")
    @patch("src.api.routers.collection.SessionLocal")
    @patch("src.api.routers.collection.CollectionService")
    def test_get_collection_empty(
        self, mock_cs_class, mock_session_local, mock_session_service, app, client
    ):
        """Test getting empty collection."""
        mock_user = MagicMock()
        mock_user.user_id = 1

        mock_game_loop = MagicMock()
        mock_player_state = MagicMock()
        mock_player_state.characters = {}
        mock_player_state.items = {}
        mock_player_state.landmarks = {}
        mock_player_state.player_name = "TestPlayer"
        mock_player_state.character_settings = {}
        mock_game_loop.get_state.return_value = mock_player_state

        mock_session = MagicMock()
        mock_session.game_loop = mock_game_loop
        mock_session_service.get_or_restore.return_value = mock_session

        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_service = MagicMock()
        mock_service.get_collection.return_value = {
            "game_id": 1,
            "characters": [],
            "items": [],
            "landmarks": [],
            "total_characters": 0,
            "total_items": 0,
            "total_landmarks": 0,
        }
        mock_cs_class.return_value = mock_service

        app.dependency_overrides[get_current_user_optional] = lambda: mock_user
        try:
            response = client.get("/collection/1")
            assert response.status_code == 200
            data = response.json()
            assert data["total_characters"] == 0
            assert data["total_items"] == 0
            assert data["total_landmarks"] == 0
        finally:
            app.dependency_overrides.clear()


# ==================== GET /{game_id}/details Tests ====================


class TestGetCollectionDetails:
    """Tests for GET /{game_id}/details endpoint."""

    def test_get_collection_details_unauthorized(self, client):
        """Test that unauthenticated requests return 401."""
        response = client.get("/collection/1/details")
        assert response.status_code == 401


# ==================== POST Generate Image Tests ====================


class TestGenerateCharacterImage:
    """Tests for POST /{game_id}/characters/{name}/generate-image endpoint."""

    def test_generate_character_image_unauthorized(self, client):
        """Test that unauthenticated requests return 401."""
        response = client.post("/collection/1/characters/TestChar/generate-image")
        assert response.status_code == 401

    @patch("src.api.routers.collection.session_service")
    @patch("src.api.routers.collection.SessionLocal")
    @patch("src.api.routers.collection.CollectionService")
    def test_generate_character_image_not_found(
        self, mock_cs_class, mock_session_local, mock_session_service, app, client
    ):
        """Test generating image for non-existent character returns 404."""
        mock_user = MagicMock()
        mock_user.user_id = 1

        mock_game_loop = MagicMock()
        mock_player_state = MagicMock()
        mock_player_state.characters = {}
        mock_player_state.player_name = "TestPlayer"
        mock_player_state.character_settings = {}
        mock_game_loop.get_state.return_value = mock_player_state

        mock_session = MagicMock()
        mock_session.game_loop = mock_game_loop
        mock_session_service.get_or_restore.return_value = mock_session

        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_service = MagicMock()
        mock_service.verify_game_ownership.return_value = MagicMock()
        mock_service.generate_character_image.side_effect = EntityNotFoundError(
            "角色 NotExist 不存在"
        )
        mock_cs_class.return_value = mock_service

        app.dependency_overrides[get_current_user_optional] = lambda: mock_user
        try:
            response = client.post("/collection/1/characters/NotExist/generate-image")
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()

    @patch("src.api.routers.collection.session_service")
    @patch("src.api.routers.collection.SessionLocal")
    @patch("src.api.routers.collection.CollectionService")
    def test_generate_character_image_success(
        self, mock_cs_class, mock_session_local, mock_session_service, app, client
    ):
        """Test successful character image generation."""
        mock_user = MagicMock()
        mock_user.user_id = 1

        mock_game_loop = MagicMock()
        mock_player_state = MagicMock()
        mock_player_state.characters = {"TestChar": {"name": "TestChar"}}
        mock_player_state.player_name = "TestPlayer"
        mock_player_state.character_settings = {}
        mock_game_loop.get_state.return_value = mock_player_state

        mock_session = MagicMock()
        mock_session.game_loop = mock_game_loop
        mock_session_service.get_or_restore.return_value = mock_session

        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_service = MagicMock()
        mock_service.verify_game_ownership.return_value = MagicMock()
        mock_service.generate_character_image.return_value = 123
        mock_cs_class.return_value = mock_service

        app.dependency_overrides[get_current_user_optional] = lambda: mock_user
        try:
            response = client.post("/collection/1/characters/TestChar/generate-image")
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["image_id"] == 123
        finally:
            app.dependency_overrides.clear()


class TestGenerateItemImage:
    """Tests for POST /{game_id}/items/{item_name}/generate-image endpoint."""

    def test_generate_item_image_unauthorized(self, client):
        """Test that unauthenticated requests return 401."""
        response = client.post("/collection/1/items/TestItem/generate-image")
        assert response.status_code == 401

    @patch("src.api.routers.collection.session_service")
    @patch("src.api.routers.collection.SessionLocal")
    @patch("src.api.routers.collection.CollectionService")
    def test_generate_item_image_not_found(
        self, mock_cs_class, mock_session_local, mock_session_service, app, client
    ):
        """Test generating image for non-existent item returns 404."""
        mock_user = MagicMock()
        mock_user.user_id = 1

        mock_game_loop = MagicMock()
        mock_player_state = MagicMock()
        mock_player_state.items = {}
        mock_game_loop.get_state.return_value = mock_player_state

        mock_session = MagicMock()
        mock_session.game_loop = mock_game_loop
        mock_session_service.get_or_restore.return_value = mock_session

        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_service = MagicMock()
        mock_service.verify_game_ownership.return_value = MagicMock()
        mock_service.generate_item_image.side_effect = EntityNotFoundError(
            "物品 NotExist 不存在"
        )
        mock_cs_class.return_value = mock_service

        app.dependency_overrides[get_current_user_optional] = lambda: mock_user
        try:
            response = client.post("/collection/1/items/NotExist/generate-image")
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


# ==================== POST Description Generation Tests ====================


class TestGenerateCharacterDescription:
    """Tests for POST /{game_id}/characters/{name}/generate-description endpoint."""

    def test_generate_character_description_unauthorized(self, client):
        """Test that unauthenticated requests return 401."""
        response = client.post("/collection/1/characters/TestChar/generate-description")
        assert response.status_code == 401

    @patch("src.api.routers.collection.session_service")
    def test_generate_character_description_already_exists(
        self, mock_session_service, app, client
    ):
        """Test that existing description returns success."""
        mock_user = MagicMock()
        mock_user.user_id = 1

        mock_game_loop = MagicMock()
        mock_player_state = MagicMock()
        mock_game_loop.get_state.return_value = mock_player_state

        mock_session = MagicMock()
        mock_session.game_loop = mock_game_loop
        mock_session_service.get_or_restore.return_value = mock_session

        app.dependency_overrides[get_current_user_optional] = lambda: mock_user
        try:
            response = client.post(
                "/collection/1/characters/TestChar/generate-description"
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "已存在" in data["message"]
        finally:
            app.dependency_overrides.clear()


# ==================== Error Scenarios Tests ====================


class TestCollectionErrorScenarios:
    """Tests for various error scenarios in collection endpoints."""

    @patch("src.api.routers.collection.session_service")
    def test_invalid_game_id_format(self, mock_session_service, client):
        """Test that invalid game_id returns appropriate error."""
        response = client.get("/collection/invalid")
        assert response.status_code == 422

    @patch("src.api.routers.collection.session_service")
    @patch("src.api.routers.collection.SessionLocal")
    @patch("src.api.routers.collection.CollectionService")
    def test_permission_denied_error(
        self, mock_cs_class, mock_session_local, mock_session_service, app, client
    ):
        """Test that permission denied raises 403."""
        mock_user = MagicMock()
        mock_user.user_id = 1

        mock_game_loop = MagicMock()
        mock_player_state = MagicMock()
        mock_player_state.characters = {
            "TestChar": {"name": "TestChar", "affinity": 30}
        }
        mock_player_state.player_name = "OtherPlayer"
        mock_player_state.character_settings = {}
        mock_game_loop.get_state.return_value = mock_player_state

        mock_session = MagicMock()
        mock_session.game_loop = mock_game_loop
        mock_session_service.get_or_restore.return_value = mock_session

        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_service = MagicMock()
        mock_service.verify_game_ownership.return_value = MagicMock()
        mock_service.validate_character_for_regenerate.side_effect = (
            PermissionDeniedError("亲密度不足，无法修改画像")
        )
        mock_cs_class.return_value = mock_service

        app.dependency_overrides[get_current_user_optional] = lambda: mock_user
        try:
            response = client.post(
                "/collection/1/characters/TestChar/regenerate-image",
                json={"feedback": "test"},
            )
            assert response.status_code == 403
        finally:
            app.dependency_overrides.clear()


# ==================== Recognize Entities Tests ====================


class TestRecognizeEntities:
    """Tests for POST /{game_id}/recognize-entities endpoint."""

    def test_recognize_entities_unauthorized(self, client):
        """Test that unauthenticated requests return 401."""
        response = client.post(
            "/collection/1/recognize-entities",
            json={"entity_types": ["item"], "min_appearances": 3},
        )
        assert response.status_code == 401


# ==================== Add Entities Tests ====================


class TestAddEntities:
    """Tests for POST /{game_id}/add-entities endpoint."""

    def test_add_entities_unauthorized(self, client):
        """Test that unauthenticated requests return 401."""
        response = client.post(
            "/collection/1/add-entities",
            json={"items": [], "characters": [], "landmarks": []},
        )
        assert response.status_code == 401


# ==================== Delete Endpoints Tests ====================


class TestDeleteItem:
    """Tests for DELETE /{game_id}/items/{item_name} endpoint."""

    def test_delete_item_unauthorized(self, client):
        """Test that unauthenticated requests return 401."""
        response = client.delete("/collection/1/items/TestItem")
        assert response.status_code == 401

    @patch("src.api.routers.collection.session_service")
    @patch("src.api.routers.collection.SessionLocal")
    @patch("src.api.routers.collection.CollectionService")
    def test_delete_item_not_found(
        self, mock_cs_class, mock_session_local, mock_session_service, app, client
    ):
        """Test deleting non-existent item returns 404."""
        mock_user = MagicMock()
        mock_user.user_id = 1

        mock_game_loop = MagicMock()
        mock_player_state = MagicMock()
        mock_player_state.items = {}
        mock_game_loop.get_state.return_value = mock_player_state

        mock_session = MagicMock()
        mock_session.game_loop = mock_game_loop
        mock_session_service.get_or_restore.return_value = mock_session

        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        mock_service = MagicMock()
        mock_service.delete_item.side_effect = EntityNotFoundError(
            "物品 NotExist 不存在"
        )
        mock_cs_class.return_value = mock_service

        app.dependency_overrides[get_current_user_optional] = lambda: mock_user
        try:
            response = client.delete("/collection/1/items/NotExist")
            assert response.status_code == 404
        finally:
            app.dependency_overrides.clear()


class TestDeleteCharacter:
    """Tests for DELETE /{game_id}/characters/{character_name} endpoint."""

    def test_delete_character_unauthorized(self, client):
        """Test that unauthenticated requests return 401."""
        response = client.delete("/collection/1/characters/TestChar")
        assert response.status_code == 401


class TestDeleteLandmark:
    """Tests for DELETE /{game_id}/landmarks/{landmark_name} endpoint."""

    def test_delete_landmark_unauthorized(self, client):
        """Test that unauthenticated requests return 401."""
        response = client.delete("/collection/1/landmarks/TestLandmark")
        assert response.status_code == 401
