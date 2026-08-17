"""SSE 超时配置契约测试。

验证 Nginx 和后端 SSE 超时配置的一致性，
确保 Nginx 不会在 SSE 生成完成前断开连接。
"""

import re
from pathlib import Path
import pytest

pytestmark = [pytest.mark.unit]


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent


class TestNginxSSETimeoutContract:
    """Nginx 与 SSE 超时配置契约。"""

    def _read_nginx_conf(self) -> str:
        conf_path = PROJECT_ROOT / "nginx" / "ecs-nginx.conf"
        return conf_path.read_text()

    def _extract_api_location_block(self, conf: str) -> str:
        """提取 /api/ location 块的内容。"""
        # 找到 location /api/ { ... } 块
        pattern = r"location\s+/api/\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}"
        match = re.search(pattern, conf)
        assert match, "未找到 location /api/ 配置块"
        return match.group(1)

    def _extract_timeout_value(self, block: str, directive: str) -> int:
        """从配置块中提取超时值（秒）。"""
        pattern = rf"{directive}\s+(\d+)s?"
        match = re.search(pattern, block)
        assert match, f"未找到 {directive} 配置"
        return int(match.group(1))

    def test_proxy_read_timeout_gte_360s(self):
        """Nginx proxy_read_timeout 必须 >= 360s（大于 SSE_STREAM_TIMEOUT 330s）。"""
        conf = self._read_nginx_conf()
        api_block = self._extract_api_location_block(conf)
        timeout = self._extract_timeout_value(api_block, "proxy_read_timeout")
        assert timeout >= 360, (
            f"proxy_read_timeout={timeout}s 小于要求的 360s，"
            f"将导致 Nginx 在 SSE 生成完成前断开连接"
        )

    def test_proxy_send_timeout_gte_360s(self):
        """Nginx proxy_send_timeout 必须 >= 360s。"""
        conf = self._read_nginx_conf()
        api_block = self._extract_api_location_block(conf)
        timeout = self._extract_timeout_value(api_block, "proxy_send_timeout")
        assert timeout >= 360, f"proxy_send_timeout={timeout}s 小于要求的 360s"

    def test_proxy_buffering_off(self):
        """SSE 需要 proxy_buffering off 确保心跳及时送达。"""
        conf = self._read_nginx_conf()
        api_block = self._extract_api_location_block(conf)
        assert "proxy_buffering off" in api_block or "proxy_buffering  off" in api_block, (
            "location /api/ 缺少 proxy_buffering off，"
            "将导致 SSE 心跳被缓冲，Nginx 因空闲超时断开连接"
        )

    def test_proxy_socket_keepalive_on(self):
        """TCP keepalive 保持长连接活跃。"""
        conf = self._read_nginx_conf()
        api_block = self._extract_api_location_block(conf)
        assert (
            "proxy_socket_keepalive on" in api_block
        ), "location /api/ 缺少 proxy_socket_keepalive on"


class TestNginxStaticAssetTransportContract:
    """Nginx 静态资源传输配置契约。"""

    def _read_nginx_conf(self) -> str:
        conf_path = PROJECT_ROOT / "nginx" / "ecs-nginx.conf"
        return conf_path.read_text()

    def test_https_listener_does_not_advertise_http2_for_next_static_assets(self):
        """Next.js chunks 必须先走 HTTP/1.1，避免浏览器 HTTP/2 chunk 加载失败后无法 hydration。"""
        conf = self._read_nginx_conf()
        assert "listen 443 ssl http2" not in conf


class TestSSETimeoutConstants:
    """后端 SSE 超时常量契约。"""

    def test_sse_stream_timeout_is_module_constant(self):
        """SSE_STREAM_TIMEOUT 应为模块级常量而非函数内硬编码。"""
        sse_helpers_path = PROJECT_ROOT / "src" / "api" / "routers" / "gameplay" / "sse_helpers.py"
        content = sse_helpers_path.read_text()

        # 检查模块级定义（在函数外部）
        lines = content.split("\n")
        found_module_level = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("SSE_STREAM_TIMEOUT") and "=" in stripped:
                # 检查缩进 — 模块级应无缩进或仅有少量缩进
                if not line.startswith(" ") and not line.startswith("\t"):
                    found_module_level = True
                    break
                # 也接受顶层缩进为0的情况
                if len(line) - len(line.lstrip()) == 0:
                    found_module_level = True
                    break

        assert found_module_level, (
            "SSE_STREAM_TIMEOUT 应定义为模块级常量，" "当前可能在函数内部硬编码"
        )

    def test_heartbeat_interval_is_module_constant(self):
        """heartbeat_interval 应为模块级常量。"""
        sse_helpers_path = PROJECT_ROOT / "src" / "api" / "routers" / "gameplay" / "sse_helpers.py"
        content = sse_helpers_path.read_text()

        lines = content.split("\n")
        found_module_level = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if "HEARTBEAT_INTERVAL" in stripped and "=" in stripped:
                if len(line) - len(line.lstrip()) == 0:
                    found_module_level = True
                    break

        assert found_module_level, "HEARTBEAT_INTERVAL 应定义为模块级常量"

    def test_sse_timeout_greater_than_nginx_timeout(self):
        """SSE_STREAM_TIMEOUT 必须大于 Nginx proxy_read_timeout。"""
        sse_helpers_path = PROJECT_ROOT / "src" / "api" / "routers" / "gameplay" / "sse_helpers.py"
        content = sse_helpers_path.read_text()

        # 提取 SSE_STREAM_TIMEOUT 值
        match = re.search(r"SSE_STREAM_TIMEOUT\s*=\s*(\d+)", content)
        assert match, "未找到 SSE_STREAM_TIMEOUT 定义"
        sse_timeout = int(match.group(1))

        # 提取 Nginx timeout
        conf_path = PROJECT_ROOT / "nginx" / "ecs-nginx.conf"
        conf = conf_path.read_text()
        api_block_match = re.search(r"location\s+/api/\s*\{([^}]*(?:\{[^}]*\}[^}]*)*)\}", conf)
        assert api_block_match
        nginx_match = re.search(r"proxy_read_timeout\s+(\d+)", api_block_match.group(1))
        assert nginx_match
        nginx_timeout = int(nginx_match.group(1))

        assert sse_timeout < nginx_timeout, (
            f"SSE_STREAM_TIMEOUT({sse_timeout}s) 应小于 "
            f"Nginx proxy_read_timeout({nginx_timeout}s)，"
            f"否则 Nginx 会在后端超时前断开连接"
        )

    def test_heartbeat_interval_lte_5s(self):
        """心跳间隔不能超过 5s，防止 Nginx 空闲断连。"""
        sse_helpers_path = PROJECT_ROOT / "src" / "api" / "routers" / "gameplay" / "sse_helpers.py"
        content = sse_helpers_path.read_text()

        match = re.search(r"(?:HEARTBEAT_INTERVAL|heartbeat_interval)\s*=\s*(\d+)", content)
        assert match, "未找到心跳间隔定义"
        interval = int(match.group(1))
        assert interval <= 5, f"心跳间隔 {interval}s > 5s，可能导致 Nginx 空闲断连"
