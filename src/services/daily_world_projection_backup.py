"""Atomic, self-validating backups for daily-world-projection repairs."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Union

from sqlalchemy.orm import Session

from src.database.models import DailyWorldProjectionRepairAudit


DEFAULT_BACKUP_ROOT = Path("data/repair-backups/world-projection")
BACKUP_ROOT_ENV = "WORLD_PROJECTION_REPAIR_BACKUP_DIR"


class BackupChecksumMismatch(ValueError):
    """A backup's external or embedded integrity check did not validate."""


@dataclass(frozen=True)
class BackupInfo:
    """The filesystem identity needed to verify or restore one backup."""

    path: Path
    sha256: str


def write_state_backup(
    backup_root: Optional[Union[str, Path]],
    *,
    game_id: int,
    state_id: int,
    state_json: Any,
) -> BackupInfo:
    """Atomically persist a complete state snapshot before any repair mutation."""

    root = _backup_root(backup_root)
    root.mkdir(parents=True, exist_ok=True)
    state_sha256 = _sha256(_normalized_json_bytes(state_json))
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    destination = root / f"{timestamp}-game-{game_id}-state-{state_id}.json"
    payload = {
        "metadata": {
            "backup_format_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "game_id": game_id,
            "state_id": state_id,
        },
        "state_json": state_json,
        "state_sha256": state_sha256,
    }
    encoded = _normalized_json_bytes(payload)
    temporary_path: Optional[Path] = None
    try:
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.", suffix=".tmp", dir=str(root)
        )
        temporary_path = Path(temporary_name)
        with os.fdopen(file_descriptor, "wb") as temporary_file:
            temporary_file.write(encoded)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, destination)
        _fsync_directory(root)
    except BaseException:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        raise

    return BackupInfo(path=destination, sha256=_sha256(encoded))


def verify_state_backup(
    path: Union[str, Path],
    expected_sha256: str,
    *,
    expected_game_id: int,
    expected_state_id: int,
) -> bool:
    """Validate file bytes and embedded complete-state checksum without DB access."""

    _read_verified_payload(
        Path(path),
        expected_sha256,
        expected_game_id=expected_game_id,
        expected_state_id=expected_state_id,
    )
    return True


def restore_state_backup(
    path: Union[str, Path],
    expected_sha256: str,
    *,
    expected_game_id: int,
    expected_state_id: int,
) -> Any:
    """Return a verified complete snapshot without performing database writes."""

    payload = _read_verified_payload(
        Path(path),
        expected_sha256,
        expected_game_id=expected_game_id,
        expected_state_id=expected_state_id,
    )
    return payload["state_json"]


def create_repair_audit(
    db: Session,
    *,
    game_id: int,
    state_id: int,
    report_hash: str,
    backup_path: str,
    backup_sha256: str,
    non_projection_digest_before: str,
    detail_json: Mapping[str, Any],
) -> DailyWorldProjectionRepairAudit:
    """Stage the backed-up repair audit row; the caller owns transaction commit."""

    audit = DailyWorldProjectionRepairAudit(
        game_id=game_id,
        state_id=state_id,
        report_hash=report_hash,
        backup_path=backup_path,
        backup_sha256=backup_sha256,
        non_projection_digest_before=non_projection_digest_before,
        status="backed_up",
        detail_json=dict(detail_json),
    )
    db.add(audit)
    db.flush()
    return audit


def _backup_root(backup_root: Optional[Union[str, Path]]) -> Path:
    if backup_root is not None:
        return Path(backup_root).resolve()
    return Path(os.environ.get(BACKUP_ROOT_ENV, str(DEFAULT_BACKUP_ROOT))).resolve()


def _normalized_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _read_verified_payload(
    path: Path,
    expected_sha256: str,
    *,
    expected_game_id: int,
    expected_state_id: int,
) -> dict[str, Any]:
    encoded = path.read_bytes()
    if not hmac.compare_digest(_sha256(encoded), expected_sha256):
        raise BackupChecksumMismatch("backup checksum mismatch")
    try:
        payload = json.loads(encoded.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackupChecksumMismatch("backup checksum mismatch") from exc
    if not isinstance(payload, dict) or "state_json" not in payload:
        raise BackupChecksumMismatch("backup checksum mismatch")
    metadata = payload.get("metadata")
    if not isinstance(metadata, Mapping):
        raise BackupChecksumMismatch("backup metadata invalid")
    format_version = metadata.get("backup_format_version")
    game_id = metadata.get("game_id")
    state_id = metadata.get("state_id")
    if (
        type(format_version) is not int
        or format_version != 1
        or type(game_id) is not int
        or game_id <= 0
        or type(state_id) is not int
        or state_id <= 0
        or type(expected_game_id) is not int
        or expected_game_id <= 0
        or type(expected_state_id) is not int
        or expected_state_id <= 0
        or game_id != expected_game_id
        or state_id != expected_state_id
    ):
        raise BackupChecksumMismatch("backup metadata binding mismatch")
    state_sha256 = payload.get("state_sha256")
    if not isinstance(state_sha256, str) or not hmac.compare_digest(
        _sha256(_normalized_json_bytes(payload["state_json"])), state_sha256
    ):
        raise BackupChecksumMismatch("backup checksum mismatch")
    return payload


def _fsync_directory(directory: Path) -> None:
    directory_descriptor = os.open(str(directory), os.O_RDONLY)
    try:
        os.fsync(directory_descriptor)
    finally:
        os.close(directory_descriptor)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
