from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.database.models import Base, Game
from src.services.music_playlist_service import (
    MusicPlaylistService,
    PlaylistQueuePolicy,
    get_music_playlist_service,
)


def _disposable_session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _game_id(session: Session) -> int:
    game = Game(language="zh", initial_state={})
    session.add(game)
    session.commit()
    session.refresh(game)
    return int(game.game_id)


def test_recommendation_merge_preserves_current_and_deduplicates_title_families() -> None:
    policy = PlaylistQueuePolicy()
    current = {"id": 1, "name": "绅士"}

    result = policy.merge_recommendations(
        current_song=current,
        existing_queue=[{"id": 8, "name": "旧队列"}],
        incoming_songs=[
            {"id": 1, "name": "绅士"},
            {"id": 2, "name": "绅士 (Live)"},
            {"id": 3, "name": "红尘客栈"},
            {"id": 4, "name": "红尘客栈 古风翻唱"},
            {"id": 5, "name": "办公室 轻电子 氛围"},
        ],
    )

    assert result.current_song == current
    assert [song["id"] for song in result.queue] == [3, 5]


def test_generated_track_becomes_next_without_duplicate_queue_entries() -> None:
    policy = PlaylistQueuePolicy()
    generated = {"id": "ai-generated-12", "name": "AI 紧张氛围", "source": "ai_generated"}

    updated = policy.insert_generated_track(
        {
            "current_song": {"id": 1, "name": "当前曲"},
            "queue": [generated, {"id": 2, "name": "下一曲"}],
        },
        generated,
    )
    empty_updated = policy.insert_generated_track({"current_song": None, "queue": []}, generated)

    assert updated["current_song"] == {"id": 1, "name": "当前曲"}
    assert updated["queue"] == [generated, {"id": 2, "name": "下一曲"}]
    assert empty_updated["current_song"] == generated
    assert empty_updated["queue"] == []


def test_playlist_service_persists_merge_sync_advance_and_wraparound() -> None:
    session = _disposable_session()
    try:
        game_id = _game_id(session)

        merged = MusicPlaylistService.merge_songs(
            session,
            game_id,
            [
                {"id": 1, "name": "开场"},
                {"id": 2, "name": "转折"},
                {"id": 3, "name": "尾声"},
            ],
            mood="紧张",
            keywords=["会议室", "转折"],
        )
        synced = MusicPlaylistService.sync_state(
            session,
            game_id,
            current_position_ms=45_000,
            is_playing=True,
            volume=0.8,
        )
        restored = MusicPlaylistService.get_state(session, game_id)
        first_advance = MusicPlaylistService.advance(session, game_id)
        second_advance = MusicPlaylistService.advance(session, game_id)
        wrapped = MusicPlaylistService.advance(session, game_id)

        assert merged.to_dict()["current_song"] == {"id": 1, "name": "开场"}
        assert [song["id"] for song in merged.queue] == [2, 3]
        assert merged.recommendation_mood == "紧张"
        assert synced["success"] is True
        assert synced["updated_at"] is not None
        assert restored.current_position_ms == 45_000
        assert restored.is_playing is True
        assert restored.volume == 0.8
        assert first_advance.current_song == {"id": 2, "name": "转折"}
        assert [song["id"] for song in first_advance.played_songs] == [1]
        assert second_advance.current_song == {"id": 3, "name": "尾声"}
        assert [song["id"] for song in second_advance.played_songs] == [1, 2]
        assert wrapped.current_song == {"id": 1, "name": "开场"}
        assert [song["id"] for song in wrapped.queue] == [2, 3]
        assert wrapped.played_songs == []
    finally:
        session.close()


def test_music_playlist_service_accessor_is_stable() -> None:
    assert get_music_playlist_service() is get_music_playlist_service()
