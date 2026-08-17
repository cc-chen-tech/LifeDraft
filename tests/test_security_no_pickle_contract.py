"""Pickle Deserialization Security Contract Tests

验证代码库中不使用 pickle 进行序列化/反序列化。
Layer 3: 契约测试 — pickle 可导致任意代码执行，必须禁止。
"""

from pathlib import Path
import pytest

pytestmark = [pytest.mark.unit]



class TestNoPickleContract:
    """测试禁止 pickle 契约"""

    def test_no_pickle_in_source(self):
        """src/ 目录中不应使用 pickle 或 cPickle"""
        src_dir = Path(__file__).parent.parent / "src"
        violations = []

        for py_file in src_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith('"""'):
                    continue
                if "import pickle" in stripped or "import cPickle" in stripped:
                    violations.append(f"{py_file.relative_to(src_dir.parent)}:{i}: {stripped}")

        assert (
            not violations
        ), f"发现 {len(violations)} 处 pickle 使用（可导致任意代码执行）:\n" + "\n".join(
            violations[:10]
        )

    def test_no_pickle_loads_or_dumps_in_source(self):
        """src/ 目录中不应调用 pickle.loads/dumps/load/dump"""
        src_dir = Path(__file__).parent.parent / "src"
        violations = []

        for py_file in src_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith('"""'):
                    continue
                if any(
                    call in stripped
                    for call in [
                        "pickle.loads(",
                        "pickle.dumps(",
                        "pickle.load(",
                        "pickle.dump(",
                    ]
                ):
                    violations.append(f"{py_file.relative_to(src_dir.parent)}:{i}: {stripped}")

        assert not violations, f"发现 {len(violations)} 处 pickle 调用:\n" + "\n".join(
            violations[:10]
        )
