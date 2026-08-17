"""Contracts for durable, self-validating repair backups."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

import pytest

import src.services.daily_world_projection_backup as backup_service
from src.services.daily_world_projection_backup import (
    BackupChecksumMismatch,
    restore_state_backup,
    verify_state_backup,
    write_state_backup,
)

pytestmark = [pytest.mark.unit]



def state_fixture() -> dict[str, object]:
    return {
        "timeline": {"day_index": 4, "current_date": "2026-08-17"},
        "relationships": {"李长庚": 42},
        "world_projection_state": {"applied_through_day_index": 3},
    }


def test_backup_preserves_complete_state_and_verifies_file_checksum(
    tmp_path: Path,
) -> None:
    """A backup must survive a round-trip with every saved field intact."""

    state = state_fixture()
    backup = write_state_backup(tmp_path, game_id=23, state_id=9001, state_json=state)

    assert backup.path.exists()
    assert backup.path.parent == tmp_path
    assert (
        verify_state_backup(
            backup.path,
            backup.sha256,
            expected_game_id=23,
            expected_state_id=9001,
        )
        is True
    )
    assert (
        restore_state_backup(
            backup.path,
            backup.sha256,
            expected_game_id=23,
            expected_state_id=9001,
        )
        == state
    )


def test_backup_fsyncs_file_and_parent_directory(monkeypatch, tmp_path: Path) -> None:
    """Durability requires syncing both written bytes and the replace directory entry."""

    synced_file_types: list[bool] = []
    original_fsync = backup_service.os.fsync

    def recording_fsync(file_descriptor: int) -> None:
        synced_file_types.append(stat.S_ISDIR(os.fstat(file_descriptor).st_mode))
        original_fsync(file_descriptor)

    monkeypatch.setattr(backup_service.os, "fsync", recording_fsync)

    write_state_backup(tmp_path, game_id=28, state_id=9007, state_json=state_fixture())

    assert synced_file_types == [False, True]


def test_backup_uses_configured_default_root(monkeypatch, tmp_path: Path) -> None:
    """Operations can redirect durable repair backups without a caller path."""

    configured_root = tmp_path / "configured-repair-backups"
    monkeypatch.setenv("WORLD_PROJECTION_REPAIR_BACKUP_DIR", str(configured_root))

    backup = write_state_backup(
        None, game_id=24, state_id=9002, state_json=state_fixture()
    )

    assert backup.path.parent == configured_root
    assert backup.path.name.endswith("-game-24-state-9002.json")


def test_backup_uses_project_repair_root_without_override(
    monkeypatch, tmp_path: Path
) -> None:
    """The no-argument path is the documented project-local repair root."""

    monkeypatch.delenv("WORLD_PROJECTION_REPAIR_BACKUP_DIR", raising=False)
    monkeypatch.chdir(tmp_path)

    backup = write_state_backup(
        None, game_id=27, state_id=9006, state_json=state_fixture()
    )

    assert backup.path.parent == tmp_path / "data/repair-backups/world-projection"


def test_restore_rejects_changed_backup_bytes(tmp_path: Path) -> None:
    """A caller cannot restore a backup whose recorded on-disk digest changed."""

    backup = write_state_backup(
        tmp_path, game_id=25, state_id=9003, state_json=state_fixture()
    )
    backup.path.write_text("corrupt", encoding="utf-8")

    with pytest.raises(BackupChecksumMismatch):
        restore_state_backup(
            backup.path,
            backup.sha256,
            expected_game_id=25,
            expected_state_id=9003,
        )


def test_restore_rejects_state_with_recomputed_file_digest(tmp_path: Path) -> None:
    """A valid file digest cannot bypass the embedded complete-state digest."""

    backup = write_state_backup(
        tmp_path, game_id=26, state_id=9004, state_json=state_fixture()
    )
    payload = json.loads(backup.path.read_text(encoding="utf-8"))
    payload["state_json"]["relationships"]["李长庚"] = 999
    tampered_bytes = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    backup.path.write_bytes(tampered_bytes)
    replacement_checksum = hashlib.sha256(tampered_bytes).hexdigest()

    with pytest.raises(BackupChecksumMismatch):
        restore_state_backup(
            backup.path,
            replacement_checksum,
            expected_game_id=26,
            expected_state_id=9004,
        )


@pytest.mark.parametrize(
    ("metadata_update", "expected_game_id", "expected_state_id"),
    [
        ({}, 999, 9005),
        ({}, 29, 999),
        ({"backup_format_version": 0}, 29, 9005),
        ({"game_id": True}, 29, 9005),
        ({"state_id": True}, 29, 9005),
    ],
)
def test_backup_rejects_wrong_owner_or_format_even_with_valid_file_checksum(
    tmp_path: Path,
    metadata_update: dict[str, object],
    expected_game_id: int,
    expected_state_id: int,
) -> None:
    backup = write_state_backup(
        tmp_path, game_id=29, state_id=9005, state_json=state_fixture()
    )
    payload = json.loads(backup.path.read_text(encoding="utf-8"))
    payload["metadata"].update(metadata_update)
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    backup.path.write_bytes(encoded)

    with pytest.raises(BackupChecksumMismatch):
        restore_state_backup(
            backup.path,
            hashlib.sha256(encoded).hexdigest(),
            expected_game_id=expected_game_id,
            expected_state_id=expected_state_id,
        )
