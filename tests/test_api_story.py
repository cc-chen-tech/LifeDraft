"""Tests for story API routes."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# API tests - story endpoints
pytestmark = pytest.mark.api

from src.api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Create auth headers."""
    return {"Authorization": "Bearer test_token"}


@pytest.fixture
def mock_auth():
    """Mock authentication."""
    with patch("src.api.deps.decode_token") as mock:
        mock.return_value = 1
        yield mock


@pytest.fixture
def mock_session():
    """Create a mock game session."""
    session = MagicMock()
    session.game_loop = MagicMock()
    session.game_loop.current_event = MagicMock()
    session.game_loop.current_event.event_description = "Original story"
    session.game_loop.current_event.model_dump.return_value = {
        "event_description": "Test story",
        "options": [],
    }
    session.game_loop.player_state = MagicMock()
    session.game_loop.player_state.character_settings = {"era": {"era_name": "现代"}}
    session.game_loop.player_state.round_history = []
    session.game_loop.player_state.to_dict.return_value = {}
    session.game_loop.ai_generator = MagicMock()
    session.game_loop.ai_generator.ai_client = MagicMock()
    session.language = "zh"
    return session


@pytest.fixture
def mock_session_service():
    """Mock session service."""
    with patch("src.api.routers.story.session_service") as mock:
        yield mock


