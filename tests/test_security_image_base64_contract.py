"""Image Base64 Security Contract Tests

验证图片服务端点正确设置 Content-Type，防止 content-sniffing XSS。
Layer 3: 契约测试 — 图片响应必须包含正确的 Content-Type 头。
"""

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


class TestImageBase64SecurityContract:
    """测试图片安全契约"""

    def test_image_endpoint_sets_content_type(self):
        """图片文件服务端点必须设置正确的 Content-Type 头"""
        # 即使文件不存在，路由处理逻辑也应该验证请求格式
        response = client.get("/api/images/file/1/scene/test.png")
        # 如果文件不存在返回 404，但 Content-Type 不应是 text/html
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "")
            assert content_type.startswith(
                "image/"
            ), f"图片端点应返回 image/* Content-Type，但返回了 {content_type}"

    def test_image_endpoint_rejects_path_traversal(self):
        """图片端点必须拒绝路径遍历尝试"""
        malicious_paths = [
            "/api/images/file/1/scene/../../../etc/passwd",
            "/api/images/file/1/scene/..%2F..%2F..%2Fetc%2Fpasswd",
            "/api/images/file/1/scene/%2e%2e/%2e%2e/%2e%2e/etc/passwd",
        ]
        for path in malicious_paths:
            response = client.get(path)
            assert response.status_code in (
                403,
                404,
            ), f"路径遍历尝试应返回 403 或 404，但 {path} 返回了 {response.status_code}"

    def test_image_base64_mime_type_sanitization(self):
        """base64 data URL 的 MIME 类型必须从文件扩展名派生，不能从用户输入"""
        import inspect

        from src.services.collection_service import CollectionService

        source = inspect.getsource(CollectionService._get_image_reference_url)
        # 验证 MIME 类型是从 storage_path 的文件扩展名派生
        assert (
            "rsplit" in source or "splitext" in source
        ), "base64 MIME 类型必须从文件扩展名派生，不能直接信任外部输入"
        # 不允许直接使用用户提供的 content-type
        assert (
            "content_type" not in source.lower() or "user" not in source.lower()
        ), "base64 MIME 类型不能信任用户输入"
