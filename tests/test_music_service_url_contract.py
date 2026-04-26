"""契约测试 — Music Service URL 配置

验证 NeteaseMusicClient 使用正确的默认 URL，
确保 Docker 环境中能正确连接 music-api 服务。
"""

import os
from unittest.mock import patch

from src.services.music_service import NeteaseMusicClient


class TestMusicServiceUrlContract:
    """契约测试：Music Service URL 配置"""

    def test_default_url_uses_music_api_service(self):
        """默认 URL 应指向 music-api:3001，而非 localhost:3000"""
        # 清除环境变量，强制使用默认值
        with patch.dict(os.environ, {}, clear=True):
            client = NeteaseMusicClient()
            assert (
                client.base_url == "http://music-api:3001"
            ), f"默认 URL 应为 http://music-api:3001，实际为 {client.base_url}"

    def test_env_override_works(self):
        """NETEASE_MUSIC_API_URL 环境变量应覆盖默认值"""
        with patch.dict(os.environ, {"NETEASE_MUSIC_API_URL": "http://custom:9999"}):
            client = NeteaseMusicClient()
            assert client.base_url == "http://custom:9999"

    def test_explicit_base_url_takes_precedence(self):
        """构造函数参数应具有最高优先级"""
        with patch.dict(os.environ, {"NETEASE_MUSIC_API_URL": "http://env:1111"}):
            client = NeteaseMusicClient(base_url="http://explicit:7777")
            assert client.base_url == "http://explicit:7777"

    def test_localhost_replaced_with_ipv4(self):
        """localhost 应被替换为 127.0.0.1 避免 IPv6 问题"""
        client = NeteaseMusicClient(base_url="http://localhost:3001")
        assert client.base_url == "http://127.0.0.1:3001"