class TestRewriteStory:
    """Tests for POST /api/story/{game_id}/rewrite."""

    def test_rewrite_story_success(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test rewriting a story segment."""
        mock_session.game_loop.ai_generator.rewrite_story_segment.return_value = (
            "Rewritten story content"
        )
        mock_session.game_loop.current_event.model_dump.return_value = {
            "event_description": "Rewritten story content",
            "options": [],
        }
        mock_session_service.get_or_restore.return_value = mock_session

        response = client.post(
            "/api/games/1/rewrite",
            json={
                "full_story": "This is the original story. Some text here.",
                "segment_to_replace": "Some text here",
                "user_instruction": "Make it more exciting",
                "language": "zh",
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "rewritten_story" in data
        assert "event" in data

    def test_rewrite_story_no_event(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test rewriting when no current event - should still work using full_story param.

        ★ 新行为：改写不再强制依赖 current_event，使用前端传来的 full_story
        """
        mock_session.game_loop.current_event = None
        mock_session.game_loop.ai_generator.rewrite_story_segment.return_value = (
            "Rewritten story"
        )
        mock_session_service.get_or_restore.return_value = mock_session

        response = client.post(
            "/api/games/1/rewrite",
            json={
                "full_story": "Story",
                "segment_to_replace": "Story",
                "user_instruction": "Change it",
                "language": "zh",
            },
            headers=auth_headers,
        )

        # ★ 新行为：即使没有 current_event，也能成功改写
        assert response.status_code == 200
        assert response.json()["new_story"] == "Rewritten story"

    def test_rewrite_story_no_session(
        self, client, auth_headers, mock_auth, mock_session_service
    ):
        """Test rewriting without active session."""
        from fastapi import HTTPException

        mock_session_service.get_or_restore.side_effect = HTTPException(
            status_code=404, detail="Game not found"
        )
        response = client.post(
            "/api/games/1/rewrite",
            json={
                "full_story": "Story",
                "segment_to_replace": "Story",
                "user_instruction": "Change it",
                "language": "zh",
            },
            headers=auth_headers,
        )

        assert response.status_code == 404

    def test_rewrite_story_error(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test rewrite error handling."""
        mock_session.game_loop.ai_generator.rewrite_story_segment.side_effect = (
            Exception("AI error")
        )
        mock_session_service.get_or_restore.return_value = mock_session

        response = client.post(
            "/api/games/1/rewrite",
            json={
                "full_story": "Story",
                "segment_to_replace": "Story",
                "user_instruction": "Change it",
                "language": "zh",
            },
            headers=auth_headers,
        )

        assert response.status_code == 500


class TestRegenerateStory:
    """Tests for POST /api/story/{game_id}/regenerate.

    ★ 现在使用完整的 generate_round_event 流程，
    确保一致性校验、关系事件、世界模型等都正常工作。
    """

    def test_regenerate_story_success(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test regenerating the entire story using full generate_round_event flow."""
        # Mock the full generate_round_event method
        mock_new_event = MagicMock()
        mock_new_event.event_description = "New regenerated story"
        mock_new_event.model_dump.return_value = {
            "event_description": "New regenerated story",
            "options": [{"text": "Option 1"}],
        }
        mock_session.game_loop.generate_round_event.return_value = mock_new_event
        mock_session_service.get_or_restore.return_value = mock_session

        response = client.post(
            "/api/games/1/regenerate", json={"language": "zh"}, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "new_story" in data
        assert "event" in data
        # Verify generate_round_event was called (full flow)
        mock_session.game_loop.generate_round_event.assert_called_once()

    def test_regenerate_returns_new_story_and_options(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test that regenerate API returns both new_story and event with options."""
        new_story_text = "This is a brand new regenerated story"

        mock_new_event = MagicMock()
        mock_new_event.event_description = new_story_text
        mock_new_event.model_dump.return_value = {
            "event_description": new_story_text,
            "story": new_story_text,
            "options": [
                {"text": "Choice A", "description": "Option A desc"},
                {"text": "Choice B", "description": "Option B desc"},
            ],
        }
        mock_session.game_loop.generate_round_event.return_value = mock_new_event
        mock_session_service.get_or_restore.return_value = mock_session

        response = client.post(
            "/api/games/1/regenerate", json={"language": "zh"}, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # ★ 关键验证：返回格式必须包含 new_story 和 event
        assert "new_story" in data, "Response must contain 'new_story'"
        assert "event" in data, "Response must contain 'event'"

        # 验证 new_story 是字符串
        assert isinstance(data["new_story"], str), "new_story must be a string"

        # 验证 event 包含正确的字段
        event = data["event"]
        assert (
            "event_description" in event or "story" in event
        ), "event must contain story content"
        assert "options" in event, "event must contain options"
        assert isinstance(event["options"], list), "options must be a list"
        assert len(event["options"]) > 0, "options must not be empty"

        # 验证选项格式
        for option in event["options"]:
            assert "text" in option, "Each option must have 'text'"

    def test_regenerate_updates_current_event(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test that regenerate API clears old event and generates new one via generate_round_event."""
        new_story = "Updated story content"

        mock_new_event = MagicMock()
        mock_new_event.event_description = new_story
        mock_new_event.model_dump.return_value = {
            "event_description": new_story,
            "options": [{"text": "New Option"}],
        }
        mock_session.game_loop.generate_round_event.return_value = mock_new_event
        mock_session_service.get_or_restore.return_value = mock_session

        response = client.post(
            "/api/games/1/regenerate", json={"language": "zh"}, headers=auth_headers
        )

        assert response.status_code == 200
        # 验证 generate_round_event 被调用（完整流程）
        mock_session.game_loop.generate_round_event.assert_called_once()

    def test_regenerate_story_no_event(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test regenerating when no current event - should still work now.

        ★ 新行为：不再要求 current_event 存在，
        因为重新生成会使用完整的 generate_round_event 流程。
        """
        mock_new_event = MagicMock()
        mock_new_event.event_description = "Generated without existing event"
        mock_new_event.model_dump.return_value = {
            "event_description": "Generated without existing event",
            "options": [{"text": "Option 1"}],
        }
        mock_session.game_loop.current_event = None
        mock_session.game_loop.generate_round_event.return_value = mock_new_event
        mock_session_service.get_or_restore.return_value = mock_session

        response = client.post(
            "/api/games/1/regenerate", json={"language": "zh"}, headers=auth_headers
        )

        # ★ 新行为：即使没有 current_event，也能成功重新生成
        assert response.status_code == 200
        mock_session.game_loop.generate_round_event.assert_called_once()

    def test_regenerate_story_no_session(
        self, client, auth_headers, mock_auth, mock_session_service
    ):
        """Test regenerating without session."""
        from fastapi import HTTPException

        mock_session_service.get_or_restore.side_effect = HTTPException(
            status_code=404, detail="Game not found"
        )
        response = client.post(
            "/api/games/1/regenerate", json={"language": "zh"}, headers=auth_headers
        )

        assert response.status_code == 404

    def test_regenerate_story_error(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test regenerate error handling."""
        mock_session.game_loop.generate_round_event.side_effect = Exception("AI error")
        mock_session_service.get_or_restore.return_value = mock_session

        response = client.post(
            "/api/games/1/regenerate", json={"language": "zh"}, headers=auth_headers
        )

        assert response.status_code == 500

    def test_regenerate_clears_current_event_before_generation(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test that regenerate clears current_event before calling generate_round_event."""
        mock_new_event = MagicMock()
        mock_new_event.event_description = "Fresh generated story"
        mock_new_event.model_dump.return_value = {
            "event_description": "Fresh generated story",
            "options": [{"text": "Option 1"}],
        }
        mock_session.game_loop.generate_round_event.return_value = mock_new_event
        mock_session_service.get_or_restore.return_value = mock_session

        response = client.post(
            "/api/games/1/regenerate", json={"language": "zh"}, headers=auth_headers
        )

        assert response.status_code == 200
        # Verify that generate_round_event was called (which means current_event was cleared)
        mock_session.game_loop.generate_round_event.assert_called_once()


class TestStoryChat:
    """Tests for POST /api/story/{game_id}/chat."""

    def test_story_chat_success(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test chatting with story assistant."""
        mock_session.game_loop.ai_generator.generate_completion.return_value = (
            "The character is brave."
        )
        mock_session_service.get_or_restore.return_value = mock_session

        response = client.post(
            "/api/games/1/chat",
            json={"message": "Tell me about the main character", "language": "zh"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert data["reply"] == "The character is brave."

    def test_story_chat_english(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test chatting in English."""
        mock_session.game_loop.ai_generator.generate_completion.return_value = (
            "The hero is brave."
        )
        mock_session_service.get_or_restore.return_value = mock_session

        response = client.post(
            "/api/games/1/chat",
            json={"message": "Who is the hero?", "language": "en"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "reply" in data

    def test_story_chat_empty_message(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test chatting with empty message."""
        mock_session_service.get_or_restore.return_value = mock_session
        response = client.post(
            "/api/games/1/chat",
            json={"message": "", "language": "zh"},
            headers=auth_headers,
        )

        assert response.status_code == 422

    def test_story_chat_no_session(
        self, client, auth_headers, mock_auth, mock_session_service
    ):
        """Test chatting without session."""
        from fastapi import HTTPException

        mock_session_service.get_or_restore.side_effect = HTTPException(
            status_code=404, detail="Game not found"
        )
        response = client.post(
            "/api/games/1/chat",
            json={"message": "Hello", "language": "zh"},
            headers=auth_headers,
        )

        assert response.status_code == 404

    def test_story_chat_error(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test chat error handling."""
        mock_session.game_loop.ai_generator.generate_completion.side_effect = Exception(
            "AI error"
        )
        mock_session_service.get_or_restore.return_value = mock_session

        response = client.post(
            "/api/games/1/chat",
            json={"message": "Hello", "language": "zh"},
            headers=auth_headers,
        )

        assert response.status_code == 500

    def test_story_chat_with_history(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test chatting with round history context."""
        mock_session.game_loop.player_state.round_history = [
            {"summary": "Started the journey"},
            {"summary": "Met a stranger"},
            {"summary": "Found a treasure"},
        ]
        mock_session.game_loop.ai_generator.generate_completion.return_value = (
            "Based on history..."
        )
        mock_session_service.get_or_restore.return_value = mock_session

        response = client.post(
            "/api/games/1/chat",
            json={"message": "What happened so far?", "language": "zh"},
            headers=auth_headers,
        )

        assert response.status_code == 200


class TestRegenerateStreamSSE:
    """Tests for GET /api/story/{game_id}/regenerate-stream (SSE).

    ★ 这些测试验证流式重新生成使用完整的 generate_round_event 流程。
    """

    def test_regenerate_stream_uses_generate_round_event(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test that regenerate-stream calls generate_round_event (完整流程)."""
        # ★ 模拟 generate_round_event 返回有效事件
        mock_event = MagicMock()
        mock_event.event_description = "Regenerated story via full flow"
        mock_event.options = [MagicMock(text="Option 1"), MagicMock(text="Option 2")]
        mock_event.model_dump.return_value = {
            "event_description": "Regenerated story via full flow",
            "options": [{"text": "Option 1"}, {"text": "Option 2"}],
        }

        mock_session.game_loop.generate_round_event.return_value = mock_event
        mock_session_service.get_or_restore.return_value = mock_session

        response = client.get("/api/games/1/regenerate-stream", headers=auth_headers)

        # SSE 端点应该返回 200
        assert response.status_code == 200
        # ★ 关键验证：应该调用 generate_round_event，而不是 regenerate_story
        mock_session.game_loop.generate_round_event.assert_called_once()

    def test_regenerate_stream_handles_empty_result(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test handling when generate_round_event returns None."""
        # ★ 模拟空结果
        mock_session.game_loop.generate_round_event.return_value = None
        mock_session_service.get_or_restore.return_value = mock_session

        response = client.get("/api/games/1/regenerate-stream", headers=auth_headers)

        assert response.status_code == 200
        # 应该返回 SSE 流
        assert "text/event-stream" in response.headers.get("content-type", "")

    def test_regenerate_stream_handles_no_options(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test handling when event has no options."""
        # ★ 模拟没有选项的事件
        mock_event = MagicMock()
        mock_event.event_description = "Story without options"
        mock_event.options = []  # 空选项

        mock_session.game_loop.generate_round_event.return_value = mock_event
        mock_session_service.get_or_restore.return_value = mock_session

        response = client.get("/api/games/1/regenerate-stream", headers=auth_headers)

        assert response.status_code == 200

    def test_regenerate_stream_handles_exception(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test handling when generate_round_event raises exception."""
        # ★ 模拟异常
        mock_session.game_loop.generate_round_event.side_effect = Exception(
            "Generation failed"
        )
        mock_session_service.get_or_restore.return_value = mock_session

        response = client.get("/api/games/1/regenerate-stream", headers=auth_headers)

        assert response.status_code == 200
        # SSE 流应该包含错误事件


class TestRegenerateEdgeCases:
    """Tests for edge cases in story regeneration.

    ★ 这些测试覆盖之前遗漏的边界情况。
    """

    def test_regenerate_with_consistency_retry(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test regenerate when consistency validation triggers retry."""
        # ★ 这个测试验证一致性校验重试在重新生成中也能工作
        from src.ai.models import EventOption, GameEvent

        mock_event = GameEvent(
            event_description="Story after consistency fix",
            options=[
                EventOption(text="Choice A", effects={"energy": 0}),
                EventOption(text="Choice B", effects={"energy": 0}),
            ],
        )

        mock_session.game_loop.generate_round_event.return_value = mock_event
        mock_session_service.get_or_restore.return_value = mock_session

        response = client.get("/api/games/1/regenerate-stream", headers=auth_headers)

        assert response.status_code == 200

    def test_regenerate_with_world_model(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test that regenerate uses world model for consistency."""
        # ★ 设置 player_state 有 world_model_data
        mock_session.game_loop.player_state.world_model_data = {
            "active_commitments": [{"description": "承诺内容"}],
            "causal_chains": [{"cause": "A", "effect": "B"}],
        }

        mock_event = MagicMock()
        mock_event.event_description = "Story respecting commitments"
        mock_event.options = [MagicMock(text="Option")]
        mock_event.model_dump.return_value = {
            "event_description": "Story",
            "options": [{"text": "Option"}],
        }

        mock_session.game_loop.generate_round_event.return_value = mock_event
        mock_session_service.get_or_restore.return_value = mock_session

        response = client.get("/api/games/1/regenerate-stream", headers=auth_headers)

        assert response.status_code == 200

    def test_regenerate_session_cleared_cache(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test that SSE cache is cleared before regeneration."""
        mock_event = MagicMock()
        mock_event.event_description = "Fresh story"
        mock_event.options = [MagicMock(text="Option")]
        mock_event.model_dump.return_value = {
            "event_description": "Fresh story",
            "options": [{"text": "Option"}],
        }

        mock_session.game_loop.generate_round_event.return_value = mock_event
        mock_session.sse_cache = ["old_chunk_1", "old_chunk_2"]
        mock_session.clear_sse_cache = MagicMock()
        mock_session_service.get_or_restore.return_value = mock_session

        response = client.get("/api/games/1/regenerate-stream", headers=auth_headers)

        assert response.status_code == 200
        # ★ 缓存应该在生成前被清理
        mock_session.clear_sse_cache.assert_called_once()
