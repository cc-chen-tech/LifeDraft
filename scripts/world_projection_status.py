#!/usr/bin/env python3
"""Print a read-only snapshot of durable daily world projection health."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional, Sequence, TextIO

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.database.models import SessionLocal
from src.services.daily_world_projection_observability import (
    summarize_projection_health,
)


EXIT_OK = 0
EXIT_QUERY_ERROR = 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Report durable daily world projection health without mutation."
    )
    parser.add_argument(
        "--json", action="store_true", help="Print the stable JSON snapshot."
    )
    return parser


def run(
    argv: Optional[Sequence[str]] = None,
    *,
    session_factory: Callable[[], Any] = SessionLocal,
    now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    stdout: Optional[TextIO] = None,
    stderr: Optional[TextIO] = None,
) -> int:
    """Query once; unhealthy data is still a successful operator read."""

    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    try:
        args = _parser().parse_args(list(argv) if argv is not None else None)
    except SystemExit as exc:
        return int(exc.code)

    session = None
    try:
        session = session_factory()
        snapshot = summarize_projection_health(session, now_fn())
    except Exception:
        # Connection exceptions can contain deployment details; keep operator
        # output actionable without echoing credentials or database URLs.
        print("projection health query failed", file=stderr)
        return EXIT_QUERY_ERROR
    finally:
        if session is not None:
            session.close()

    payload = snapshot.to_dict()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True), file=stdout)
    else:
        for key, value in payload.items():
            print(
                f"{key}: {json.dumps(value, ensure_ascii=False, sort_keys=True)}",
                file=stdout,
            )
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(run())
