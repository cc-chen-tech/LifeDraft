"""JWT Secret Security Contract Tests

验证 JWT 密钥不依赖硬编码回退值。
Layer 3: 契约测试 — 生产代码不能有硬编码的 fallback secret。
"""

import ast
import os
from pathlib import Path

# ★ 必须在导入 src.api.deps 之前设置环境变量，因为模块导入时会验证
os.environ.setdefault("JWT_SECRET", "test-secret-for-contract-tests")


class TestJWTSecretSecurityContract:
    """测试 JWT 密钥安全契约"""

    def test_jwt_secret_no_hardcoded_fallback(self):
        """JWT_SECRET 不能包含硬编码的 fallback 默认值"""
        deps_path = Path(__file__).parent.parent / "src" / "api" / "deps.py"
        source = deps_path.read_text(encoding="utf-8")

        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "JWT_SECRET":
                        # 检查 os.getenv 的第二个参数（默认值）
                        if (
                            isinstance(node.value, ast.Call)
                            and isinstance(node.value.func, ast.Attribute)
                            and node.value.func.attr == "getenv"
                        ):
                            # 如果 os.getenv 有两个参数，第二个就是 fallback
                            if len(node.value.args) >= 2:
                                fallback = node.value.args[1]
                                if (
                                    isinstance(fallback, ast.Constant)
                                    and fallback.value
                                ):
                                    raise AssertionError(
                                        f"JWT_SECRET 有硬编码回退值: {fallback.value!r}. "
                                        "生产代码不能包含硬编码的 JWT secret。"
                                    )
                            # 检查关键字参数 default=
                            for kw in node.value.keywords:
                                if kw.arg == "default":
                                    if (
                                        isinstance(kw.value, ast.Constant)
                                        and kw.value.value
                                    ):
                                        raise AssertionError(
                                            f"JWT_SECRET 有硬编码回退值: {kw.value.value!r}. "
                                            "生产代码不能包含硬编码的 JWT secret。"
                                        )

    def test_jwt_secret_uses_env_only(self):
        """JWT_SECRET 必须仅从环境变量读取"""
        deps_path = Path(__file__).parent.parent / "src" / "api" / "deps.py"
        source = deps_path.read_text(encoding="utf-8")

        # 源码中不应该有硬编码的 secret 字符串（除了 os.getenv 的调用本身）
        forbidden_secrets = [
            "dev-secret-change-in-production",
            "change-this-in-production",
            "your-secret-key",
            "supersecret",
            "mysecret",
        ]
        for secret in forbidden_secrets:
            assert secret not in source, f"发现硬编码的 JWT 回退密钥: {secret!r}"

    def test_decode_token_rejects_invalid_secret(self, monkeypatch):
        """decode_token 必须拒绝用错误密钥签名的 token"""
        monkeypatch.setenv("JWT_SECRET", "test-secret-for-contract-tests")

        # ★ 重新导入以确保使用当前环境变量
        import importlib

        from src.api import deps as deps_module

        importlib.reload(deps_module)
        decode_token = deps_module.decode_token

        from datetime import datetime, timedelta

        from jose import jwt

        # 用正确的密钥签名
        payload = {"sub": "123", "exp": datetime.utcnow() + timedelta(hours=1)}
        valid_token = jwt.encode(
            payload, "test-secret-for-contract-tests", algorithm="HS256"
        )

        # 用错误的密钥签名
        invalid_token = jwt.encode(payload, "wrong-secret", algorithm="HS256")

        # 正确密钥的 token 应该能解码
        assert decode_token(valid_token) == 123

        # 错误密钥的 token 应该返回 None
        assert decode_token(invalid_token) is None
