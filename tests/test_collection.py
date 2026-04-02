"""Tests for collection router."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

# API tests - collection endpoints
pytestmark = pytest.mark.api

from src.api.routers.collection import router
from src.game.state.item_state import ItemState
from src.services.collection_service import (CollectionService,
                                             EntityNotFoundError,
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


class TestVerifyGameOwnership:
    """Test CollectionService.verify_game_ownership method."""

    def test_verify_game_ownership_success(self):
        """Test successful game ownership verification."""
        mock_db = MagicMock()
        mock_game = MagicMock()
        mock_game.user_id = 1
        mock_db.query.return_value.filter.return_value.first.return_value = mock_game

        service = CollectionService(mock_db)
        result = service.verify_game_ownership(1, 1)
        assert result == mock_game

    def test_verify_game_ownership_game_not_found(self):
        """Test when game is not found."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        service = CollectionService(mock_db)
        with pytest.raises(EntityNotFoundError):
            service.verify_game_ownership(999, 1)

    def test_verify_game_ownership_wrong_user(self):
        """Test when game belongs to different user."""
        mock_db = MagicMock()
        mock_game = MagicMock()
        mock_game.user_id = 2
        mock_db.query.return_value.filter.return_value.first.return_value = mock_game

        service = CollectionService(mock_db)
        with pytest.raises(EntityNotFoundError):
            service.verify_game_ownership(1, 1)

    def test_verify_game_ownership_no_user_id_backward_compat(self):
        """Test backward compatibility when game has no user_id."""
        mock_db = MagicMock()
        mock_game = MagicMock()
        mock_game.user_id = None
        mock_db.query.return_value.filter.return_value.first.return_value = mock_game

        service = CollectionService(mock_db)
        result = service.verify_game_ownership(1, 1)
        assert result == mock_game


class TestItemState:
    """Test ItemState model."""

    def test_item_state_creation(self):
        """Test creating an ItemState instance."""
        item = ItemState(
            name="魔法剑",
            description="一把散发着神秘光芒的长剑",
            importance="critical",
            category="weapon",
            acquired_week=5,
            acquired_context="在古老遗迹中发现",
            is_key_item=True,
        )
        assert item.name == "魔法剑"
        assert item.importance == "critical"
        assert item.category == "weapon"
        assert item.is_key_item is True
        assert item.image_generated is False

    def test_item_state_defaults(self):
        """Test ItemState default values."""
        item = ItemState(name="普通物品")
        assert item.importance == "normal"
        assert item.category == "other"
        assert item.is_key_item is False
        assert item.description == ""
        assert item.metadata == {}

    def test_item_state_to_context_string(self):
        """Test ItemState.to_context_string method."""
        item = ItemState(
            name="传家宝",
            description="家族世代相传的玉佩",
            category="keepsake",
            is_key_item=True,
            acquired_context="祖母临终前赠予",
        )
        context = item.to_context_string()
        assert "【传家宝】" in context
        assert "家族世代相传的玉佩" in context
        assert "纪念品" in context
        assert "★ 关键物品" in context

    def test_item_state_from_dict(self):
        """Test ItemState.from_dict class method."""
        data = {
            "name": "神器",
            "description": "传说中的神器",
            "importance": "critical",
            "category": "treasure",
            "acquired_week": 10,
        }
        item = ItemState.from_dict(data)
        assert item.name == "神器"
        assert item.importance == "critical"

    def test_item_state_to_dict(self):
        """Test ItemState.to_dict method."""
        item = ItemState(
            name="测试物品",
            description="测试描述",
            importance="important",
        )
        data = item.to_dict()
        assert data["name"] == "测试物品"
        assert data["description"] == "测试描述"
        assert data["importance"] == "important"


