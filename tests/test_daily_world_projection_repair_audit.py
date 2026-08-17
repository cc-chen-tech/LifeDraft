"""Database contracts for projection-repair audit records."""

from __future__ import annotations

from src.database.models import DailyWorldProjectionRepairAudit, Game
from src.services.daily_world_projection_backup import create_repair_audit


def test_create_repair_audit_records_backup_and_visible_digest(db_session) -> None:
    """A completed backup gains a durable audit record before repair work begins."""

    game = Game(initial_state={})
    db_session.add(game)
    db_session.flush()
    audit = create_repair_audit(
        db_session,
        game_id=game.game_id,
        state_id=9005,
        report_hash="a" * 64,
        backup_path="data/repair-backups/world-projection/backup.json",
        backup_sha256="b" * 64,
        non_projection_digest_before="c" * 64,
        detail_json={"rebuild_day_indexes": [0, 1]},
    )
    db_session.commit()

    stored = db_session.get(DailyWorldProjectionRepairAudit, audit.audit_id)
    assert stored is not None
    assert stored.status == "backed_up"
    assert stored.non_projection_digest_after is None
    assert stored.detail_json == {"rebuild_day_indexes": [0, 1]}
