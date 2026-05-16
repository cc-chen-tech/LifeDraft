"""Tests for landmark collection system."""

from unittest.mock import Mock

from src.game.state.landmark_state import (LANDMARK_CATEGORY_LABELS,
                                           LANDMARK_IMPORTANCE_LABELS,
                                           LandmarkState)
from src.services.landmark_extraction_service import LandmarkExtractionService


class TestLandmarkState:
    """Test LandmarkState model."""

    def test_create_landmark_state(self):
        """Test creating a landmark state."""
        landmark = LandmarkState(
            name="古老的图书馆",
            description="一座充满历史气息的图书馆",
            category="building",
            importance="important",
            first_appear_week=1,
            appear_count=1,
            last_appear_week=1,
            context="主角第一次来到这里",
            is_key_location=True,
        )

        assert landmark.name == "古老的图书馆"
        assert landmark.description == "一座充满历史气息的图书馆"
        assert landmark.category == "building"
        assert landmark.importance == "important"
        assert landmark.first_appear_week == 1
        assert landmark.appear_count == 1
        assert landmark.last_appear_week == 1
        assert landmark.context == "主角第一次来到这里"
        assert landmark.is_key_location is True
        assert landmark.image_generated is False

    def test_landmark_state_defaults(self):
        """Test default values for landmark state."""
        landmark = LandmarkState(name="测试地点")

        assert landmark.description == ""
        assert landmark.category == "other"
        assert landmark.importance == "normal"
        assert landmark.first_appear_week == 0
        assert landmark.appear_count == 1
        assert landmark.last_appear_week == 0
        assert landmark.context == ""
        assert landmark.is_key_location is False
        assert landmark.metadata == {}
        assert landmark.image_url is None
        assert landmark.image_generated is False

    def test_to_context_string(self):
        """Test generating context string."""
        landmark = LandmarkState(
            name="城市广场",
            description="繁华的城市中心广场",
            category="area",
            importance="critical",
            is_key_location=True,
            appear_count=3,
        )

        context = landmark.to_context_string()

        assert "【城市广场】" in context
        assert "描述：繁华的城市中心广场" in context
        assert "类型：区域" in context
        assert "★ 关键地点" in context
        assert "出现次数：3" in context

    def test_from_dict_and_to_dict(self):
        """Test serialization."""
        data = {
            "name": "神秘森林",
            "description": "一片古老的森林",
            "category": "nature",
            "importance": "important",
            "first_appear_week": 2,
            "appear_count": 2,
            "last_appear_week": 5,
            "context": "主角在这里遇到了神秘老人",
            "is_key_location": False,
            "metadata": {"atmosphere": "神秘"},
            "image_url": None,
            "image_generated": False,
        }

        landmark = LandmarkState.from_dict(data)
        assert landmark.name == "神秘森林"
        assert landmark.category == "nature"

        output = landmark.to_dict()
        assert output["name"] == "神秘森林"
        assert output["category"] == "nature"

    def test_category_labels_exist(self):
        """Test that all category labels are defined."""
        assert "building" in LANDMARK_CATEGORY_LABELS
        assert "nature" in LANDMARK_CATEGORY_LABELS
        assert "room" in LANDMARK_CATEGORY_LABELS
        assert "area" in LANDMARK_CATEGORY_LABELS
        assert "other" in LANDMARK_CATEGORY_LABELS

        # Check both languages
        assert LANDMARK_CATEGORY_LABELS["building"]["zh"] == "建筑"
        assert LANDMARK_CATEGORY_LABELS["building"]["en"] == "Building"

    def test_importance_labels_exist(self):
        """Test that all importance labels are defined."""
        assert "critical" in LANDMARK_IMPORTANCE_LABELS
        assert "important" in LANDMARK_IMPORTANCE_LABELS
        assert "normal" in LANDMARK_IMPORTANCE_LABELS

        assert LANDMARK_IMPORTANCE_LABELS["critical"]["zh"] == "关键"
        assert LANDMARK_IMPORTANCE_LABELS["critical"]["en"] == "Critical"