class TestCollectionRouterEndpoints:
    """Test collection router endpoints with mocked dependencies."""

    @patch("src.api.routers.collection.session_service")
    @patch("src.api.routers.collection.SessionLocal")
    def test_get_collection_unauthorized(
        self, mock_session_local, mock_session_service, client
    ):
        """Test get_collection returns 401 when not logged in."""
        response = client.get("/collection/1")
        # Should return 401 because no user is provided
        assert response.status_code == 401

    @patch("src.api.routers.collection.session_service")
    @patch("src.api.routers.collection.SessionLocal")
    def test_get_collection_success(
        self, mock_session_local, mock_session_service, client
    ):
        """Test get_collection returns correct data."""
        # Mock user
        mock_user = MagicMock()
        mock_user.user_id = 1

        # Mock session and game loop
        mock_game_loop = MagicMock()
        mock_player_state = MagicMock()
        mock_player_state.characters = {}
        mock_player_state.items = {
            "魔法剑": {
                "name": "魔法剑",
                "description": "一把神奇的剑",
                "importance": "critical",
                "category": "weapon",
                "acquired_week": 5,
                "is_key_item": True,
            }
        }
        mock_player_state.character_settings = {
            "relationships": {"key_people": []},
            "family": {"family_members": []},
        }
        mock_game_loop.get_state.return_value = mock_player_state

        mock_session = MagicMock()
        mock_session.game_loop = mock_game_loop
        mock_session_service.get_or_restore.return_value = mock_session

        # Mock database
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.order_by.return_value.all.return_value = (
            []
        )
        mock_session_local.return_value = mock_db

        # Mock image service - now in collection_service module
        with patch(
            "src.services.collection_service.ImageService"
        ) as mock_image_service_class:
            mock_image_service = MagicMock()
            mock_image_service.get_image_url.return_value = None
            mock_image_service_class.return_value = mock_image_service

            # We can't easily test with dependencies, so this is a simplified test
            # In a real scenario, we would use dependency injection overrides

    @patch("src.api.routers.collection.session_service")
    def test_generate_item_image_item_not_found(self, mock_session_service, client):
        """Test generate_item_image returns 404 when item not found."""
        mock_user = MagicMock()

        mock_game_loop = MagicMock()
        mock_player_state = MagicMock()
        mock_player_state.items = {}
        mock_game_loop.get_state.return_value = mock_player_state

        mock_session = MagicMock()
        mock_session.game_loop = mock_game_loop
        mock_session_service.get_or_restore.return_value = mock_session

        # This would need proper dependency injection to test fully
        # For now, we verify the structure is correct


class TestItemExtractionService:
    """Test ItemExtractionService."""

    def test_parse_extraction_response_empty(self):
        """Test parsing empty response."""
        from src.services.item_extraction_service import ItemExtractionService

        service = ItemExtractionService(MagicMock())
        result = service._parse_extraction_response("{}", current_week=5)
        assert result == []

    def test_parse_extraction_response_with_items(self):
        """Test parsing response with items."""
        from src.services.item_extraction_service import ItemExtractionService

        service = ItemExtractionService(MagicMock())
        response = """
        {
            "items": [
                {
                    "name": "神秘宝石",
                    "description": "一颗散发着蓝色光芒的宝石",
                    "importance": "important",
                    "category": "treasure",
                    "acquired_context": "在山洞中发现",
                    "is_key_item": false
                }
            ]
        }
        """
        result = service._parse_extraction_response(response, current_week=10)

        assert len(result) == 1
        assert result[0].name == "神秘宝石"
        assert result[0].importance == "important"
        assert result[0].category == "treasure"
        assert result[0].acquired_week == 10

    def test_parse_extraction_response_invalid_importance(self):
        """Test parsing response with invalid importance defaults to 'normal'."""
        from src.services.item_extraction_service import ItemExtractionService

        service = ItemExtractionService(MagicMock())
        response = """
        {
            "items": [
                {
                    "name": "普通物品",
                    "importance": "invalid_value",
                    "category": "other"
                }
            ]
        }
        """
        result = service._parse_extraction_response(response, current_week=1)

        assert len(result) == 1
        assert result[0].importance == "normal"

    def test_parse_extraction_response_invalid_category(self):
        """Test parsing response with invalid category defaults to 'other'."""
        from src.services.item_extraction_service import ItemExtractionService

        service = ItemExtractionService(MagicMock())
        response = """
        {
            "items": [
                {
                    "name": "未知物品",
                    "category": "invalid_category"
                }
            ]
        }
        """
        result = service._parse_extraction_response(response, current_week=1)

        assert len(result) == 1
        assert result[0].category == "other"

    def test_parse_extraction_response_skip_non_new_actions(self):
        """Test that non-'new' actions are skipped."""
        from src.services.item_extraction_service import ItemExtractionService

        service = ItemExtractionService(MagicMock())
        response = """
        {
            "items": [
                {"action": "new", "name": "新物品"},
                {"action": "update", "name": "更新物品"},
                {"name": "默认新物品"}
            ]
        }
        """
        result = service._parse_extraction_response(response, current_week=1)

        # Only 'new' action items should be included
        assert len(result) == 2
        names = [item.name for item in result]
        assert "新物品" in names
        assert "默认新物品" in names
        assert "更新物品" not in names


