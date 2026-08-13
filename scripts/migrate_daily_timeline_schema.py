#!/usr/bin/env python3
"""Preview or apply additive scene-image columns for daily timeline v2."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect, text

from src.database.models import engine


def pending_statements() -> list[str]:
    inspector = inspect(engine)
    columns = {item["name"] for item in inspector.get_columns("scene_images")}
    indexes = {item["name"] for item in inspector.get_indexes("scene_images")}
    statements: list[str] = []
    if "story_date" not in columns:
        statements.append("ALTER TABLE scene_images ADD COLUMN story_date VARCHAR(10)")
    if "day_index" not in columns:
        statements.append("ALTER TABLE scene_images ADD COLUMN day_index INTEGER")
    if "ix_scene_images_story_date" not in indexes:
        statements.append(
            "CREATE INDEX ix_scene_images_story_date ON scene_images (story_date)"
        )
    if "ix_scene_images_day_index" not in indexes:
        statements.append(
            "CREATE INDEX ix_scene_images_day_index ON scene_images (day_index)"
        )
    if "ix_scene_images_game_day_stage" not in indexes:
        statements.append(
            "CREATE UNIQUE INDEX ix_scene_images_game_day_stage "
            "ON scene_images (game_id, day_index, stage)"
        )
    return statements


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply", action="store_true", help="execute additive migration statements"
    )
    args = parser.parse_args()
    statements = pending_statements()
    if not statements:
        print("daily timeline schema is current")
        return 0
    for statement in statements:
        print(statement)
    if args.apply:
        with engine.begin() as connection:
            for statement in statements:
                connection.execute(text(statement))
        print(f"applied {len(statements)} statement(s)")
    else:
        print(f"dry-run: {len(statements)} statement(s); pass --apply to execute")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
