from __future__ import annotations

import os
import subprocess
from pathlib import Path
import pytest

pytestmark = [pytest.mark.e2e]



ROOT = Path(__file__).resolve().parents[1]
TEST_SH = ROOT / "test.sh"


def test_fresh_ownerless_lock_is_not_reclaimed_during_owner_publication(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "runs"
    lock_dir = run_root / "locks" / "e2e.lock"
    lock_dir.mkdir(parents=True)
    marker = tmp_path / "contender-ran"
    command = (
        f'set -- __source_only__; source "{TEST_SH}"; '
        f'with_e2e_lock touch "{marker}"'
    )

    result = subprocess.run(
        ["bash", "-c", command],
        cwd=ROOT,
        env={
            **os.environ,
            "TEST_RUN_ROOT": str(run_root),
            "TEST_NAMESPACE": "publication-contender",
        },
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )

    assert result.returncode != 0
    assert not marker.exists()
    assert lock_dir.exists()
    assert "owner" in (result.stdout + result.stderr).lower()