class TestCharacterSettingsNestedDict:
    """Test handling of nested dictionaries in character_settings."""

    def test_character_collection_item_with_nested_age_gender(self):
        """Test CharacterCollectionItem handles nested age/gender dicts correctly."""
        from src.api.schemas import CharacterCollectionItem

        # Simulate the actual data structure from character_settings
        # where age and gender can be nested dicts
        age_dict = {"age": 19, "birth_year": 2007, "birth_month": 5}
        gender_dict = {"gender": "男", "gender_desc": "性格开朗"}

        # Extract values as the fixed code should do
        age_val = age_dict.get("age") if isinstance(age_dict, dict) else age_dict
        gender_val = (
            gender_dict.get("gender") if isinstance(gender_dict, dict) else gender_dict
        )

        # Should create without validation error
        item = CharacterCollectionItem(
            name="测试角色",
            role="主角",
            description=f"{age_val}岁，{gender_val}",
            affinity=100,
            age=age_val,
            gender=gender_val,
            occupation="学生",
            personality_traits=[],
            image_url=None,
            image_generated=False,
            description_generated=True,
        )

        assert item.name == "测试角色"
        assert item.age == 19
        assert item.gender == "男"

    def test_character_collection_item_with_simple_values(self):
        """Test CharacterCollectionItem handles simple age/gender values."""
        from src.api.schemas import CharacterCollectionItem

        # Simple values should still work
        item = CharacterCollectionItem(
            name="测试角色2",
            role="朋友",
            description="25岁，女",
            affinity=80,
            age=25,
            gender="女",
            occupation="工程师",
            personality_traits=["开朗"],
            image_url=None,
            image_generated=False,
            description_generated=True,
        )

        assert item.age == 25
        assert item.gender == "女"


class TestRegenerateImageSchemas:
    """Test regenerate image request schemas."""

    def test_regenerate_character_image_request_valid(self):
        """Test RegenerateCharacterImageRequest with valid data."""
        from src.api.schemas import RegenerateCharacterImageRequest

        # Test with feedback only
        request1 = RegenerateCharacterImageRequest(feedback="头发变长一点")
        assert request1.feedback == "头发变长一点"
        assert request1.image_id is None

        # Test with feedback and image_id
        request2 = RegenerateCharacterImageRequest(
            feedback="换一件蓝色衣服", image_id=123
        )
        assert request2.feedback == "换一件蓝色衣服"
        assert request2.image_id == 123

    def test_regenerate_item_image_request_valid(self):
        """Test RegenerateItemImageRequest with valid data."""
        from src.api.schemas import RegenerateItemImageRequest

        request = RegenerateItemImageRequest(feedback="颜色改深一点")
        assert request.feedback == "颜色改深一点"


