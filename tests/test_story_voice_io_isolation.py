"""Real SQLite contention must not freeze unrelated voice HTTP requests."""

import asyncio
import sqlite3
import threading
import time

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from src.api.deps import get_current_user, get_session
from src.api.routers.voice_reading import router
from src.database.models import Base, User, VoiceReadingProgress

pytestmark = pytest.mark.integration


@pytest.fixture
def voice_http(tmp_path):
    database = tmp_path / "voice-lock.sqlite"
    engine = create_engine(
        f"sqlite:///{database}", connect_args={"check_same_thread": False, "timeout": 2}
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as session:
        session.add(User(user_id=1, private_id="voice-lock", public_id="voice-lock"))
        session.add(
            VoiceReadingProgress(
                user_id=1,
                game_id=1,
                day_index=0,
                text_hash="chapter",
                voice_id="female-shaonv",
                speed=1.0,
                paragraph_index=0,
                position_ms=0,
                completed=False,
            )
        )
        session.commit()
    app = FastAPI()
    app.include_router(router, prefix="/api/voice-reading")

    def session_dependency():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_session] = session_dependency
    app.dependency_overrides[get_current_user] = lambda: 1

    @app.get("/health")
    async def health():
        return {"ok": True}

    yield app, engine, database, sessions
    engine.dispose()


def _progress(position=1500):
    return dict(
        game_id=1,
        day_index=0,
        text_hash="chapter",
        voice_id="female-shaonv",
        speed=1.0,
        paragraph_index=0,
        position_ms=position,
        completed=False,
    )


async def test_contended_progress_write_does_not_block_event_loop(voice_http):
    app, engine, database, _ = voice_http
    started = threading.Event()
    times = {}

    def note_write(conn, cursor, statement, params, context, executemany):
        if statement.lstrip().upper().startswith("UPDATE VOICE_READING_PROGRESS"):
            times.setdefault("write", time.monotonic())
            started.set()

    event.listen(engine, "before_cursor_execute", note_write)
    lock = sqlite3.connect(database)
    lock.execute("BEGIN IMMEDIATE")
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            request = asyncio.create_task(
                client.patch("/api/voice-reading/progress", json=_progress())
            )
            assert await asyncio.to_thread(started.wait, 5)
            health = await client.get("/health")
            elapsed = time.monotonic() - times["write"]
            result = await request
        assert health.json() == {"ok": True}
        assert elapsed < 0.5, f"SQLite blocked the ASGI event loop for {elapsed:.2f}s"
        assert result.status_code == 503
        assert result.json()["detail"]["error_code"] == "progress_store_busy"
        assert result.headers["Retry-After"] == "1"
    finally:
        lock.rollback()
        lock.close()
        event.remove(engine, "before_cursor_execute", note_write)


async def test_progress_busy_budget_then_success_after_lock_release(voice_http):
    app, engine, database, sessions = voice_http
    lock = sqlite3.connect(database)
    lock.execute("BEGIN IMMEDIATE")
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client:
            started = time.monotonic()
            failed = await client.patch("/api/voice-reading/progress", json=_progress())
            elapsed = time.monotonic() - started
            assert failed.status_code == 503
            assert elapsed < 1.5, f"progress lock wait exceeded budget: {elapsed:.2f}s"
            with sessions() as observer:
                assert observer.query(VoiceReadingProgress).one().position_ms == 0
            lock.rollback()
            saved = await client.patch(
                "/api/voice-reading/progress", json=_progress(2400)
            )
            assert saved.status_code == 200
            assert saved.json()["position_ms"] == 2400
            with engine.connect() as connection:
                assert (
                    connection.exec_driver_sql("PRAGMA busy_timeout").scalar() == 2000
                )
    finally:
        lock.rollback()
        lock.close()


async def test_progress_database_errors_are_not_all_relabelled_busy(voice_http):
    app, engine, _, _ = voice_http
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE voice_reading_progress")
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    ) as client:
        result = await client.patch("/api/voice-reading/progress", json=_progress())
    assert result.status_code == 500
