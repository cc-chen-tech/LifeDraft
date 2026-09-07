"""Bounded progress persistence; a busy database must not stall playback."""

from __future__ import annotations

import sqlite3
import time
from typing import Any

from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from src.database.models import VoiceReadingProgress
from src.services.story_voice_repository import StoryVoiceReadingRepository


class ProgressStoreBusy(RuntimeError):
    """The client can retry its latest progress after the write lock clears."""


def save_voice_progress(db: Session, **values: Any) -> VoiceReadingProgress:
    """Use an owned connection so short busy timeouts never leak into the pool.

    Retry only SQLite BUSY/LOCKED, with a fresh transaction each time. The
    request Session is not used concurrently or passed to another thread.
    PostgreSQL keeps its normal transaction semantics.
    """
    bind = db.get_bind()
    if bind.dialect.name != "sqlite":
        progress = StoryVoiceReadingRepository(db).upsert_progress(**values)
        db.commit()
        return progress

    with bind.engine.connect() as connection:
        original_timeout = connection.exec_driver_sql(
            "PRAGMA busy_timeout"
        ).scalar_one()
        connection.exec_driver_sql("PRAGMA busy_timeout=200")
        connection.commit()
        try:
            for attempt in range(3):
                with Session(bind=connection, expire_on_commit=False) as write_db:
                    try:
                        progress = StoryVoiceReadingRepository(
                            write_db
                        ).upsert_progress(**values)
                        write_db.commit()
                        return progress
                    except OperationalError as error:
                        write_db.rollback()
                        code = getattr(error.orig, "sqlite_errorcode", None)
                        if not isinstance(error.orig, sqlite3.OperationalError) or (
                            code is None
                            or code & 0xFF
                            not in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
                        ):
                            raise
                        if attempt == 2:
                            raise ProgressStoreBusy(
                                "Playback progress store is busy"
                            ) from error
                time.sleep(0.05 * (attempt + 1))
        finally:
            connection.rollback()
            connection.exec_driver_sql(f"PRAGMA busy_timeout={int(original_timeout)}")
            connection.rollback()
    raise AssertionError("progress retry loop did not return")