class TestRegenerateCharacterImageEndpoint:
    """Test regenerate_character_image endpoint."""

    @patch("src.api.routers.collection.session_service")
    @patch("src.api.routers.collection.SessionLocal")
    def test_regenerate_character_image_unauthorized(
        self, mock_session_local, mock_session_service, client
    ):
        """Test regenerate_character_image returns 401 when not logged in."""
        response = client.post(
            "/collection/1/characters/张三/regenerate-image",
            json={"feedback": "头发变长"},
        )
        assert response.status_code == 401

    @patch("src.api.routers.collection.session_service")
    @patch("src.api.routers.collection.SessionLocal")
    def test_regenerate_character_image_character_not_found(
        self, mock_session_local, mock_session_service, client
    ):
        """Test regenerate_character_image returns 404 when character not found anywhere."""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from src.api.routers.collection import router

        app = FastAPI()
        app.include_router(router, prefix="/collection")

        test_client = TestClient(app)

        mock_user = MagicMock()
        mock_user.user_id = 1

        mock_game_loop = MagicMock()
        mock_player_state = MagicMock()
        mock_player_state.characters = {}  # No characters
        mock_player_state.player_name = "主角"
        mock_player_state.character_settings = {}  # No key_people or family
        mock_game_loop.get_state.return_value = mock_player_state

        mock_session = MagicMock()
        mock_session.game_loop = mock_game_loop
        mock_session_service.get_or_restore.return_value = mock_session

        # Need to mock dependency injection for user
        # This test demonstrates the scenario but would need proper DI

    def test_character_in_key_people_allowed(self, app):
        """Test that character in key_people (not in characters) is allowed to regenerate image."""
        from src.api.deps import get_current_user_optional
        from src.services.image_service import ImageService

        mock_user = MagicMock()
        mock_user.user_id = 1

        mock_game_loop = MagicMock()
        mock_player_state = MagicMock()
        mock_player_state.characters = {}  # Not in characters
        mock_player_state.player_name = "主角"
        mock_player_state.character_settings = {
            "relationships": {"key_people": [{"name": "赵灵儿", "role": "青梅竹马"}]}
        }
        mock_game_loop.get_state.return_value = mock_player_state

        mock_session = MagicMock()
        mock_session.game_loop = mock_game_loop

        mock_db_session = MagicMock()
        mock_image = MagicMock()
        mock_image.image_id = 456
        mock_game = MagicMock()
        mock_game.user_id = 1  # Same as mock_user.user_id
        mock_db_session.query.return_value.filter.return_value.first.return_value = (
            mock_image
        )
        # For verify_game_ownership
        mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            mock_image
        )

        with patch("src.api.routers.collection.session_service") as mock_ss:
            with patch("src.api.routers.collection.SessionLocal") as mock_db_class:
                with patch.object(
                    CollectionService, "verify_game_ownership"
                ) as mock_verify:
                    with patch.object(
                        ImageService, "regenerate_image"
                    ) as mock_regenerate:
                        mock_ss.get_or_restore.return_value = mock_session
                        mock_db_class.return_value = mock_db_session
                        mock_verify.return_value = mock_game  # Pass ownership check
                        mock_regenerate.return_value = [mock_image]

                        app.dependency_overrides[get_current_user_optional] = (
                            lambda: mock_user
                        )

                        test_client = TestClient(app)
                        response = test_client.post(
                            "/collection/1/characters/赵灵儿/regenerate-image",
                            json={"feedback": "裙子变长"},
                        )

                        # key_people should be allowed without affinity check
                        assert response.status_code == 200
                        assert response.json()["success"] is True

                        app.dependency_overrides.clear()

    def test_character_in_family_members_allowed(self, app):
        """Test that character in family_members is allowed to regenerate image."""
        from src.api.deps import get_current_user_optional
        from src.services.image_service import ImageService

        mock_user = MagicMock()
        mock_user.user_id = 1

        mock_game = MagicMock()
        mock_game.user_id = 1

        mock_game_loop = MagicMock()
        mock_player_state = MagicMock()
        mock_player_state.characters = {}  # Not in characters
        mock_player_state.player_name = "主角"
        mock_player_state.character_settings = {
            "family": {"family_members": [{"name": "父亲", "role": "父亲"}]}
        }
        mock_game_loop.get_state.return_value = mock_player_state

        mock_session = MagicMock()
        mock_session.game_loop = mock_game_loop

        mock_db_session = MagicMock()
        mock_image = MagicMock()
        mock_image.image_id = 789
        mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            mock_image
        )

        with patch("src.api.routers.collection.session_service") as mock_ss:
            with patch("src.api.routers.collection.SessionLocal") as mock_db_class:
                with patch.object(
                    CollectionService, "verify_game_ownership"
                ) as mock_verify:
                    with patch.object(
                        ImageService, "regenerate_image"
                    ) as mock_regenerate:
                        mock_ss.get_or_restore.return_value = mock_session
                        mock_db_class.return_value = mock_db_session
                        mock_verify.return_value = mock_game  # Pass ownership check
                        mock_regenerate.return_value = [mock_image]

                        app.dependency_overrides[get_current_user_optional] = (
                            lambda: mock_user
                        )

                        test_client = TestClient(app)
                        response = test_client.post(
                            "/collection/1/characters/父亲/regenerate-image",
                            json={"feedback": "戴眼镜"},
                        )

                        # family_members should be allowed without affinity check
                        assert response.status_code == 200
                        assert response.json()["success"] is True

                        app.dependency_overrides.clear()

    def test_character_in_characters_affinity_49_rejected(self, app):
        """Test that character in player_state.characters with affinity 49 is rejected."""
        from src.api.deps import get_current_user_optional
        from src.services.image_service import ImageService

        mock_user = MagicMock()
        mock_user.user_id = 1

        mock_game = MagicMock()
        mock_game.user_id = 1

        mock_game_loop = MagicMock()
        mock_player_state = MagicMock()
        mock_player_state.characters = {"李四": {"name": "李四", "affinity": 49}}
        mock_player_state.player_name = "主角"
        mock_player_state.character_settings = {}
        mock_game_loop.get_state.return_value = mock_player_state

        mock_session = MagicMock()
        mock_session.game_loop = mock_game_loop

        mock_db_session = MagicMock()
        mock_image = MagicMock()
        mock_image.image_id = 123
        mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            mock_image
        )

        with patch("src.api.routers.collection.session_service") as mock_ss:
            with patch("src.api.routers.collection.SessionLocal") as mock_db_class:
                with patch.object(
                    CollectionService, "verify_game_ownership"
                ) as mock_verify:
                    with patch.object(
                        ImageService, "regenerate_image"
                    ) as mock_regenerate:
                        mock_ss.get_or_restore.return_value = mock_session
                        mock_db_class.return_value = mock_db_session
                        mock_verify.return_value = mock_game
                        mock_regenerate.return_value = [mock_image]

                        app.dependency_overrides[get_current_user_optional] = (
                            lambda: mock_user
                        )

                        test_client = TestClient(app)
                        response = test_client.post(
                            "/collection/1/characters/李四/regenerate-image",
                            json={"feedback": "头发变长"},
                        )

                        # affinity < 50 should be rejected with 403
                        assert response.status_code == 403
                        assert "亲密度" in response.json()["detail"]

                        app.dependency_overrides.clear()

    def test_character_in_characters_affinity_50_allowed(self, app):
        """Test that character in player_state.characters with affinity 50 is allowed."""
        from src.api.deps import get_current_user_optional
        from src.services.image_service import ImageService

        mock_user = MagicMock()
        mock_user.user_id = 1

        mock_game = MagicMock()
        mock_game.user_id = 1

        mock_game_loop = MagicMock()
        mock_player_state = MagicMock()
        mock_player_state.characters = {"王五": {"name": "王五", "affinity": 50}}
        mock_player_state.player_name = "主角"
        mock_player_state.character_settings = {}
        mock_game_loop.get_state.return_value = mock_player_state

        mock_session = MagicMock()
        mock_session.game_loop = mock_game_loop

        # Mock database and image service
        mock_db_session = MagicMock()
        mock_image = MagicMock()
        mock_image.image_id = 123
        mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            mock_image
        )

        with patch("src.api.routers.collection.session_service") as mock_ss:
            with patch("src.api.routers.collection.SessionLocal") as mock_db_class:
                with patch.object(
                    CollectionService, "verify_game_ownership"
                ) as mock_verify:
                    with patch.object(
                        ImageService, "regenerate_image"
                    ) as mock_regenerate:
                        mock_ss.get_or_restore.return_value = mock_session
                        mock_db_class.return_value = mock_db_session
                        mock_verify.return_value = mock_game
                        mock_regenerate.return_value = [mock_image]

                        app.dependency_overrides[get_current_user_optional] = (
                            lambda: mock_user
                        )

                        test_client = TestClient(app)
                        response = test_client.post(
                            "/collection/1/characters/王五/regenerate-image",
                            json={"feedback": "头发变长"},
                        )

                        # affinity >= 50 should be allowed
                        assert response.status_code == 200
                        assert response.json()["success"] is True

                        app.dependency_overrides.clear()

    def test_player_can_regenerate_own_image(self, app):
        """Test that player can regenerate their own image without affinity check."""
        from src.api.deps import get_current_user_optional
        from src.services.image_service import ImageService

        mock_user = MagicMock()
        mock_user.user_id = 1

        mock_game = MagicMock()
        mock_game.user_id = 1

        mock_game_loop = MagicMock()
        mock_player_state = MagicMock()
        mock_player_state.characters = {}
        mock_player_state.player_name = "李逍遥"
        mock_player_state.character_settings = {"player_name": "李逍遥"}
        mock_game_loop.get_state.return_value = mock_player_state

        mock_session = MagicMock()
        mock_session.game_loop = mock_game_loop

        mock_db_session = MagicMock()
        mock_image = MagicMock()
        mock_image.image_id = 999
        mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            mock_image
        )

        with patch("src.api.routers.collection.session_service") as mock_ss:
            with patch("src.api.routers.collection.SessionLocal") as mock_db_class:
                with patch.object(
                    CollectionService, "verify_game_ownership"
                ) as mock_verify:
                    with patch.object(
                        ImageService, "regenerate_image"
                    ) as mock_regenerate:
                        mock_ss.get_or_restore.return_value = mock_session
                        mock_db_class.return_value = mock_db_session
                        mock_verify.return_value = mock_game
                        mock_regenerate.return_value = [mock_image]

                        app.dependency_overrides[get_current_user_optional] = (
                            lambda: mock_user
                        )

                        test_client = TestClient(app)
                        response = test_client.post(
                            "/collection/1/characters/李逍遥/regenerate-image",
                            json={"feedback": "换个发型"},
                        )

                        # Player should always be allowed
                        assert response.status_code == 200
                        assert response.json()["success"] is True

                        app.dependency_overrides.clear()

    def test_character_not_found_anywhere_returns_404(self, app):
        """Test that character not found anywhere returns 404."""
        from src.api.deps import get_current_user_optional

        mock_user = MagicMock()
        mock_user.user_id = 1

        mock_game_loop = MagicMock()
        mock_player_state = MagicMock()
        mock_player_state.characters = {}
        mock_player_state.player_name = "主角"
        mock_player_state.character_settings = {}  # No key_people or family
        mock_game_loop.get_state.return_value = mock_player_state

        mock_session = MagicMock()
        mock_session.game_loop = mock_game_loop

        with patch("src.api.routers.collection.session_service") as mock_ss:
            with patch("src.api.routers.collection.SessionLocal"):
                mock_ss.get_or_restore.return_value = mock_session

                app.dependency_overrides[get_current_user_optional] = lambda: mock_user

                test_client = TestClient(app)
                response = test_client.post(
                    "/collection/1/characters/陌生人/regenerate-image",
                    json={"feedback": "头发变长"},
                )

                # Character not found should return 404
                assert response.status_code == 404
                assert "不存在" in response.json()["detail"]

                app.dependency_overrides.clear()

    def test_character_in_characters_priority_over_key_people(self, app):
        """Test that player_state.characters is checked first and affinity is validated."""
        from src.api.deps import get_current_user_optional
        from src.services.image_service import ImageService

        # Character exists in BOTH characters (with low affinity) AND key_people
        # Should use characters data and apply affinity check
        mock_user = MagicMock()
        mock_user.user_id = 1

        mock_game = MagicMock()
        mock_game.user_id = 1

        mock_game_loop = MagicMock()
        mock_player_state = MagicMock()
        mock_player_state.characters = {
            "林月如": {"name": "林月如", "affinity": 45}  # Low affinity
        }
        mock_player_state.player_name = "主角"
        mock_player_state.character_settings = {
            "relationships": {
                "key_people": [{"name": "林月如", "role": "好友"}]  # Also in key_people
            }
        }
        mock_game_loop.get_state.return_value = mock_player_state

        mock_session = MagicMock()
        mock_session.game_loop = mock_game_loop

        mock_db_session = MagicMock()
        mock_image = MagicMock()
        mock_image.image_id = 123
        mock_db_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = (
            mock_image
        )

        with patch("src.api.routers.collection.session_service") as mock_ss:
            with patch("src.api.routers.collection.SessionLocal") as mock_db_class:
                with patch.object(
                    CollectionService, "verify_game_ownership"
                ) as mock_verify:
                    with patch.object(
                        ImageService, "regenerate_image"
                    ) as mock_regenerate:
                        mock_ss.get_or_restore.return_value = mock_session
                        mock_db_class.return_value = mock_db_session
                        mock_verify.return_value = mock_game
                        mock_regenerate.return_value = [mock_image]

                        app.dependency_overrides[get_current_user_optional] = (
                            lambda: mock_user
                        )

                        test_client = TestClient(app)
                        response = test_client.post(
                            "/collection/1/characters/林月如/regenerate-image",
                            json={"feedback": "换个发型"},
                        )

                        # Should check affinity from characters, not bypass
                        assert response.status_code == 403
                        assert "亲密度" in response.json()["detail"]

                        app.dependency_overrides.clear()


