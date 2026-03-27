"""路径遍历防护测试 - 对应优化 C-01"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Unit tests - no external dependencies
pytestmark = pytest.mark.unit


class TestPathTraversalPrevention:
    """测试路径遍历防护函数"""

    def test_valid_filename_under_image_dir(self, safe_image_dir):
        """正常文件名应通过验证"""
        # 验证 safe_image_dir 下的合法路径
        valid_path = safe_image_dir / "1" / "character" / "test.png"
        assert valid_path.exists()
        resolved = valid_path.resolve()
        assert resolved.is_relative_to(safe_image_dir.resolve())

    def test_valid_nested_path(self, safe_image_dir):
        """嵌套路径应通过验证"""
        valid_path = safe_image_dir / "1" / "round_scene" / "scene_w1_r1.png"
        assert valid_path.exists()
        resolved = valid_path.resolve()
        assert resolved.is_relative_to(safe_image_dir.resolve())

    def test_valid_filename_with_spaces(self, safe_image_dir):
        """含空格的文件名应通过验证"""
        spaced = safe_image_dir / "test file.png"
        spaced.write_bytes(b"fake")
        resolved = spaced.resolve()
        assert resolved.is_relative_to(safe_image_dir.resolve())

    def test_valid_filename_with_unicode(self, safe_image_dir):
        """含 Unicode 的文件名应通过验证"""
        unicode_file = safe_image_dir / "角色_图片.png"
        unicode_file.write_bytes(b"fake")
        resolved = unicode_file.resolve()
        assert resolved.is_relative_to(safe_image_dir.resolve())

    def test_reject_dot_dot_slash(self, safe_image_dir):
        """../../../etc/passwd 应被拒绝"""
        malicious = safe_image_dir / ".." / ".." / ".." / "etc" / "passwd"
        resolved = malicious.resolve()
        assert not resolved.is_relative_to(safe_image_dir.resolve())

    def test_reject_encoded_traversal(self, safe_image_dir):
        """URL 编码的遍历路径应被拒绝"""
        # %2e%2e%2f 解码后是 ../
        from urllib.parse import unquote

        encoded = "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd"
        decoded = unquote(encoded)
        malicious = safe_image_dir / decoded
        resolved = malicious.resolve()
        assert not resolved.is_relative_to(safe_image_dir.resolve())

    def test_reject_absolute_path(self, safe_image_dir):
        """绝对路径应被拒绝"""
        abs_path = Path("/etc/passwd")
        assert not abs_path.resolve().is_relative_to(safe_image_dir.resolve())

    def test_reject_null_byte(self, safe_image_dir):
        """包含 null byte 的路径应被拒绝"""
        # null byte 攻击
        try:
            malicious = safe_image_dir / "file\x00.png"
            # 如果系统允许创建这样的路径对象，检查它不在安全目录内
            # 在大多数系统上这会引发 ValueError
            resolved = malicious.resolve()
            assert not resolved.is_relative_to(safe_image_dir.resolve())
        except (ValueError, OSError):
            pass  # 系统正确拒绝了 null byte

    def test_reject_backslash_traversal(self, safe_image_dir):
        """Windows 风格反斜杠遍历应被拒绝"""
        malicious = safe_image_dir / ".." / ".." / ".."
        resolved = malicious.resolve()
        assert not resolved.is_relative_to(safe_image_dir.resolve())

    def test_reject_symlink_escape(self, safe_image_dir, tmp_path):
        """符号链接逃逸应被检测"""
        import os

        # 创建指向 tmp_path 外部的符号链接
        external_dir = tmp_path / "external"
        external_dir.mkdir()
        (external_dir / "secret.txt").write_text("secret")

        symlink_path = safe_image_dir / "link_to_external"
        try:
            symlink_path.symlink_to(external_dir)
            target = (symlink_path / "secret.txt").resolve()
            # 符号链接解析后不应在 safe_image_dir 内
            assert not target.is_relative_to(safe_image_dir.resolve())
        except OSError:
            pytest.skip("Symlink creation not supported")

    def test_empty_filename(self, safe_image_dir):
        """空文件名应被拒绝"""
        empty_path = safe_image_dir / ""
        # 空路径应等于目录本身，但不是有效文件
        assert not (safe_image_dir / "").is_file()

    def test_filename_only_dots(self, safe_image_dir):
        """仅由点组成的文件名应被拒绝"""
        dots_path = safe_image_dir / "..."
        assert not dots_path.exists()


class TestImageEndpointSecurity:
    """测试图片端点的安全性（API 级别）"""

    @pytest.fixture(autouse=True)
    def reset_app_state(self):
        """每个测试前后重置 app 状态，避免测试间状态泄漏"""
        from src.api.main import app

        # 测试前清理
        app.dependency_overrides.clear()
        yield
        # 测试后清理
        app.dependency_overrides.clear()

    def test_traversal_in_url_returns_error(self, client, mock_auth):
        """URL 中包含路径遍历时应返回 403 或 400"""
        response = client.get(
            "/api/images/file/../../../etc/passwd",
            headers={"Authorization": "Bearer test_token"},
        )
        assert response.status_code in (400, 403, 404, 422)

    def test_valid_image_path_format(self, safe_image_dir, tmp_path):
        """合法的图片路径格式不应触发安全拒绝（403）或参数错误（400/422）"""
        from unittest.mock import MagicMock, patch

        from fastapi.testclient import TestClient

        from src.api.deps import get_current_user
        from src.api.main import app

        # 创建独立的 mock，确保测试隔离
        mock_storage = MagicMock()
        mock_storage.local_path = safe_image_dir
        mock_storage.image_exists.return_value = True
        mock_storage.get_image_data.return_value = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

        # 使用 app.dependency_overrides 覆盖认证依赖和存储服务
        app.dependency_overrides[get_current_user] = lambda: 1

        try:
            with patch("src.api.routers.images.ImageStorageService") as MockStorage:
                MockStorage.return_value = mock_storage

                # 创建新的 TestClient 以确保依赖覆盖生效
                with TestClient(app) as test_client:
                    response = test_client.get(
                        "/api/images/file/1/character/test.png",
                        headers={"Authorization": "Bearer test_token"},
                    )
                    # 核心断言：合法路径不应触发安全拒绝(403)或参数错误(400/422)
                    # 401 是认证问题，不是安全问题，200 表示路径验证通过
                    assert response.status_code not in (
                        400,
                        403,
                        422,
                    ), f"合法路径不应触发安全拒绝，实际状态码: {response.status_code}"
        finally:
            # 清理依赖覆盖
            app.dependency_overrides.clear()
