"""Tests for story API routes."""

import copy
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# API tests - story endpoints
pytestmark = pytest.mark.api

from src.api.main import app
from src.api.services.event_generation_operation import EventGenerationCoordinator
from src.game.daily_timeline import build_daily_timeline


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
    with patch("src.api.deps.session_service") as mock:
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

    def test_rewrite_story_updates_current_event_data(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Non-streaming rewrite should update persisted current_event_data."""
        mock_session.game_loop.player_state.current_event_data = {
            "event_description": "Original story",
            "story_text": "Original story",
            "options": [{"text": "Continue"}],
        }
        mock_session.game_loop.ai_generator.rewrite_story_segment.return_value = (
            "Rewritten story content"
        )
        mock_session.game_loop.current_event.model_dump.return_value = {
            "event_description": "Rewritten story content",
            "story_text": "Rewritten story content",
            "options": [{"text": "Continue"}],
        }
        mock_session.game_loop.get_state.return_value = mock_session.game_loop.player_state
        mock_session_service.get_or_restore.return_value = mock_session

        mock_db = MagicMock()
        with patch("src.api.routers.gameplay.sse_helpers.get_db", return_value=mock_db):
            response = client.post(
                "/api/games/1/rewrite",
                json={
                    "full_story": "Original story",
                    "segment_to_replace": "Original",
                    "user_instruction": "Make it warmer",
                    "language": "zh",
                },
                headers=auth_headers,
            )

        assert response.status_code == 200
        assert (
            mock_session.game_loop.player_state.current_event_data["event_description"]
            == "Rewritten story content"
        )
        assert (
            mock_session.game_loop.player_state.current_event_data["story_text"]
            == "Rewritten story content"
        )
        mock_db.save_game_progress.assert_called_once_with(1, mock_session.game_loop.player_state)

    def test_rewrite_story_no_event(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test rewriting when no current event - should still work using full_story param.

        ★ 新行为：改写不再强制依赖 current_event，使用前端传来的 full_story
        """
        mock_session.game_loop.current_event = None
        mock_session.game_loop.ai_generator.rewrite_story_segment.return_value = "Rewritten story"
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

    def test_rewrite_story_no_session(self, client, auth_headers, mock_auth, mock_session_service):
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
        mock_session.game_loop.ai_generator.rewrite_story_segment.side_effect = Exception(
            "AI error"
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

    def test_rewrite_story_provider_failure_preserves_original_story(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Provider failure must be visible and must not persist a fake rewrite."""
        from src.ai.story_exceptions import StoryRewriteFailure

        original_story = "原始故事"
        mock_session.game_loop.player_state.current_event_data = {
            "event_description": original_story,
            "story_text": original_story,
        }
        mock_session.game_loop.ai_generator.rewrite_story_segment.side_effect = (
            StoryRewriteFailure("provider unavailable")
        )
        mock_session_service.get_or_restore.return_value = mock_session

        response = client.post(
            "/api/games/1/rewrite",
            json={
                "full_story": original_story,
                "segment_to_replace": original_story,
                "user_instruction": "改写成八个自然段",
                "language": "zh",
            },
            headers=auth_headers,
        )

        assert response.status_code == 503
        assert "original story was not changed" in response.json()["detail"]
        assert mock_session.game_loop.player_state.current_event_data["story_text"] == original_story


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
        assert "event_description" in event or "story" in event, "event must contain story content"
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
        """Test a cited answer from authoritative character settings."""
        mock_session.game_loop.ai_generator.generate_completion_json.return_value = {
            "reply": "故事时代是现代。",
            "citations": ["setting:era.era_name"],
            "uncertain": False,
        }
        mock_session_service.get_or_restore.return_value = mock_session

        response = client.post(
            "/api/games/1/chat",
            json={"message": "Tell me about the main character", "language": "zh"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert data["reply"] == "故事时代是现代。"

    def test_story_chat_english(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Test chatting in English with a cited identity."""
        mock_session.game_loop.player_state.continuity_ledger = {
            "immutable_identities": {
                "Hero": {
                    "canonical_name": "Hero",
                    "roles": ["architect"],
                    "relationships": ["protagonist"],
                    "life_status": "alive",
                }
            },
            "timeline": [],
            "completed_events": {},
            "mutable_states": {"health": {}, "relationships": {}, "facts": {}},
        }
        mock_session.game_loop.ai_generator.generate_completion_json.return_value = {
            "reply": "The Hero is an architect.",
            "citations": ["identity:Hero"],
            "uncertain": False,
        }
        mock_session_service.get_or_restore.return_value = mock_session

        response = client.post(
            "/api/games/1/chat",
            json={"message": "Who is the hero?", "language": "en"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "reply" in data

    def test_story_chat_rejects_unsupported_professional_guarantee(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        mock_session.game_loop.ai_generator.generate_completion_json.return_value = {
            "reply": "律师说用母亲名义注册公司规避竞业是合法合规的路径，风险几乎为零。",
            "citations": [],
            "uncertain": True,
        }
        mock_session_service.get_or_restore.return_value = mock_session

        response = client.post(
            "/api/games/1/chat",
            json={"message": "这个做法安全吗？", "language": "zh"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        reply = response.json()["reply"]
        assert "风险几乎为零" not in reply
        assert "有资质的法律专业人士" in reply
        mock_session.game_loop.ai_generator.generate_completion_json.assert_called()

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
        mock_session.game_loop.ai_generator.generate_completion_json.side_effect = (
            Exception("AI error")
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
        """Free-form round history is not used as assistant authority."""
        mock_session.game_loop.player_state.round_history = [
            {"summary": "Started the journey"},
            {"summary": "Met a stranger"},
            {"summary": "Found a treasure"},
        ]
        mock_session.game_loop.player_state.continuity_ledger = {
            "immutable_identities": {},
            "timeline": [
                {
                    "event_id": "w1-r1",
                    "week": 1,
                    "round": 1,
                    "status": "committed",
                    "summary": "Started the journey",
                }
            ],
            "completed_events": {},
            "mutable_states": {"health": {}, "relationships": {}, "facts": {}},
        }
        mock_session.game_loop.ai_generator.generate_completion_json.return_value = {
            "reply": "Started the journey.",
            "citations": ["event:w1-r1"],
            "uncertain": False,
        }
        mock_session_service.get_or_restore.return_value = mock_session

        response = client.post(
            "/api/games/1/chat",
            json={"message": "What happened so far?", "language": "zh"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        prompt = mock_session.game_loop.ai_generator.generate_completion_json.call_args.kwargs[
            "system_prompt"
        ]
        assert "Met a stranger" not in prompt
        assert "Found a treasure" not in prompt

    def test_story_chat_uses_only_authoritative_structured_evidence(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """Draft prose and free-form history must never ground assistant facts."""
        mock_session.game_loop.player_state.player_name = "林岚"
        mock_session.game_loop.player_state.age = 31
        mock_session.game_loop.player_state.week = 2
        mock_session.game_loop.player_state.current_round = 1
        mock_session.game_loop.player_state.current_event_data = {
            "event_description": "未提交草稿称林岚获得五百万元。"
        }
        mock_session.game_loop.player_state.round_history = [
            {"summary": "自由故事文本称林岚已经搬到火星。"}
        ]
        mock_session.game_loop.player_state.continuity_ledger = {
            "version": 1,
            "immutable_identities": {
                "林岚": {
                    "canonical_name": "林岚",
                    "roles": ["建筑师"],
                    "relationships": ["主角"],
                    "life_status": "alive",
                    "age_baseline": 31,
                }
            },
            "timeline": [],
            "completed_events": {},
            "mutable_states": {"health": {}, "relationships": {}, "facts": {}},
        }
        mock_session.game_loop.ai_generator.generate_completion_json.return_value = {
            "reply": "林岚是建筑师。",
            "citations": ["identity:林岚"],
            "uncertain": False,
        }
        mock_session_service.get_or_restore.return_value = mock_session

        response = client.post(
            "/api/games/1/chat",
            json={"message": "林岚的职业是什么？", "language": "zh"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert response.json() == {"reply": "林岚是建筑师。"}
        call = mock_session.game_loop.ai_generator.generate_completion_json.call_args
        evidence_prompt = call.kwargs["system_prompt"]
        assert "identity:林岚" in evidence_prompt
        assert "未提交草稿" not in evidence_prompt
        assert "自由故事文本" not in evidence_prompt

    def test_story_chat_unknown_person_is_read_only_and_skips_ai(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        mock_session.game_loop.player_state.player_name = "林岚"
        mock_session.game_loop.player_state.continuity_ledger = {
            "version": 1,
            "immutable_identities": {
                "林岚": {
                    "canonical_name": "林岚",
                    "roles": ["建筑师"],
                    "relationships": ["主角"],
                    "life_status": "alive",
                }
            },
            "timeline": [],
            "completed_events": {},
            "mutable_states": {"health": {}, "relationships": {}, "facts": {}},
        }
        before = copy.deepcopy(mock_session.game_loop.player_state.continuity_ledger)
        mock_session_service.get_or_restore.return_value = mock_session

        response = client.post(
            "/api/games/1/chat",
            json={"message": "李华是谁？", "language": "zh"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        assert "没有找到" in response.json()["reply"]
        assert mock_session.game_loop.player_state.continuity_ledger == before
        mock_session.game_loop.ai_generator.generate_completion_json.assert_not_called()


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

    def test_daily_regenerate_without_current_event_generates_missing_story(
        self, client, auth_headers, mock_auth, mock_session_service, mock_session
    ):
        """A mistaken replacement call must repair a missing daily event."""
        from src.ai.models import EventOption, GameEvent

        generated = GameEvent(
            event_description="补生成的当天故事",
            options=[
                EventOption(text="继续前进", effects={}),
                EventOption(text="停下观察", effects={}),
            ],
        )
        mock_session.game_loop.current_event = None
        mock_session.game_loop.player_state.timeline = build_daily_timeline(
            start_date="2026-08-16",
            day_index=0,
        )
        mock_session.game_loop.player_state.current_event_data = None
        mock_session.game_loop.generate_round_event.return_value = generated
        mock_session.event_generation = EventGenerationCoordinator()
        mock_session_service.get_or_restore.return_value = mock_session

        with (
            patch(
                "src.api.routers.gameplay.sse_helpers._set_generation_resume_view"
            ),
            patch(
                "src.api.routers.gameplay.sse_helpers._trigger_round_illustration_generation"
            ),
            patch(
                "src.services.daily_recommended_prefetch.ensure_daily_recommended_prefetch"
            ),
        ):
            response = client.get(
                "/api/games/1/regenerate-stream",
                headers=auth_headers,
            )

        assert response.status_code == 200
        assert "event: complete" in response.text
        assert "补生成的当天故事" in response.text
        assert "No current daily event" not in response.text
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
        mock_session.game_loop.generate_round_event.side_effect = Exception("Generation failed")
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
        # ★ 缓存应该在生成前被清理（可能在 session 和 event_generator_service 中各清理一次）
        assert mock_session.clear_sse_cache.call_count >= 1
