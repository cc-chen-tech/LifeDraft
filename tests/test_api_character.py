"""Tests for character API routes."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# API tests - character endpoints
pytestmark = pytest.mark.api

from src.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_character_creator():
    """Mock CharacterCreator."""
    with patch("src.api.routers.character.CharacterCreator") as mock:
        creator = MagicMock()
        mock.return_value = creator
        yield creator


class TestGenerateSetting:
    """Tests for POST /api/character/setting."""

    def test_generate_era_success(self, client, mock_character_creator):
        """Test generating era setting."""
        mock_character_creator.generate_setting.return_value = {
            "era_name": "现代",
            "era_description": "21世纪的现代世界",
        }

        response = client.post(
            "/api/character/setting",
            json={
                "setting_type": "era",
                "player_name": "Test",
                "life_vision": "成为成功的企业家",
                "previous_settings": {},
                "language": "zh",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "era_name" in data

    def test_generate_age_success(self, client, mock_character_creator):
        """Test generating age setting."""
        mock_character_creator.generate_setting.return_value = {
            "starting_age": 22,
            "age_description": "刚刚大学毕业",
        }

        response = client.post(
            "/api/character/setting",
            json={
                "setting_type": "age",
                "player_name": "Test",
                "life_vision": "",
                "previous_settings": {"era": {"era_name": "现代"}},
                "language": "zh",
            },
        )

        assert response.status_code == 200

    def test_generate_gender_success(self, client, mock_character_creator):
        """Test generating gender setting."""
        mock_character_creator.generate_setting.return_value = {
            "gender": "男",
            "gender_description": "一个普通的年轻男子",
        }

        response = client.post(
            "/api/character/setting",
            json={
                "setting_type": "gender",
                "player_name": "Test",
                "life_vision": "",
                "previous_settings": {},
                "language": "zh",
            },
        )

        assert response.status_code == 200

    def test_generate_world_success(self, client, mock_character_creator):
        """Test generating world setting."""
        mock_character_creator.generate_setting.return_value = {
            "world_name": "都市",
            "world_description": "繁华的大都市",
        }

        response = client.post(
            "/api/character/setting",
            json={
                "setting_type": "world",
                "player_name": "Test",
                "life_vision": "",
                "previous_settings": {},
                "language": "zh",
            },
        )

        assert response.status_code == 200

    def test_generate_family_success(self, client, mock_character_creator):
        """Test generating family background."""
        mock_character_creator.generate_setting.return_value = {
            "family_description": "中产阶级家庭",
            "parents": [],
        }

        response = client.post(
            "/api/character/setting",
            json={
                "setting_type": "family",
                "player_name": "Test",
                "life_vision": "",
                "previous_settings": {},
                "language": "zh",
            },
        )

        assert response.status_code == 200

    def test_generate_traits_success(self, client, mock_character_creator):
        """Test generating traits."""
        mock_character_creator.generate_setting.return_value = {
            "traits": ["聪明", "勤奋", "内向"],
            "traits_description": "一个聪明勤奋但内向的人",
        }

        response = client.post(
            "/api/character/setting",
            json={
                "setting_type": "traits",
                "player_name": "Test",
                "life_vision": "",
                "previous_settings": {},
                "language": "zh",
            },
        )

        assert response.status_code == 200

    def test_generate_wealth_success(self, client, mock_character_creator):
        """Retired wealth setting requests are rejected by request validation."""
        mock_character_creator.generate_setting.return_value = {
            "wealth_level": "中等",
            "starting_wealth": 50000,
        }

        response = client.post(
            "/api/character/setting",
            json={
                "setting_type": "wealth",
                "player_name": "Test",
                "life_vision": "",
                "previous_settings": {},
                "language": "zh",
            },
        )

        assert response.status_code == 422
        mock_character_creator.generate_setting.assert_not_called()

    def test_generate_setting_with_feedback(self, client, mock_character_creator):
        """Test generating setting with user feedback."""
        mock_character_creator.generate_setting.return_value = {
            "era_name": "未来",
            "era_description": "2100年的科幻世界",
        }

        response = client.post(
            "/api/character/setting",
            json={
                "setting_type": "era",
                "player_name": "Test",
                "life_vision": "",
                "previous_settings": {},
                "feedback": "我想要更科幻的背景",
                "language": "zh",
            },
        )

        assert response.status_code == 200
        mock_character_creator.generate_setting.assert_called_once()

    def test_generate_setting_error(self, client, mock_character_creator):
        """Test setting generation error."""
        mock_character_creator.generate_setting.side_effect = Exception("AI error")

        response = client.post(
            "/api/character/setting",
            json={
                "setting_type": "era",
                "player_name": "Test",
                "life_vision": "",
                "previous_settings": {},
                "language": "zh",
            },
        )

        assert response.status_code == 500


class TestGenerateRelationship:
    """Tests for POST /api/character/relationship."""

    def test_generate_relationship_success(self, client, mock_character_creator):
        """Test generating a relationship person."""
        mock_character_creator.generate_single_relationship_person.return_value = {
            "name": "李明",
            "relationship_type": "好友",
            "personality": "开朗外向",
        }

        response = client.post(
            "/api/character/relationship",
            json={
                "player_name": "Test",
                "life_vision": "",
                "previous_settings": {},
                "existing_people": [],
                "person_index": 0,
                "total_needed": 3,
                "language": "zh",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "name" in data

    def test_generate_relationship_with_existing(self, client, mock_character_creator):
        """Test generating relationship with existing people."""
        mock_character_creator.generate_single_relationship_person.return_value = {
            "name": "王华",
            "relationship_type": "同事",
            "personality": "严肃认真",
        }

        response = client.post(
            "/api/character/relationship",
            json={
                "player_name": "Test",
                "life_vision": "",
                "previous_settings": {},
                "existing_people": [{"name": "李明"}],
                "person_index": 1,
                "total_needed": 3,
                "language": "zh",
            },
        )

        assert response.status_code == 200

    def test_generate_relationship_error(self, client, mock_character_creator):
        """Test relationship generation error."""
        mock_character_creator.generate_single_relationship_person.side_effect = Exception("Error")

        response = client.post(
            "/api/character/relationship",
            json={
                "player_name": "Test",
                "life_vision": "",
                "previous_settings": {},
                "existing_people": [],
                "person_index": 0,
                "total_needed": 3,
                "language": "zh",
            },
        )

        assert response.status_code == 500


class TestGenerateAttributes:
    """Tests for POST /api/character/attributes."""

    def test_generate_attributes_success(self, client, mock_character_creator):
        """Test generating initial attributes."""
        mock_character_creator.generate_initial_attributes.return_value = {
            "energy": 80,
            "mood": 70,
            "knowledge": 50,
            "wealth": 10000,
        }

        response = client.post(
            "/api/character/attributes",
            json={
                "character_settings": {"era": {"era_name": "现代"}},
                "language": "zh",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "energy" in data
        assert "mood" in data

    def test_generate_attributes_error(self, client, mock_character_creator):
        """Test attributes generation error."""
        mock_character_creator.generate_initial_attributes.side_effect = Exception("Error")

        response = client.post(
            "/api/character/attributes",
            json={"character_settings": {}, "language": "zh"},
        )

        assert response.status_code == 500


class TestRelationshipsSummary:
    """Tests for POST /api/character/relationships-summary."""

    def test_generate_summary_success(self, client, mock_character_creator):
        """Test generating relationships summary."""
        mock_character_creator.generate_relationships_summary.return_value = "你有三个重要的人..."

        response = client.post(
            "/api/character/relationships-summary",
            json={
                "player_name": "Test",
                "life_vision": "",
                "previous_settings": {},
                "key_people": [{"name": "李明"}, {"name": "王华"}],
                "language": "zh",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "relationships_description" in data

    def test_generate_summary_error(self, client, mock_character_creator):
        """Test summary generation error."""
        mock_character_creator.generate_relationships_summary.side_effect = Exception("Error")

        response = client.post(
            "/api/character/relationships-summary",
            json={
                "player_name": "Test",
                "life_vision": "",
                "previous_settings": {},
                "key_people": [],
                "language": "zh",
            },
        )

        assert response.status_code == 500


class TestOpeningStory:
    """Tests for POST /api/character/opening-story (SSE endpoint)."""

    def test_opening_story_cached(self, client, mock_character_creator):
        """Test opening story returns cached result."""
        # First request to generate
        import time

        from src.api.routers.character import _cache_lock, _opening_story_cache

        # Pre-populate cache
        from src.api.routers.character import _build_opening_story_cache_key
        from src.api.schemas import OpeningStoryRequest

        with _cache_lock:
            _opening_story_cache[
                _build_opening_story_cache_key(
                    OpeningStoryRequest(
                        character_settings={"era": {"era_name": "现代"}},
                        player_name="CacheTest",
                        life_vision="",
                        language="zh",
                    )
                )
            ] = {
                "generating": False,
                "result": "Cached story...",
                "timestamp": time.time(),
            }

        response = client.post(
            "/api/character/opening-story",
            json={
                "character_settings": {"era": {"era_name": "现代"}},
                "player_name": "CacheTest",
                "life_vision": "",
                "language": "zh",
            },
        )

        assert response.status_code == 200
        # Clean up
        with _cache_lock:
            del _opening_story_cache[
                _build_opening_story_cache_key(
                    OpeningStoryRequest(
                        character_settings={"era": {"era_name": "现代"}},
                        player_name="CacheTest",
                        life_vision="",
                        language="zh",
                    )
                )
            ]

    def test_opening_story_generation_in_progress(self, client):
        """Test opening story when generation in progress."""
        import time

        from src.api.routers.character import _cache_lock, _opening_story_cache

        # Pre-populate cache as generating
        from src.api.routers.character import _build_opening_story_cache_key
        from src.api.schemas import OpeningStoryRequest

        with _cache_lock:
            _opening_story_cache[
                _build_opening_story_cache_key(
                    OpeningStoryRequest(
                        character_settings={},
                        player_name="GeneratingTest",
                        life_vision="",
                        language="zh",
                    )
                )
            ] = {
                "generating": True,
                "result": None,
                "timestamp": time.time(),
            }

        response = client.post(
            "/api/character/opening-story",
            json={
                "character_settings": {},
                "player_name": "GeneratingTest",
                "life_vision": "",
                "language": "zh",
            },
        )

        assert response.status_code == 409
        # Clean up
        with _cache_lock:
            del _opening_story_cache[
                _build_opening_story_cache_key(
                    OpeningStoryRequest(
                        character_settings={},
                        player_name="GeneratingTest",
                        life_vision="",
                        language="zh",
                    )
                )
            ]
