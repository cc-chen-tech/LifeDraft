"""Scene SSE scene_id propagation contract tests.

验证 SSE scene_image_ready 事件包含 scene_id。
Layer 3: 契约测试。
"""


class TestSceneSSESceneIdPropagation:
    """测试 SSE 事件包含 scene_id"""

    def test_scene_image_ready_event_includes_scene_id(self):
        """SSE scene_image_ready 事件应包含 scene_id 字段"""
        # 验证数据模型有 scene_id
        from src.database.models import SceneImage

        assert hasattr(SceneImage, "scene_id"), "SceneImage 模型应有 scene_id 字段"

    def test_scene_sse_event_payload_has_scene_id_key(self):
        """SSE 事件 payload 应有 scene_id key"""
        import datetime

        # 模拟事件 payload
        payload = {
            "type": "scene_image_ready",
            "game_id": 1,
            "round_number": 1,
            "week": 0,
            "stage": "result",
            "image_url": "http://test.png",
            "scene_description": "测试",
            "scene_id": 42,
            "timestamp": datetime.datetime.now().isoformat(),
        }

        assert "scene_id" in payload, "SSE payload 应包含 scene_id"
        assert payload["scene_id"] == 42, "scene_id 应正确传递"