class TestLandmarkExtractionService:
    """Test LandmarkExtractionService."""

    def test_extract_landmarks_empty_story(self):
        """Test extraction with empty story."""
        mock_ai_client = Mock()
        service = LandmarkExtractionService(mock_ai_client)

        result = service.extract_landmarks_from_story(
            story_text="",
            existing_landmarks={},
            character_settings={},
            current_week=1,
        )

        assert result == []

    def test_extract_landmarks_new_landmark(self):
        """Test extracting a new landmark."""
        mock_ai_client = Mock()
        mock_ai_client.call.return_value = """
        {
            "landmarks": [
                {
                    "action": "new",
                    "name": "钟楼",
                    "description": "城市中心的古老钟楼",
                    "category": "building",
                    "importance": "important",
                    "context": "主角在钟楼下等人",
                    "is_key_location": true,
                    "metadata": {"atmosphere": "庄重"}
                }
            ]
        }
        """

        service = LandmarkExtractionService(mock_ai_client)

        result = service.extract_landmarks_from_story(
            story_text="主角来到城市中心的钟楼下等待朋友。",
            existing_landmarks={},
            character_settings={"player_name": "小明"},
            current_week=1,
        )

        assert len(result) == 1
        assert result[0]["action"] == "new"
        landmark = result[0]["landmark"]
        assert landmark.name == "钟楼"
        assert landmark.category == "building"
        assert landmark.importance == "important"
        assert landmark.is_key_location is True

    def test_extract_landmarks_update_existing(self):
        """Test updating an existing landmark."""
        mock_ai_client = Mock()
        mock_ai_client.call.return_value = """
        {
            "landmarks": [
                {
                    "action": "update",
                    "name": "钟楼"
                }
            ]
        }
        """

        service = LandmarkExtractionService(mock_ai_client)

        existing_landmarks = {
            "钟楼": {
                "name": "钟楼",
                "description": "城市中心的古老钟楼",
                "category": "building",
                "importance": "important",
                "first_appear_week": 1,
                "appear_count": 1,
                "last_appear_week": 1,
            }
        }

        result = service.extract_landmarks_from_story(
            story_text="主角再次来到钟楼。",
            existing_landmarks=existing_landmarks,
            character_settings={"player_name": "小明"},
            current_week=3,
        )

        assert len(result) == 1
        assert result[0]["action"] == "update"
        assert result[0]["name"] == "钟楼"

    def test_extract_landmarks_invalid_category_defaults_to_other(self):
        """Test that invalid category defaults to 'other'."""
        mock_ai_client = Mock()
        mock_ai_client.call.return_value = """
        {
            "landmarks": [
                {
                    "action": "new",
                    "name": "神秘地点",
                    "description": "一个神秘的地方",
                    "category": "invalid_category",
                    "importance": "normal",
                    "context": "主角发现了一个新地方",
                    "is_key_location": false
                }
            ]
        }
        """

        service = LandmarkExtractionService(mock_ai_client)

        result = service.extract_landmarks_from_story(
            story_text="主角发现了一个神秘地点。",
            existing_landmarks={},
            character_settings={"player_name": "小明"},
            current_week=1,
        )

        assert len(result) == 1
        landmark = result[0]["landmark"]
        assert landmark.category == "other"

    def test_extract_landmarks_invalid_importance_defaults_to_normal(self):
        """Test that invalid importance defaults to 'normal'."""
        mock_ai_client = Mock()
        mock_ai_client.call.return_value = """
        {
            "landmarks": [
                {
                    "action": "new",
                    "name": "普通地点",
                    "description": "一个普通的地方",
                    "category": "area",
                    "importance": "super_important",
                    "context": "主角路过这里",
                    "is_key_location": false
                }
            ]
        }
        """

        service = LandmarkExtractionService(mock_ai_client)

        result = service.extract_landmarks_from_story(
            story_text="主角路过一个普通的地方。",
            existing_landmarks={},
            character_settings={"player_name": "小明"},
            current_week=1,
        )

        assert len(result) == 1
        landmark = result[0]["landmark"]
        assert landmark.importance == "normal"

    def test_extract_landmarks_no_landmarks_found(self):
        """Test when no landmarks are found in the story."""
        mock_ai_client = Mock()
        mock_ai_client.call.return_value = '{"landmarks": []}'

        service = LandmarkExtractionService(mock_ai_client)

        result = service.extract_landmarks_from_story(
            story_text="主角在家休息。",
            existing_landmarks={},
            character_settings={"player_name": "小明"},
            current_week=1,
        )

        assert result == []

    def test_extract_landmarks_ai_error(self):
        """Test handling AI errors."""
        mock_ai_client = Mock()
        mock_ai_client.call.side_effect = Exception("AI error")

        service = LandmarkExtractionService(mock_ai_client)

        result = service.extract_landmarks_from_story(
            story_text="主角来到一个新地方。",
            existing_landmarks={},
            character_settings={"player_name": "小明"},
            current_week=1,
        )

        assert result == []

    def test_extract_landmarks_invalid_json(self):
        """Test handling invalid JSON response."""
        mock_ai_client = Mock()
        mock_ai_client.call.return_value = "This is not valid JSON"

        service = LandmarkExtractionService(mock_ai_client)

        result = service.extract_landmarks_from_story(
            story_text="主角来到一个新地方。",
            existing_landmarks={},
            character_settings={"player_name": "小明"},
            current_week=1,
        )

        assert result == []

    def test_generate_landmark_description(self):
        """Test generating landmark description."""
        mock_ai_client = Mock()
        mock_ai_client.call.return_value = (
            '{"description": "这是一座宏伟的建筑，高耸入云，散发着神秘的光芒。"}'
        )

        service = LandmarkExtractionService(mock_ai_client)

        description = service.generate_landmark_description(
            landmark_name="魔法塔",
            landmark_category="building",
            context="主角发现了这座高塔",
            story_context="在森林深处发现了一座神秘的塔",
            language="zh",
        )

        assert description == "这是一座宏伟的建筑，高耸入云，散发着神秘的光芒。"

    def test_generate_landmark_description_error(self):
        """Test handling errors in description generation."""
        mock_ai_client = Mock()
        mock_ai_client.call.side_effect = Exception("AI error")

        service = LandmarkExtractionService(mock_ai_client)

        description = service.generate_landmark_description(
            landmark_name="魔法塔",
            landmark_category="building",
            context="主角发现了这座高塔",
            story_context="在森林深处发现了一座神秘的塔",
            language="zh",
        )

        assert description is None


