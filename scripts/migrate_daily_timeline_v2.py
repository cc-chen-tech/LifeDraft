#!/usr/bin/env python3
"""Preview or apply the idempotent v1-save to daily-timeline-v2 migration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.game.daily_timeline import migrate_legacy_state


def build_report(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    timeline = after["timeline"]
    return {
        "already_v2": before.get("timeline_version") == 2,
        "start_date": timeline["start_date"],
        "current_date": timeline["current_date"],
        "day_index": timeline["day_index"],
        "legacy_round_records": len(before.get("round_history") or []),
        "migrated_day_records": len(after.get("day_history") or []),
        "scheduled_events": len(after.get("scheduled_events") or []),
        "would_change": before != after,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="saved PlayerState JSON")
    parser.add_argument("--apply", action="store_true", help="replace input after preview")
    parser.add_argument("--output", type=Path, help="write migrated JSON to this path")
    args = parser.parse_args()

    before = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(before, dict):
        raise ValueError("save JSON must be an object")
    after = migrate_legacy_state(before)
    print(json.dumps(build_report(before, after), ensure_ascii=False, indent=2))

    target = args.output or (args.input if args.apply else None)
    if target is not None:
        target.write_text(
            json.dumps(after, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
