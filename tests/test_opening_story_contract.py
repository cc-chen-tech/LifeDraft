"""API 契约测试 - POST /api/character/opening-story (SSE)

验证开场故事 SSE 流式端点的请求/响应格式、并发控制和缓存行为。
这些测试在实现代码之前编写，定义了生产者和消费者之间的契约。
"""

import json
import time
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


class TestOpeningStoryAPIContract:
    """契约测试：POST /api/character/opening-story"""

    def test_opening_story_sse_format(self, mock_auth):
        """SSE 流应包含 status、story、complete 三种事件类型，且格式正确"""
        with patch("src.api.routers.character.CharacterCreator") as mock_creator_cls:
            # Mock CharacterCreator.generate_opening_story 返回生成器
            def mock_stream():
                yield MagicMock(
                    choices=[MagicMock(delta=MagicMock(content="从前有"))]
                )
                yield MagicMock(
                    choices=[MagicMock(delta=MagicMock(content="一座山"))]
                )

            mock_creator = MagicMock()
            mock_creator.generate_opening_story.return_value = mock_stream()
            mock_creator_cls.return_value = mock_creator

            # 清除缓存避免干扰
            from src.api.routers import character as char_module
            with char_module._cache_lock:
                char_module._opening_story_cache.clear()

            response = client.post(
                "/api/character/opening-story",
                json={
                    "character_settings": {"era": "现代"},
                    "player_name": "TestSSE",
                    "life_vision": "探索世界",
                    "language": "zh",
                },
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
            assert response.headers["content-type"].startswith("text/event-stream")

            # 解析 SSE 事件
            body = response.text
            lines = [line for line in body.strip().split("\n") if line.strip()]

            event_types = []
            for line in lines:
                if line.startswith("event:"):
                    event_types.append(line.replace("event:", "").strip())
                elif line.startswith("data:"):
                    data_str = line.replace("data:", "").strip()
                    # 验证 data 是合法 JSON
                    json.loads(data_str)

            # 验证事件序列：必须有 status 开头，complete 结尾，中间有 story
            assert "status" in event_types, f"SSE 流应包含 status 事件，实际事件: {event_types}"
            assert "story" in event_types, f"SSE 流应包含 story 事件，实际事件: {event_types}"
            assert "complete" in event_types, f"SSE 流应包含 complete 事件，实际事件: {event_types}"
            assert event_types[0] == "status", "第一个事件应为 status"
            assert event_types[-1] == "complete", "最后一个事件应为 complete"

    def test_opening_story_concurrent_request(self, mock_auth):
        """同一 player_name 并发请求时，如果前一个请求仍在生成中，应返回 409"""
        from src.api.routers import character as char_module

        # 手动设置缓存为 generating 状态，模拟前一个请求正在进行
        with char_module._cache_lock:
            char_module._opening_story_cache.clear()
            char_module._opening_story_cache["TestConcurrent"] = {
                "generating": True,
                "result": None,
                "timestamp": time.time(),  # 刚启动，不会超过 60s
            }

        # 发送请求，应返回 409
        response = client.post(
            "/api/character/opening-story",
            json={
                "character_settings": {"era": "现代"},
                "player_name": "TestConcurrent",
                "life_vision": "探索世界",
                "language": "zh",
            },
            headers={"Authorization": "Bearer test_token"},
        )

        # 清理
        with char_module._cache_lock:
            char_module._opening_story_cache.pop("TestConcurrent", None)

        assert response.status_code == 409, (
            f"并发请求应返回 409，实际返回 {response.status_code}: {response.text}"
        )
        data = response.json()
        assert "detail" in data
        assert "generation in progress" in data["detail"].lower() or "正在生成" in data["detail"]

    def test_opening_story_concurrent_stale_timeout(self, mock_auth):
        """超过 60 秒的 generating 状态应被视为失效，允许新请求"""
        from src.api.routers import character as char_module

        with char_module._cache_lock:
            char_module._opening_story_cache.clear()
            char_module._opening_story_cache["TestStale"] = {
                "generating": True,
                "result": None,
                "timestamp": time.time() - 70,  # 70 秒前启动，已超时
            }

        with patch("src.api.routers.character.CharacterCreator") as mock_creator_cls:
            def mock_stream():
                yield MagicMock(
                    choices=[MagicMock(delta=MagicMock(content="超时后"))]
                )

            mock_creator = MagicMock()
            mock_creator.generate_opening_story.return_value = mock_stream()
            mock_creator_cls.return_value = mock_creator

            response = client.post(
                "/api/character/opening-story",
                json={
                    "character_settings": {"era": "现代"},
                    "player_name": "TestStale",
                    "life_vision": "探索世界",
                    "language": "zh",
                },
                headers={"Authorization": "Bearer test_token"},
            )

        # 清理
        with char_module._cache_lock:
            char_module._opening_story_cache.pop("TestStale", None)

        assert response.status_code == 200, (
            f"超时后应允许新请求，实际返回 {response.status_code}"
        )

    def test_opening_story_heartbeat_on_slow_generation(self, mock_auth):
        """AI 生成缓慢时应发送 heartbeat status 事件保持连接活跃"""
        import time

        with patch("src.api.routers.character.CharacterCreator") as mock_creator_cls:
            # 模拟缓慢生成器：第一个 chunk 延迟 6 秒后返回
            def slow_stream():
                time.sleep(6)
                yield MagicMock(
                    choices=[MagicMock(delta=MagicMock(content="慢速故事"))]
                )

            mock_creator = MagicMock()
            mock_creator.generate_opening_story.return_value = slow_stream()
            mock_creator_cls.return_value = mock_creator

            from src.api.routers import character as char_module
            with char_module._cache_lock:
                char_module._opening_story_cache.clear()

            response = client.post(
                "/api/character/opening-story",
                json={
                    "character_settings": {"era": "现代"},
                    "player_name": "TestHeartbeat",
                    "life_vision": "探索世界",
                    "language": "zh",
                },
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 200
            body = response.text
            # 验证包含 heartbeat status 事件（phase: writing）
            assert "writing" in body, f"慢速生成应包含 heartbeat (writing)，实际响应: {body[:200]}"
            # 验证最终仍有 complete 事件
            assert "complete" in body, "慢速生成最终应有 complete 事件"

    def test_opening_story_cache_hit(self, mock_auth):
        """缓存命中时应直接返回缓存结果，不重新生成"""
        from src.api.routers import character as char_module

        # 预先设置缓存结果
        with char_module._cache_lock:
            char_module._opening_story_cache.clear()
            char_module._opening_story_cache["TestCache"] = {
                "generating": False,
                "result": "这是一个缓存的故事",
                "timestamp": time.time(),
            }

        response = client.post(
            "/api/character/opening-story",
            json={
                "character_settings": {"era": "现代"},
                "player_name": "TestCache",
                "life_vision": "探索世界",
                "language": "zh",
            },
            headers={"Authorization": "Bearer test_token"},
        )

        # 清理
        with char_module._cache_lock:
            char_module._opening_story_cache.pop("TestCache", None)

        assert response.status_code == 200
        body = response.text
        # 缓存命中响应应包含 cached 标记
        assert "cached" in body, "缓存命中响应应包含 cached 标记"
        # 应包含缓存的故事内容
        assert "这是一个缓存的故事" in body, "缓存命中应返回缓存的故事内容"