class TestPlayerStateLandmarkMethods:
    """Test PlayerState landmark methods."""

    def test_add_landmark(self):
        """Test adding a landmark to player state."""
        from src.game.state.player_state import PlayerState

        player = PlayerState(player_name="Test")
        landmark = LandmarkState(
            name="测试地点",
            description="一个测试地点",
            category="building",
            importance="important",
            first_appear_week=1,
            appear_count=1,
            last_appear_week=1,
        )

        player.add_landmark(landmark)

        assert "测试地点" in player.landmarks
        assert player.landmarks["测试地点"]["description"] == "一个测试地点"

    def test_get_landmark(self):
        """Test getting a landmark from player state."""
        from src.game.state.player_state import PlayerState

        player = PlayerState(player_name="Test")
        landmark = LandmarkState(name="钟楼", description="古老的钟楼")
        player.add_landmark(landmark)

        result = player.get_landmark("钟楼")

        assert result is not None
        assert result.name == "钟楼"
        assert result.description == "古老的钟楼"

    def test_get_landmark_not_found(self):
        """Test getting a non-existent landmark."""
        from src.game.state.player_state import PlayerState

        player = PlayerState(player_name="Test")

        result = player.get_landmark("不存在")

        assert result is None

    def test_get_all_landmarks(self):
        """Test getting all landmarks."""
        from src.game.state.player_state import PlayerState

        player = PlayerState(player_name="Test")
        player.add_landmark(LandmarkState(name="地点1", description="第一个地点"))
        player.add_landmark(LandmarkState(name="地点2", description="第二个地点"))

        result = player.get_all_landmarks()

        assert len(result) == 2
        names = [lm.name for lm in result]
        assert "地点1" in names
        assert "地点2" in names

    def test_get_key_landmarks(self):
        """Test getting key landmarks."""
        from src.game.state.player_state import PlayerState

        player = PlayerState(player_name="Test")
        player.add_landmark(LandmarkState(name="普通地点", is_key_location=False))
        player.add_landmark(LandmarkState(name="关键地点", is_key_location=True))

        result = player.get_key_landmarks()

        assert len(result) == 1
        assert result[0].name == "关键地点"

    def test_update_landmark(self):
        """Test updating a landmark."""
        from src.game.state.player_state import PlayerState

        player = PlayerState(player_name="Test")
        player.add_landmark(LandmarkState(name="钟楼", appear_count=1))

        result = player.update_landmark("钟楼", appear_count=2, last_appear_week=5)

        assert result is True
        assert player.landmarks["钟楼"]["appear_count"] == 2
        assert player.landmarks["钟楼"]["last_appear_week"] == 5

    def test_update_landmark_not_found(self):
        """Test updating a non-existent landmark."""
        from src.game.state.player_state import PlayerState

        player = PlayerState(player_name="Test")

        result = player.update_landmark("不存在", appear_count=2)

        assert result is False

    def test_get_landmarks_context(self):
        """Test generating landmarks context string."""
        from src.game.state.player_state import PlayerState

        player = PlayerState(player_name="Test")
        player.add_landmark(
            LandmarkState(
                name="钟楼",
                description="古老的钟楼",
                category="building",
                is_key_location=True,
            )
        )

        context = player.get_landmarks_context()

        assert "【钟楼】" in context
        assert "古老的钟楼" in context

    def test_get_landmarks_context_empty(self):
        """Test generating context when no landmarks."""
        from src.game.state.player_state import PlayerState

        player = PlayerState(player_name="Test")

        context = player.get_landmarks_context()

        assert context == "无重要地点"
