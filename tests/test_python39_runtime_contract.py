"""Runtime compatibility checks for the production Python image.

The ECS backend image currently runs Python 3.9. Keep source annotations
compatible with that runtime so imports do not fail after deployment.
"""

import ast
from pathlib import Path
import pytest

pytestmark = [pytest.mark.unit]



SRC_ROOT = Path(__file__).resolve().parents[1] / "src"


def _annotation_nodes(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.arg) and node.annotation is not None:
            yield node.annotation
        elif isinstance(node, ast.AnnAssign) and node.annotation is not None:
            yield node.annotation
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.returns is not None:
                yield node.returns


def test_src_annotations_do_not_use_pep604_union_syntax() -> None:
    offenders = []
    for path in SRC_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for annotation in _annotation_nodes(tree):
            for node in ast.walk(annotation):
                if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
                    offenders.append(f"{path.relative_to(SRC_ROOT.parent)}:{node.lineno}")

    assert not offenders, (
        "Python 3.9 production runtime cannot evaluate PEP 604 `A | B` "
        f"annotations. Use typing.Optional/Union instead: {offenders}"
    )
