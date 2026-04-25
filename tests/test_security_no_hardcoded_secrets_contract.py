"""No Hardcoded Secrets Contract Tests

验证源码和配置中不包含硬编码的 API 密钥、密码等敏感信息。
Layer 3: 契约测试 — 禁止将 secrets 提交到版本控制。
"""

import ast
from pathlib import Path


class TestNoHardcodedSecretsContract:
    """测试无硬编码密钥契约"""

    # 可疑的密钥模式（用于检测误提交的密钥）
    SUSPICIOUS_PATTERNS = [
        "sk-",  # OpenAI/DeepSeek API key prefix
        "sk-ant-",  # Anthropic API key
        "AK",  # 阿里云/腾讯云 AccessKey
        "ghp_",  # GitHub PAT
        "-----BEGIN",  # PEM/SSH key
    ]

    # 允许出现的模式（在测试数据、文档中）
    ALLOWLIST = [
        "sk-example",  # 示例
        "sk-test",  # 测试
        "sk-xxxxxxxx",  # 占位符
        "AKIDxxxxxxxx",  # 占位符
    ]

    def test_no_api_keys_in_tracked_source_files(self):
        """被 git 跟踪的源码文件中不应包含真实 API 密钥"""
        import subprocess

        result = subprocess.run(
            ["git", "ls-files", "src/", "tests/"],
            capture_output=True, text=True, cwd=Path(__file__).parent.parent,
        )
        tracked_files = result.stdout.strip().split("\n")

        violations = []
        for rel_path in tracked_files:
            if not rel_path.endswith(".py"):
                continue
            file_path = Path(__file__).parent.parent / rel_path
            if not file_path.exists():
                continue
            content = file_path.read_text(encoding="utf-8")
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                # 跳过注释和字符串中的示例
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith('"""'):
                    continue
                # 检查可疑模式
                for pattern in self.SUSPICIOUS_PATTERNS:
                    if pattern in line:
                        # 检查是否在允许列表中
                        if any(allow in line for allow in self.ALLOWLIST):
                            continue
                        # 检查是否是 os.getenv 调用（从环境变量读取是允许的）
                        if "getenv" in line or "environ" in line:
                            continue
                        violations.append(f"{rel_path}:{i}: {line.strip()}")

        assert not violations, (
            f"发现 {len(violations)} 处可能的硬编码密钥:\n" + "\n".join(violations[:20])
        )

    def test_env_file_not_tracked(self):
        """.env 文件不应被 git 跟踪"""
        import subprocess

        result = subprocess.run(
            ["git", "ls-files", ".env"],
            capture_output=True, text=True, cwd=Path(__file__).parent.parent,
        )
        tracked = result.stdout.strip()
        assert not tracked, (
            ".env 文件不应被 git 跟踪（它包含敏感配置）。"
            "请从 git 中移除: git rm --cached .env"
        )

    def test_getenv_used_for_secrets(self):
        """密钥应通过 os.getenv 读取，不应直接硬编码"""
        deps_path = Path(__file__).parent.parent / "src" / "api" / "deps.py"
        source = deps_path.read_text(encoding="utf-8")
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and "SECRET" in target.id:
                        # SECRET 变量必须通过 os.getenv 读取
                        if isinstance(node.value, ast.Call):
                            if (
                                isinstance(node.value.func, ast.Attribute)
                                and node.value.func.attr == "getenv"
                            ):
                                continue  # 正确：通过环境变量读取
                        raise AssertionError(
                            f"变量 {target.id} 必须通过 os.getenv() 读取，"
                            f"当前赋值方式不安全: {ast.dump(node.value)[:80]}"
                        )
