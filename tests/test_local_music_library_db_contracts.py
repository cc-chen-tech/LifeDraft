"""Provider-free SQLite contracts for local generated music reuse."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.database.models import Base, Game, GeneratedMusicAsset, GeneratedMusicLibraryEntry
from src.services.local_ai_music_library import LocalAiMusicLibraryService
from src.services.music_service import MusicBrief


GENERATION_SETTINGS = {
    "output_format": "url",
    "format": "mp3",
    "sample_rate": 44100,
    "bitrate": 256000,
    "is_instrumental": True,
}


def _session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def _game_id(session: Session) -> int:
    game = Game(language="zh", initial_state={})
    session.add(game)
    session.commit()
    return int(game.game_id)


def _brief(*, negative_cues: list[str] | None = None) -> MusicBrief:
    return MusicBrief.from_analysis(
        {
            "mood": "紧张",
            "scene_type": "现代职场危机",
            "environment": "2020年代互联网公司会议室",
            "pacing": "紧凑",
            "energy": "中高",
            "instruments": ["电子合成器", "钢琴"],
            "negative_cues": negative_cues or ["人声", "歌词"],
        }
    )


def _asset(
    session: Session,
    *,
    game_id: int,
    storage_path: str,
    prompt_text: str = "tense workplace instrumental ambience, no vocals, no lyrics",
) -> GeneratedMusicAsset:
    asset = GeneratedMusicAsset(
        game_id=game_id,
        source="ai_generated",
        provider="minimax",
        model="music-2.6",
        status="ready",
        music_brief_json={
            "mood": "紧张",
            "scene_type": "现代职场危机",
            "environment": "2020年代互联网公司会议室",
            "pacing": "紧凑",
            "energy": "中高",
            "instruments": ["电子合成器", "钢琴"],
            "negative_cues": ["人声", "歌词"],
            "_generation_settings": GENERATION_SETTINGS,
        },
        prompt_text=prompt_text,
        brief_hash="local-library-contract",
        storage_path=storage_path,
        duration_ms=90_000,
        loopable=True,
        created_at=datetime.utcnow(),
    )
    session.add(asset)
    session.commit()
    return asset


def test_ready_asset_reindex_updates_single_library_entry(tmp_path: Path) -> None:
    session = _session()
    try:
        audio_path = tmp_path / "ready.mp3"
        audio_path.write_bytes(b"ID3-ready")
        asset = _asset(session, game_id=_game_id(session), storage_path=str(audio_path))
        service = LocalAiMusicLibraryService(match_threshold=70)

        first_entry = service.upsert_ready_asset(session, asset)
        asset.music_brief_json = {
            **asset.music_brief_json,
            "mood": "克制紧张",
            "instruments": ["钢琴"],
        }
        session.commit()
        second_entry = service.upsert_ready_asset(session, asset)
        session.commit()

        assert first_entry is not None
        assert second_entry is not None
        assert first_entry.entry_id == second_entry.entry_id
        assert session.query(GeneratedMusicLibraryEntry).count() == 1
        assert second_entry.mood == "克制紧张"
        assert second_entry.instruments_json == ["钢琴"]
        assert second_entry.usage_count == 0
    finally:
        session.close()


def test_compatible_asset_reuse_records_metadata_without_source_prompt(tmp_path: Path) -> None:
    session = _session()
    try:
        audio_path = tmp_path / "reuse.mp3"
        audio_path.write_bytes(b"ID3-reuse")
        source_game_id = _game_id(session)
        requesting_game_id = _game_id(session)
        asset = _asset(
            session,
            game_id=source_game_id,
            storage_path=str(audio_path),
            prompt_text="source game private narrative; instrumental workplace ambience",
        )
        service = LocalAiMusicLibraryService(match_threshold=70)
        decision = service.find_best_match(
            session,
            requesting_game_id=requesting_game_id,
            brief=_brief(),
            provider="minimax",
            model="music-2.6",
            generation_settings=GENERATION_SETTINGS,
        )
        track = service.reuse_match(
            session,
            decision=decision,
            requesting_game_id=requesting_game_id,
            current_brief=_brief(),
        )

        entry = session.query(GeneratedMusicLibraryEntry).filter_by(asset_id=asset.asset_id).one()
        assert decision.hit is True
        assert track["id"] == f"ai-generated-{asset.asset_id}"
        assert track["library_reused"] is True
        assert "prompt_text" not in track
        assert "private narrative" not in str(track)
        assert entry.usage_count == 1
        assert entry.last_used_game_id == requesting_game_id
        assert entry.last_match_reason == "scene_fit"
    finally:
        session.close()


def test_incompatible_settings_and_negative_cues_report_rejection_reasons(tmp_path: Path) -> None:
    session = _session()
    try:
        audio_path = tmp_path / "conflict.mp3"
        audio_path.write_bytes(b"ID3-conflict")
        asset = _asset(
            session,
            game_id=_game_id(session),
            storage_path=str(audio_path),
            prompt_text="tense workplace track with vocals",
        )
        requesting_game_id = _game_id(session)
        service = LocalAiMusicLibraryService(match_threshold=70)
        service.upsert_ready_asset(session, asset)

        settings_miss = service.find_best_match(
            session,
            requesting_game_id=requesting_game_id,
            brief=_brief(),
            provider="minimax",
            model="music-2.6",
            generation_settings={**GENERATION_SETTINGS, "bitrate": 128000},
        )
        cue_miss = service.find_best_match(
            session,
            requesting_game_id=requesting_game_id,
            brief=_brief(negative_cues=["vocals"]),
            provider="minimax",
            model="music-2.6",
            generation_settings=GENERATION_SETTINGS,
        )

        assert settings_miss.hit is False
        assert "generation_settings_mismatch" in settings_miss.rejection_reasons
        assert cue_miss.hit is False
        assert "negative_cue_conflict" in cue_miss.rejection_reasons
    finally:
        session.close()
