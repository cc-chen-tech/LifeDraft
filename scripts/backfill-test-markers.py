#!/usr/bin/env python3
"""One-off marker backfill: classify every unmarked test file into the
pytest.ini markers (unit / integration / api / e2e / slow) based on naming.

Rules (first match wins):
  e2e         name contains "_e2e"
  integration name contains "_db" or "_integration"
  api         name contains "_api" or "_router" or starts with "test_api_"
  unit        everything else
  slow        additionally when the file contains time.sleep(...)

Files that already use a layer marker are left untouched. Idempotent.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"

SLEEP_RE = re.compile(r"time\.sleep\(")
LAYER_RE = re.compile(r"pytest\.mark\.(unit|integration|api|e2e|slow)")


def classify(name: str, text: str) -> list[str]:
    if "_e2e" in name:
        primary = "e2e"
    elif "_db" in name or "_integration" in name:
        primary = "integration"
    elif "_api" in name or "_router" in name or name.startswith("test_api_"):
        primary = "api"
    else:
        primary = "unit"
    markers = [primary]
    if SLEEP_RE.search(text):
        markers.append("slow")
    return markers


def last_import_line(tree: ast.Module, default: int) -> int:
    last = default
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            last = max(last, node.end_lineno)
    return last


def main() -> None:
    changed = []
    skipped = []
    for path in sorted(TESTS.rglob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        if LAYER_RE.search(text):
            skipped.append(path.name)
            continue
        markers = classify(path.name, text)
        tree = ast.parse(text)
        insert_at = last_import_line(tree, 1)
        lines = text.splitlines(keepends=True)
        idx = insert_at  # 1-based line -> 0-based index of the following line
        marker_line = "pytestmark = [pytest.mark." + ", pytest.mark.".join(markers) + "]\n"
        needs_pytest_import = not re.search(r"^\s*(import pytest|from pytest)", text, re.M)
        if needs_pytest_import:
            insertion = "import pytest\n\n" + marker_line + "\n"
        else:
            insertion = "\n" + marker_line + "\n"
        lines[idx:idx] = [insertion]
        path.write_text("".join(lines), encoding="utf-8")
        changed.append((path.name, markers))
    print(f"changed: {len(changed)} files, skipped (already marked): {len(skipped)}")
    for name, markers in changed:
        print(f"  {name} -> {markers}")


if __name__ == "__main__":
    main()