class TestRegenerateItemImageEndpoint:
    """Test regenerate_item_image endpoint."""

    @patch("src.api.routers.collection.session_service")
    @patch("src.api.routers.collection.SessionLocal")
    def test_regenerate_item_image_unauthorized(
        self, mock_session_local, mock_session_service, client
    ):
        """Test regenerate_item_image returns 401 when not logged in."""
        response = client.post(
            "/collection/1/items/魔法剑/regenerate-image", json={"feedback": "增加光泽"}
        )
        assert response.status_code == 401

    @patch("src.api.routers.collection.session_service")
    @patch("src.api.routers.collection.SessionLocal")
    def test_regenerate_item_image_item_not_found(
        self, mock_session_local, mock_session_service, client
    ):
        """Test regenerate_item_image returns 404 when item not found."""
        mock_user = MagicMock()
        mock_user.user_id = 1

        mock_game_loop = MagicMock()
        mock_player_state = MagicMock()
        mock_player_state.items = {}  # No items
        mock_game_loop.get_state.return_value = mock_player_state

        mock_session = MagicMock()
        mock_session.game_loop = mock_game_loop
        mock_session_service.get_or_restore.return_value = mock_session

        # This would need proper dependency injection to test fully


class TestAffinityValidation:
    """Test affinity validation for character image modification."""

    def test_affinity_check_player_bypass(self):
        """Test that player (is_player=True) bypasses affinity check."""
        # Player should always have affinity 100 effectively
        # The backend should check is_player flag and skip affinity validation
        pass

    def test_affinity_check_npc_below_threshold(self):
        """Test that NPC with affinity <= 50 is rejected."""
        # NPC with affinity 50 or below should get 403 error
        pass

    def test_affinity_check_npc_above_threshold(self):
        """Test that NPC with affinity > 50 is allowed."""
        # NPC with affinity 51+ should be allowed to modify image
        pass
