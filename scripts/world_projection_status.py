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
    session_factory: Optional[Callable[[], Any]] = None,
    summarizer: Optional[Callable[[Any, datetime], Any]] = None,
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

    session: Optional[Any] = None
    snapshot: Optional[Any] = None
    failed = False
    try:
        if session_factory is None:
            from src.database.models import SessionLocal

            session_factory = SessionLocal
        if summarizer is None:
            from src.services.daily_world_projection_observability import (
                summarize_projection_health,
            )

            summarizer = summarize_projection_health
        session = session_factory()
        snapshot = summarizer(session, now_fn())
    except Exception:
        failed = True
    finally:
        if session is not None:
            try:
                session.close()
            except Exception:
                failed = True

    if failed or snapshot is None:
        # Import, connection, query, and cleanup exceptions can contain deployment
        # details; never echo their text, a URL, or a credential to the terminal.
        print("projection health query failed", file=stderr)
        return EXIT_QUERY_ERROR

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
