"""Operator-only rejection inspection. Run with the backend's evidence key.

python -m scripts.read_validation_evidence --user-id 7 --operation-id ID logs/app.log*
Output contains private diagnostic excerpts; do not publish it as a CI artifact.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterator

from src.observability.validation_evidence import decrypt_validation_evidence


def read_evidence(paths: list[Path], *, user_id: int, operation_id: str) -> Iterator[dict[str, Any]]:
    seen: set[str] = set()
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                try:
                    payload = json.loads(line)
                except ValueError:
                    continue  # Legacy non-JSON lines may share a rotation.
                if not isinstance(payload, dict) or payload.get("event") != "story_validation_evidence":
                    continue
                if payload.get("user_id") != user_id or payload.get("operation_id") != operation_id:
                    continue
                token = payload.get("encrypted_evidence")
                if not token:
                    yield {"phase": payload.get("phase"), "error_code": payload.get("error_code"),
                           "attempt_id": payload.get("attempt_id"), "outcome": "evidence_unavailable"}
                    continue
                if token in seen:
                    continue
                seen.add(token)
                yield {"timestamp": payload.get("timestamp"),
                       **decrypt_validation_evidence(payload, user_id=user_id, operation_id=operation_id)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", required=True, type=int)
    parser.add_argument("--operation-id", required=True)
    parser.add_argument("logs", nargs="+", type=Path)
    args = parser.parse_args()
    count = 0
    try:
        for row in read_evidence(args.logs, user_id=args.user_id, operation_id=args.operation_id):
            print(json.dumps(row, ensure_ascii=False))
            count += 1
    except (OSError, ValueError):
        parser.exit(2, "Cannot read/decrypt evidence; check log access, identity, and the matching evidence key.\n")
    if not count:
        parser.exit(1, "No retained evidence matches this user and operation.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
