"""SQLAlchemy Raw SQL Security Contract Tests

验证数据库操作使用参数化查询，禁止字符串拼接 SQL。
Layer 3: 契约测试 — 防止 SQL 注入。
"""

import ast
from pathlib import Path


class TestSQLAlchemyRawSQLContract:
    """测试 SQLAlchemy SQL 安全契约"""

    def test_no_f_string_sql_in_database_code(self):
        """database/ 代码中不应使用 f-string 拼接 SQL 语句（除 add_performance_indexes.py 外）"""
        db_dir = Path(__file__).parent.parent / "src" / "database"
        violations = []

        for py_file in db_dir.rglob("*.py"):
            if py_file.name == "add_performance_indexes.py":
                continue
            content = py_file.read_text(encoding="utf-8")
            lines = content.split("\n")
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.JoinedStr):
                    for value in node.values:
                        if isinstance(value, ast.Constant) and isinstance(
                            value.value, str
                        ):
                            lowered = value.value.lower()
                            if any(
                                kw in lowered
                                for kw in [
                                    "select ",
                                    "insert ",
                                    "update ",
                                    "delete ",
                                    "drop ",
                                    "create ",
                                    "alter ",
                                ]
                            ):
                                # 排除日志语句：检查整行是否包含 logger.
                                line = (
                                    lines[node.lineno - 1]
                                    if node.lineno <= len(lines)
                                    else ""
                                )
                                if "logger." in line or "log." in line:
                                    continue
                                violations.append(
                                    f"{py_file.relative_to(db_dir.parent.parent)}:{node.lineno}: f-string SQL"
                                )

        assert (
            not violations
        ), f"发现 {len(violations)} 处 f-string 拼接 SQL:\n" + "\n".join(
            violations[:10]
        )

    def test_performance_indexes_use_constants(self):
        """add_performance_indexes.py 只能使用硬编码常量，不能拼接外部输入"""
        file_path = (
            Path(__file__).parent.parent
            / "src"
            / "database"
            / "add_performance_indexes.py"
        )
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content)

        # 检查 PERFORMANCE_INDEXES 是否为硬编码列表
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if (
                        isinstance(target, ast.Name)
                        and target.id == "PERFORMANCE_INDEXES"
                    ):
                        found = True
                        # 必须是常量列表（元组列表）
                        if isinstance(node.value, ast.List):
                            for elt in node.value.elts:
                                if not isinstance(elt, ast.Tuple):
                                    raise AssertionError(
                                        "PERFORMANCE_INDEXES 必须只包含硬编码的元组"
                                    )
                        else:
                            raise AssertionError(
                                "PERFORMANCE_INDEXES 必须是硬编码的列表"
                            )

        assert found, "未找到 PERFORMANCE_INDEXES 常量定义"

    def test_no_string_concatenation_in_filter(self):
        """SQLAlchemy filter 应使用 ORM 表达式，不应拼接字符串"""
        src_dir = Path(__file__).parent.parent / "src"
        violations = []

        for py_file in src_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            lines = content.split("\n")
            for i, line in enumerate(lines, 1):
                # 检查是否有 .filter() 中使用字符串拼接
                if ".filter(" in line and (
                    "+" in line or "%" in line or ".format(" in line
                ):
                    # 排除注释和日志
                    stripped = line.strip()
                    if stripped.startswith("#") or "logger" in stripped:
                        continue
                    violations.append(
                        f"{py_file.relative_to(src_dir.parent)}:{i}: {stripped}"
                    )

        assert (
            not violations
        ), f"发现 {len(violations)} 处可疑的 filter 字符串拼接:\n" + "\n".join(
            violations[:10]
        )
