from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEST_SH = ROOT / "test.sh"
TURBOPACK_ROOT_RESOLVER = (
    ROOT / "frontend" / "scripts" / "resolve-turbopack-root.mjs"
)


def _source_and_run(command: str) -> str:
    return f'set -- __source_only__; source "{TEST_SH}"; {command}'


def _runtime_env(run_root: Path, namespace: str) -> dict[str, str]:
    return {
        **os.environ,
        "TEST_RUN_ROOT": str(run_root),
        "TEST_NAMESPACE": namespace,
    }


def _wait_for(path: Path, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return
        time.sleep(0.02)
    raise AssertionError(f"timed out waiting for {path}")


def _start_lock_holder(
    run_root: Path,
    namespace: str,
    ready_file: Path,
) -> subprocess.Popen[str]:
    command = _source_and_run(
        f'with_e2e_lock bash -c \'touch "{ready_file}"; exec sleep 30\''
    )
    return subprocess.Popen(
        ["bash", "-c", command],
        cwd=ROOT,
        env=_runtime_env(run_root, namespace),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )


def _terminate_process_group(process: subprocess.Popen[str]) -> tuple[str, str]:
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
    return process.communicate(timeout=5)


def test_turbopack_root_contains_linked_worktree_and_real_dependencies(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    project = repository / ".worktrees" / "feature" / "frontend"
    real_node_modules = repository / "frontend" / "node_modules"
    project.mkdir(parents=True)
    real_node_modules.mkdir(parents=True)
    (project / "node_modules").symlink_to(real_node_modules, target_is_directory=True)

    probe = subprocess.run(
        [
            "node",
            "--input-type=module",
            "--eval",
            (
                "const { resolveTurbopackRoot } = await import(process.argv[1]); "
                "console.log(resolveTurbopackRoot(process.argv[2]));"
            ),
            TURBOPACK_ROOT_RESOLVER.as_uri(),
            str(project),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert probe.returncode == 0, probe.stderr
    assert Path(probe.stdout.strip()) == repository


def test_live_e2e_owner_blocks_another_worktree_and_reports_owner(tmp_path: Path) -> None:
    run_root = tmp_path / "runs"
    ready_file = tmp_path / "holder-ready"
    holder = _start_lock_holder(run_root, "holder-worktree", ready_file)
    try:
        _wait_for(ready_file)
        owner_file = run_root / "locks" / "e2e.lock" / "owner"
        _wait_for(owner_file)

        marker = tmp_path / "contender-ran"
        contender = subprocess.run(
            [
                "bash",
                "-c",
                _source_and_run(f'with_e2e_lock touch "{marker}"'),
            ],
            cwd=ROOT,
            env=_runtime_env(run_root, "contender-worktree"),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )

        output = contender.stdout + contender.stderr
        assert contender.returncode != 0
        assert not marker.exists()
        assert "holder-worktree" in output
        assert str(ROOT) in output
        assert f"pid={holder.pid}" in owner_file.read_text(encoding="utf-8")
    finally:
        _terminate_process_group(holder)


def test_parallel_e2e_override_is_rejected_before_command_runs(tmp_path: Path) -> None:
    marker = tmp_path / "parallel-ran"
    env = _runtime_env(tmp_path / "runs", "parallel-request")
    env["TEST_ALLOW_PARALLEL_E2E"] = "1"

    result = subprocess.run(
        ["bash", "-c", _source_and_run(f'with_e2e_lock touch "{marker}"')],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )

    assert result.returncode != 0
    assert not marker.exists()
    assert "TEST_ALLOW_PARALLEL_E2E=1" in result.stdout + result.stderr


def test_stale_e2e_lock_is_reclaimed_atomically(tmp_path: Path) -> None:
    run_root = tmp_path / "runs"
    lock_dir = run_root / "locks" / "e2e.lock"
    lock_dir.mkdir(parents=True)
    (lock_dir / "owner").write_text(
        "pid=99999999\nnamespace=dead-worktree\nproject=/tmp/dead-worktree\n",
        encoding="utf-8",
    )
    marker = tmp_path / "reclaimed-ran"

    result = subprocess.run(
        ["bash", "-c", _source_and_run(f'with_e2e_lock touch "{marker}"')],
        cwd=ROOT,
        env=_runtime_env(run_root, "reclaimer-worktree"),
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert marker.exists()
    assert not lock_dir.exists()


def test_signal_releases_owned_e2e_lock(tmp_path: Path) -> None:
    run_root = tmp_path / "runs"
    ready_file = tmp_path / "signal-ready"
    holder = _start_lock_holder(run_root, "signal-owner", ready_file)
    lock_dir = run_root / "locks" / "e2e.lock"
    _wait_for(ready_file)
    _wait_for(lock_dir / "owner")

    _terminate_process_group(holder)

    assert holder.returncode != 0
    assert not lock_dir.exists()


def test_cleanup_preserves_lock_after_owner_changes(tmp_path: Path) -> None:
    run_root = tmp_path / "runs"
    ready_file = tmp_path / "changed-owner-ready"
    holder = _start_lock_holder(run_root, "original-owner", ready_file)
    lock_dir = run_root / "locks" / "e2e.lock"
    owner_file = lock_dir / "owner"
    try:
        _wait_for(ready_file)
        _wait_for(owner_file)
        owner_file.write_text(
            f"pid={os.getpid()}\nnamespace=replacement-owner\nproject={ROOT}\n",
            encoding="utf-8",
        )

        _terminate_process_group(holder)

        assert lock_dir.exists()
        assert "namespace=replacement-owner" in owner_file.read_text(encoding="utf-8")
    finally:
        if holder.poll() is None:
            _terminate_process_group(holder)
        owner_file.unlink(missing_ok=True)
        lock_dir.rmdir()
