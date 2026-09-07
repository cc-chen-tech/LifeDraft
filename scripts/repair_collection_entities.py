#!/usr/bin/env python3
"""Preview or apply a safe, deterministic collection entity repair."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.database.models import GameState, SessionLocal
from src.services.entity_recognition_migration import repair_collection_state


def _latest_states(db: Any, game_id: Optional[int]) -> Iterable[GameState]:
    query = db.query(GameState)
    if game_id is not None:
        query = query.filter(GameState.game_id == game_id)
    rows = query.order_by(GameState.game_id.asc(), GameState.state_id.desc()).all()
    seen_games: set[int] = set()
    for row in rows:
        if row.game_id in seen_games:
            continue
        seen_games.add(row.game_id)
        yield row


def build_report(db: Any, game_id: Optional[int] = None) -> Dict[str, Any]:
    candidates = []
    for row in _latest_states(db, game_id):
        repaired, detail = repair_collection_state(dict(row.state_json or {}))
        candidates.append(
            {
                "game_id": row.game_id,
                "state_id": row.state_id,
                "detail": detail,
                "repaired_state": repaired,
            }
        )
    public_candidates = [
        {key: value for key, value in candidate.items() if key != "repaired_state"}
        for candidate in candidates
    ]
    encoded = json.dumps(public_candidates, ensure_ascii=False, sort_keys=True).encode()
    return {
        "candidates": public_candidates,
        "report_hash": hashlib.sha256(encoded).hexdigest(),
        "would_change": any(
            candidate["detail"].get("would_change") for candidate in candidates
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-id", type=int)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-report-hash")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    with SessionLocal() as db:
        report = build_report(db, args.game_id)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if not args.apply:
            return 0
        if args.expected_report_hash != report["report_hash"]:
            print(
                "report changed; run preview and pass its exact report hash",
                file=sys.stderr,
            )
            return 2

        for candidate in report["candidates"]:
            if not candidate["detail"].get("would_change"):
                continue
            row = (
                db.query(GameState)
                .filter(
                    GameState.game_id == candidate["game_id"],
                )
                .order_by(GameState.state_id.desc())
                .first()
            )
            if row is None or row.state_id != candidate["state_id"]:
                raise RuntimeError(
                    "latest collection repair state changed during apply"
                )
            repaired_state, _ = repair_collection_state(dict(row.state_json or {}))
            db.add(
                GameState(
                    game_id=row.game_id,
                    week=row.week,
                    age=row.age,
                    state_json=deepcopy(repaired_state),
                )
            )
        db.commit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
