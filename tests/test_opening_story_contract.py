"""API 契约测试 - POST /api/character/opening-story (SSE)

验证开场故事 SSE 流式端点的请求/响应格式、并发控制和缓存行为。
这些测试在实现代码之前编写，定义了生产者和消费者之间的契约。
"""

import asyncio
import json
import time
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routers.character import _build_opening_story_cache_key
from src.api.schemas import OpeningStoryRequest
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.slow]


client = TestClient(app)


def _cache_key(player_name: str) -> str:
    """与端点使用相同的内容哈希 key（era=现代 / 探索世界 / zh）。"""
    return _build_opening_story_cache_key(
        OpeningStoryRequest(
            character_settings={"era": "现代"},
            player_name=player_name,
            life_vision="探索世界",
            language="zh",
        )
    )


class TestOpeningStoryAPIContract:
    """契约测试：POST /api/character/opening-story"""

    def test_opening_story_sse_format(self, mock_auth):
        """SSE 流应包含 status、story、complete 三种事件类型，且格式正确"""
        with patch("src.api.routers.character.CharacterCreator") as mock_creator_cls:
            # Mock CharacterCreator.generate_opening_story 返回生成器
            def mock_stream():
                yield MagicMock(choices=[MagicMock(delta=MagicMock(content="从前有"))])
                yield MagicMock(choices=[MagicMock(delta=MagicMock(content="一座山"))])

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

            assert (
                response.status_code == 200
            ), f"Expected 200, got {response.status_code}: {response.text}"
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
            char_module._opening_story_cache[_cache_key("TestConcurrent")] = {
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
            char_module._opening_story_cache.pop(_cache_key("TestConcurrent"), None)

        assert (
            response.status_code == 409
        ), f"并发请求应返回 409，实际返回 {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data
        assert "generation in progress" in data["detail"].lower() or "正在生成" in data["detail"]

    def test_opening_story_concurrent_stale_timeout(self, mock_auth):
        """超过 60 秒的 generating 状态应被视为失效，允许新请求"""
        from src.api.routers import character as char_module

        with char_module._cache_lock:
            char_module._opening_story_cache.clear()
            char_module._opening_story_cache[_cache_key("TestStale")] = {
                "generating": True,
                "result": None,
                "timestamp": time.time() - 70,  # 70 秒前启动，已超时
            }

        with patch("src.api.routers.character.CharacterCreator") as mock_creator_cls:

            def mock_stream():
                yield MagicMock(choices=[MagicMock(delta=MagicMock(content="超时后"))])

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
            char_module._opening_story_cache.pop(_cache_key("TestStale"), None)

        assert response.status_code == 200, f"超时后应允许新请求，实际返回 {response.status_code}"

    def test_opening_story_heartbeat_on_slow_generation(self, mock_auth):
        """AI 生成缓慢时应发送 heartbeat status 事件保持连接活跃"""
        import time

        with patch("src.api.routers.character.CharacterCreator") as mock_creator_cls:
            # 模拟缓慢生成器：第一个 chunk 延迟 6 秒后返回
            def slow_stream():
                time.sleep(6)
                yield MagicMock(choices=[MagicMock(delta=MagicMock(content="慢速故事"))])

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

    def test_opening_story_timeout_does_not_emit_empty_complete(self, mock_auth):
        """开场故事超时后不能再发送 full_story 为空的 complete 事件。"""
        with patch("src.api.routers.character.CharacterCreator") as mock_creator_cls:

            def empty_stream():
                return
                yield  # pragma: no cover

            async def immediate_timeout(awaitable, *args, **kwargs):
                if hasattr(awaitable, "close"):
                    awaitable.close()
                raise asyncio.TimeoutError()

            mock_creator = MagicMock()
            mock_creator.generate_opening_story.return_value = empty_stream()
            mock_creator_cls.return_value = mock_creator

            from src.api.routers import character as char_module

            with char_module._cache_lock:
                char_module._opening_story_cache.clear()

            with patch("src.api.routers.character.asyncio.wait_for", immediate_timeout):
                response = client.post(
                    "/api/character/opening-story",
                    json={
                        "character_settings": {"era": "现代"},
                        "player_name": "TestTimeoutNoEmptyComplete",
                        "life_vision": "探索世界",
                        "language": "zh",
                    },
                    headers={"Authorization": "Bearer test_token"},
                )

            assert response.status_code == 200
            body = response.text
            assert "Generation timeout" in body
            assert '"full_story": ""' not in body
            assert "event: complete" not in body

    def test_opening_story_truncated_text_does_not_emit_complete_or_cache(self, mock_auth):
        """开场故事疑似截断时不能被缓存或作为完整故事发送。"""
        with patch("src.api.routers.character.CharacterCreator") as mock_creator_cls:

            def truncated_stream():
                yield MagicMock(
                    choices=[
                        MagicMock(
                            delta=MagicMock(
                                content=(
                                    "2024年1月，林知夏站在上海共享办公空间里，盯着银行余额。"
                                    "她知道六万元启动资金必须撑过第一轮版本开发，团队还在等待发行顾问回复。"
                                    "门外传来脚步声，刘子涵推"
                                )
                            ),
                            finish_reason=None,
                        )
                    ]
                )

            mock_creator = MagicMock()
            mock_creator.generate_opening_story.return_value = truncated_stream()
            mock_creator_cls.return_value = mock_creator

            from src.api.routers import character as char_module

            with char_module._cache_lock:
                char_module._opening_story_cache.clear()

            response = client.post(
                "/api/character/opening-story",
                json={
                    "character_settings": {"era": "现代"},
                    "player_name": "TestTruncatedOpening",
                    "life_vision": "探索世界",
                    "language": "zh",
                },
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 200
            body = response.text
            assert "Opening story appears truncated" in body
            assert "event: complete" not in body
            with char_module._cache_lock:
                cache_entry = char_module._opening_story_cache.get(
                    _cache_key("TestTruncatedOpening")
                )
            assert cache_entry is not None
            assert cache_entry["result"] is None

    def test_opening_story_length_finish_reason_truncation(self, mock_auth):
        """当 finish_reason 为 length 时应视为截断，转为 error 并清缓存。"""
        with patch("src.api.routers.character.CharacterCreator") as mock_creator_cls:

            def length_finish_stream():
                yield MagicMock(
                    choices=[
                        MagicMock(
                            delta=MagicMock(
                                content=(
                                    "夜色里，林知夏拖着行李走进一间昏暗的共享办公区。"
                                    "她的银行卡只剩下 5800 元，团队还在争论"
                                )
                            ),
                            finish_reason="length",
                        )
                    ]
                )

            mock_creator = MagicMock()
            mock_creator.generate_opening_story.return_value = length_finish_stream()
            mock_creator_cls.return_value = mock_creator

            from src.api.routers import character as char_module

            with char_module._cache_lock:
                char_module._opening_story_cache.clear()

            response = client.post(
                "/api/character/opening-story",
                json={
                    "character_settings": {"era": "现代"},
                    "player_name": "TestLengthFinish",
                    "life_vision": "探索世界",
                    "language": "zh",
                },
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 200
            body = response.text
            assert "Opening story appears truncated" in body
            assert "event: complete" not in body

            with char_module._cache_lock:
                cache_entry = char_module._opening_story_cache.get(
                    _cache_key("TestLengthFinish")
                )
            assert cache_entry is not None
            assert cache_entry["result"] is None

    def test_opening_story_wait_for_timeout_while_thread_alive_is_heartbeat_not_failure(self, mock_auth):
        """队列等待提前超时时，只要生成线程仍活跃，就应保持 SSE 而不是立刻报 Generation timeout。"""
        with patch("src.api.routers.character.CharacterCreator") as mock_creator_cls:
            call_count = {"wait_for": 0}
            original_wait_for = asyncio.wait_for

            def slow_first_chunk_stream():
                time.sleep(0.05)
                yield MagicMock(choices=[MagicMock(delta=MagicMock(content="最终故事"))])

            async def first_wait_times_out(awaitable, *args, **kwargs):
                call_count["wait_for"] += 1
                if call_count["wait_for"] == 1:
                    if hasattr(awaitable, "close"):
                        awaitable.close()
                    raise asyncio.TimeoutError()
                return await original_wait_for(awaitable, *args, **kwargs)

            mock_creator = MagicMock()
            mock_creator.generate_opening_story.return_value = slow_first_chunk_stream()
            mock_creator_cls.return_value = mock_creator

            from src.api.routers import character as char_module

            with char_module._cache_lock:
                char_module._opening_story_cache.clear()

            with patch("src.api.routers.character.asyncio.wait_for", first_wait_times_out):
                response = client.post(
                    "/api/character/opening-story",
                    json={
                        "character_settings": {"era": "现代"},
                        "player_name": "TestTransientQueueTimeout",
                        "life_vision": "探索世界",
                        "language": "zh",
                    },
                    headers={"Authorization": "Bearer test_token"},
                )

            assert response.status_code == 200
            body = response.text
            assert "Generation timeout" not in body
            assert "最终故事" in body
            assert "event: complete" in body

    def test_opening_story_cache_hit(self, mock_auth):
        """缓存命中时应直接返回缓存结果，不重新生成"""
        from src.api.routers import character as char_module

        # 预先设置缓存结果
        with char_module._cache_lock:
            char_module._opening_story_cache.clear()
            char_module._opening_story_cache[_cache_key("TestCache")] = {
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
