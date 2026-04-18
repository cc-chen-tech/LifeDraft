"""契约测试 — docker-compose.ecs.yml 配置验证

验证服务定义、healthcheck 和网络配置符合预期。
"""

import yaml
import pytest


class TestDockerComposeContract:
    """契约测试：docker-compose 配置"""

    @pytest.fixture
    def compose(self):
        with open("docker-compose.ecs.yml") as f:
            return yaml.safe_load(f)

    def test_music_api_has_healthcheck(self, compose):
        """music-api 服务必须有 healthcheck"""
        services = compose.get("services", {})
        music_api = services.get("music-api", {})
        assert "healthcheck" in music_api, "music-api 必须配置 healthcheck"
        hc = music_api["healthcheck"]
        assert "test" in hc
        assert "interval" in hc
        assert "timeout" in hc
        assert "retries" in hc

    def test_backend_has_healthcheck(self, compose):
        """backend 服务必须有 healthcheck"""
        services = compose.get("services", {})
        backend = services.get("backend", {})
        assert "healthcheck" in backend, "backend 必须配置 healthcheck"

    def test_nginx_depends_on_backend(self, compose):
        """nginx 必须依赖 backend"""
        services = compose.get("services", {})
        nginx = services.get("nginx", {})
        depends_on = nginx.get("depends_on", [])
        assert "backend" in depends_on, "nginx 必须依赖 backend"

    def test_all_services_use_same_network(self, compose):
        """所有服务必须使用同一个网络"""
        services = compose.get("services", {})
        networks = compose.get("networks", {})
        network_name = list(networks.keys())[0] if networks else "story2-network"
        for name, svc in services.items():
            svc_nets = svc.get("networks", [])
            assert network_name in svc_nets, f"{name} 必须使用 {network_name} 网络"
