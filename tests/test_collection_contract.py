"""收集面板缓存优化 - 契约测试 (Layer 3).

验证 API 生产者/消费者字段名一致性，确保前端缓存逻辑与后端响应格式匹配。
"""

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


class TestCollectionAPIContract:
    """测试收集 API 契约"""

    def test_get_collection_details_unauthorized(self):
        """测试未授权访问收集详情返回 401"""
        response = client.get("/api/collection/1/details")
        assert response.status_code == 401
        data = response.json()
        assert "detail" in data

    def test_generate_character_image_unauthorized(self):
        """测试未授权生成图片返回 401"""
        response = client.post("/api/collection/1/characters/Test/generate-image")
        assert response.status_code == 401

    def test_generate_item_image_unauthorized(self):
        """测试未授权生成物品图片返回 401"""
        response = client.post("/api/collection/1/items/Test/generate-image")
        assert response.status_code == 401

    def test_delete_item_unauthorized(self):
        """测试未授权删除物品返回 401"""
        response = client.delete("/api/collection/1/items/Test")
        assert response.status_code == 401


class TestCollectionResponseContract:
    """测试 CollectionResponse 字段契约"""

    def test_collection_response_has_required_fields(self):
        """验证 CollectionResponse 模型包含前端需要的所有字段"""
        from src.api.schemas import CollectionResponse

        # Pydantic v2 使用 model_fields 获取字段名
        fields = set(CollectionResponse.model_fields.keys())
        required_fields = [
            "game_id",
            "characters",
            "items",
            "landmarks",
            "total_characters",
            "total_items",
            "total_landmarks",
        ]

        for field in required_fields:
            assert field in fields, f"CollectionResponse 缺少字段: {field}"

    def test_character_collection_item_fields(self):
        """验证 CharacterCollectionItem 字段完整"""
        from src.api.schemas import CharacterCollectionItem

        fields = set(CharacterCollectionItem.model_fields.keys())
        required_fields = [
            "name",
            "role",
            "description",
            "affinity",
            "age",
            "gender",
            "occupation",
            "personality_traits",
            "image_url",
            "image_generated",
            "description_generated",
        ]

        for field in required_fields:
            assert field in fields, f"CharacterCollectionItem 缺少字段: {field}"

    def test_item_collection_item_fields(self):
        """验证 ItemCollectionItem 字段完整"""
        from src.api.schemas import ItemCollectionItem

        fields = set(ItemCollectionItem.model_fields.keys())
        required_fields = [
            "name",
            "description",
            "importance",
            "category",
            "acquired_week",
            "acquired_context",
            "is_key_item",
            "image_url",
            "image_generated",
            "description_generated",
            "metadata",
        ]

        for field in required_fields:
            assert field in fields, f"ItemCollectionItem 缺少字段: {field}"

    def test_landmark_collection_item_fields(self):
        """验证 LandmarkCollectionItem 字段完整"""
        from src.api.schemas import LandmarkCollectionItem

        fields = set(LandmarkCollectionItem.model_fields.keys())
        required_fields = [
            "name",
            "description",
            "category",
            "importance",
            "first_appear_week",
            "appear_count",
            "last_appear_week",
            "context",
            "is_key_location",
            "image_url",
            "image_generated",
            "metadata",
        ]

        for field in required_fields:
            assert field in fields, f"LandmarkCollectionItem 缺少字段: {field}"


class TestSessionServiceContract:
    """测试 SessionService 接口契约"""

    def test_get_or_restore_returns_gameloop_session(self):
        """验证 get_or_restore 返回 GameLoopSession"""
        import inspect

        from src.api.services.session_service import session_service

        sig = inspect.signature(session_service.get_or_restore)
        params = list(sig.parameters.keys())
        assert "game_id" in params

    def test_session_service_has_async_illustration_check(self):
        """验证 SessionService 有异步插画检查能力"""
        from src.api.services.session_service import SessionService

        assert hasattr(SessionService, "_check_and_generate_missing_illustrations")
        assert callable(
            getattr(SessionService, "_check_and_generate_missing_illustrations")
        )
