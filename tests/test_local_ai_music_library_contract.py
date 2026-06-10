"""Contracts for reusable local AI-generated music library behavior."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.database.models import Base, Game, GeneratedMusicAsset, SessionLocal, init_db
from src.services.minimax_config import MiniMaxConfig
from src.services.minimax_music_generation import (
    GeneratedMusicFile,
    MiniMaxMusicGenerationProvider,
    StoryMusicGenerationService,
)
from src.services.music_playlist_service import MusicPlaylistService
from src.services.music_service import MusicBrief


GENERATION_SETTINGS: Dict[str, Any] = {
    "output_format": "url",
    "format": "mp3",
    "sample_rate": 44100,
    "bitrate": 256000,
    "is_instrumental": True,
}


def _create_game(db_session) -> Game:
    game = Game(language="zh", initial_state={})
    db_session.add(game)
    db_session.commit()
    db_session.refresh(game)
    return game


def _write_audio(tmp_path: Path, name: str = "local-ai.mp3") -> str:
    audio_path = tmp_path / name
    audio_path.write_bytes(b"ID3-local-ai-music")
    return str(audio_path)


def _create_asset(
    db_session,
    *,
    game_id: int,
    storage_path: str,
    status: str = "ready",
    provider: str = "minimax",
    model: str = "music-2.6",
    mood: str = "紧张",
    scene_type: str = "现代职场危机",
    environment: str = "2020年代互联网公司会议室",
    pacing: str = "紧凑",
    energy: str = "中高",
    instruments: Optional[list[str]] = None,
    negative_cues: Optional[list[str]] = None,
    prompt_text: str = "tense modern workplace instrumental ambience, no vocals, no lyrics",
    settings: Optional[Dict[str, Any]] = None,
) -> GeneratedMusicAsset:
    brief = {
        "mood": mood,
        "scene_type": scene_type,
        "environment": environment,
        "era_or_environment": environment,
        "pacing": pacing,
        "energy": energy,
        "instruments": instruments or ["电子合成器", "钢琴"],
        "search_queries": ["办公室 轻电子 氛围"],
        "negative_cues": negative_cues or ["人声", "歌词"],
        "_generation_settings": settings or GENERATION_SETTINGS,
    }
    asset = GeneratedMusicAsset(
        game_id=game_id,
        source="ai_generated",
        provider=provider,
        model=model,
        status=status,
        music_brief_json=brief,
        prompt_text=prompt_text,
        brief_hash=f"brief-{game_id}-{scene_type}-{status}",
        storage_path=storage_path,
        duration_ms=90000,
        loopable=True,
        created_at=datetime.utcnow(),
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


def test_local_library_indexes_ready_assets_and_excludes_non_ready(db_session, tmp_path):
    from src.database.models import GeneratedMusicLibraryEntry
    from src.services.local_ai_music_library import LocalAiMusicLibraryService

    Base.metadata.create_all(bind=db_session.get_bind())
    source_game = _create_game(db_session)
    target_game = _create_game(db_session)
    ready_asset = _create_asset(
        db_session,
        game_id=source_game.game_id,
        storage_path=_write_audio(tmp_path, "ready.mp3"),
    )
    _create_asset(
        db_session,
        game_id=source_game.game_id,
        status="pending",
        storage_path=_write_audio(tmp_path, "pending.mp3"),
    )

    service = LocalAiMusicLibraryService(match_threshold=70)
    indexed_count = service.backfill_ready_assets(db_session)
    brief = MusicBrief.from_analysis(
        {
            "mood": "紧张",
            "scene_type": "现代职场危机",
            "environment": "2020年代互联网公司会议室",
            "pacing": "紧凑",
            "energy": "中高",
            "instruments": ["电子合成器", "钢琴"],
            "negative_cues": ["人声", "歌词"],
        }
    )

    decision = service.find_best_match(
        db_session,
        requesting_game_id=target_game.game_id,
        brief=brief,
        provider="minimax",
        model="music-2.6",
        generation_settings=GENERATION_SETTINGS,
    )

    assert indexed_count == 1
    assert decision.hit is True
    assert decision.asset_id == ready_asset.asset_id
    entry = (
        db_session.query(GeneratedMusicLibraryEntry)
        .filter_by(asset_id=ready_asset.asset_id)
        .one()
    )
    assert entry.scene_type == "现代职场危机"
    assert entry.mood == "紧张"
    assert entry.energy == "中高"
    assert entry.usage_count == 0


def test_local_library_reuse_updates_usage_and_privacy_safe_track(
    db_session,
    tmp_path,
):
    from src.database.models import GeneratedMusicLibraryEntry
    from src.services.local_ai_music_library import LocalAiMusicLibraryService

    Base.metadata.create_all(bind=db_session.get_bind())
    source_game = _create_game(db_session)
    target_game = _create_game(db_session)
    asset = _create_asset(
        db_session,
        game_id=source_game.game_id,
        storage_path=_write_audio(tmp_path, "privacy.mp3"),
        prompt_text=(
            "Story summary: source game secret boardroom betrayal. "
            "Create tense modern workplace instrumental ambience."
        ),
    )
    service = LocalAiMusicLibraryService(match_threshold=70)
    service.upsert_ready_asset(db_session, asset)
    brief = MusicBrief.from_analysis(
        {
            "mood": "紧张",
            "scene_type": "现代职场危机",
            "environment": "2020年代互联网公司会议室",
            "pacing": "紧凑",
            "energy": "中高",
            "instruments": ["电子合成器", "钢琴"],
            "negative_cues": ["人声", "歌词"],
        }
    )
    decision = service.find_best_match(
        db_session,
        requesting_game_id=target_game.game_id,
        brief=brief,
        provider="minimax",
        model="music-2.6",
        generation_settings=GENERATION_SETTINGS,
    )

    track = service.reuse_match(
        db_session,
        decision=decision,
        requesting_game_id=target_game.game_id,
        current_brief=brief,
    )

    assert track["id"] == f"ai-generated-{asset.asset_id}"
    assert track["source"] == "ai_generated"
    assert track["library_reused"] is True
    assert track["name"] == "AI MiniMax 现代职场危机"
    assert "source_game" not in track
    assert "source_game_id" not in track
    assert "prompt_text" not in track
    assert "source game secret" not in str(track)
    entry = (
        db_session.query(GeneratedMusicLibraryEntry)
        .filter_by(asset_id=asset.asset_id)
        .one()
    )
    assert entry.usage_count == 1
    assert entry.last_used_game_id == target_game.game_id
    assert entry.last_match_score == decision.score


def test_local_library_reuse_titles_generic_narrative_scene_from_context(
    db_session,
    tmp_path,
):
    from src.services.local_ai_music_library import (
        LocalAiMusicLibraryService,
        LocalAiMusicMatchDecision,
    )

    Base.metadata.create_all(bind=db_session.get_bind())
    source_game = _create_game(db_session)
    target_game = _create_game(db_session)
    asset = _create_asset(
        db_session,
        game_id=source_game.game_id,
        storage_path=_write_audio(tmp_path, "generic-scene.mp3"),
        mood="紧张",
        scene_type="叙事",
        environment="现代医院",
        prompt_text="tense modern hospital instrumental ambience, no vocals",
    )
    service = LocalAiMusicLibraryService(match_threshold=70)
    entry = service.upsert_ready_asset(db_session, asset)
    assert entry is not None
    brief = MusicBrief.from_analysis(
        {
            "mood": "紧张",
            "scene_type": "叙事",
            "environment": "现代医院",
            "pacing": "紧凑",
            "energy": "中高",
            "instruments": ["电子合成器", "钢琴"],
            "negative_cues": ["人声", "歌词"],
        }
    )

    track = service.reuse_match(
        db_session,
        decision=LocalAiMusicMatchDecision(
            hit=True,
            asset_id=asset.asset_id,
            entry_id=entry.entry_id,
            score=88,
            reason="scene_fit",
            entry=entry,
        ),
        requesting_game_id=target_game.game_id,
        current_brief=brief,
    )

    assert track["name"] == "AI MiniMax 现代医院 紧张"
    assert track["name"] != "AI MiniMax 叙事"


def test_local_library_rejects_conflicts_low_score_stale_audio_and_provider_mismatch(
    db_session,
    tmp_path,
):
    from src.services.local_ai_music_library import LocalAiMusicLibraryService

    Base.metadata.create_all(bind=db_session.get_bind())
    source_game = _create_game(db_session)
    target_game = _create_game(db_session)
    _create_asset(
        db_session,
        game_id=source_game.game_id,
        storage_path=_write_audio(tmp_path, "vocal.mp3"),
        prompt_text="romantic pop song with vocals and lyrics",
    )
    _create_asset(
        db_session,
        game_id=source_game.game_id,
        storage_path=_write_audio(tmp_path, "distant.mp3"),
        mood="神秘",
        scene_type="古风山林探索",
        environment="古风山林",
        pacing="舒缓",
        energy="低",
        instruments=["笛子"],
    )
    _create_asset(
        db_session,
        game_id=source_game.game_id,
        storage_path=str(tmp_path / "missing.mp3"),
    )
    _create_asset(
        db_session,
        game_id=source_game.game_id,
        storage_path=_write_audio(tmp_path, "other-provider.mp3"),
        provider="other-provider",
    )
    service = LocalAiMusicLibraryService(match_threshold=70)
    service.backfill_ready_assets(db_session)
    brief = MusicBrief.from_analysis(
        {
            "mood": "紧张",
            "scene_type": "现代职场危机",
            "environment": "2020年代互联网公司会议室",
            "pacing": "紧凑",
            "energy": "中高",
            "instruments": ["电子合成器", "钢琴"],
            "negative_cues": ["vocals", "lyrics", "人声", "歌词"],
        }
    )

    decision = service.find_best_match(
        db_session,
        requesting_game_id=target_game.game_id,
        brief=brief,
        provider="minimax",
        model="music-2.6",
        generation_settings=GENERATION_SETTINGS,
    )

    assert decision.hit is False
    assert "negative_cue_conflict" in decision.rejection_reasons
    assert "low_scene_fit" in decision.rejection_reasons
    assert "stale_audio" in decision.rejection_reasons
    assert "provider_model_mismatch" in decision.rejection_reasons


def test_story_generation_reuses_local_library_before_provider_call(
    db_session,
    tmp_path,
):
    Base.metadata.create_all(bind=db_session.get_bind())
    source_game = _create_game(db_session)
    target_game = _create_game(db_session)
    asset = _create_asset(
        db_session,
        game_id=source_game.game_id,
        storage_path=_write_audio(tmp_path, "reuse-before-provider.mp3"),
    )

    class ExplodingProvider:
        provider = "minimax"
        model = "music-2.6"
        config = MiniMaxConfig.from_env(
            {
                "MINIMAX_API_KEY": "test-key",
                "MINIMAX_MUSIC_PROMPT_MAX_CHARS": "900",
                "STORY_MUSIC_AI_GENERATION_ENABLED": "true",
            }
        )
        build_brief_from_story = staticmethod(
            MiniMaxMusicGenerationProvider.build_brief_from_story
        )
        to_playlist_track = staticmethod(MiniMaxMusicGenerationProvider.to_playlist_track)

        def generate_to_asset(self, *_args, **_kwargs):
            raise AssertionError("MiniMax provider should not be called on library hit")

    track = StoryMusicGenerationService(provider=ExplodingProvider()).generate_ready_track(
        db=db_session,
        game_id=target_game.game_id,
        story_text="顾晨曦在互联网公司会议室复盘用户数据，AI 协作工具出现关键危机。",
        analysis={
            "mood": "紧张",
            "scene_type": "现代职场危机",
            "environment": "2020年代互联网公司会议室",
            "pacing": "紧凑",
            "energy": "中高",
            "instruments": ["电子合成器", "钢琴"],
            "negative_cues": ["人声", "歌词"],
        },
    )

    assert track["asset_id"] == asset.asset_id
    assert track["library_reused"] is True
    updated = MusicPlaylistService.insert_generated_track(
        {
            "current_song": {"id": 1, "name": "NetEase current", "source": "netease"},
            "queue": [{"id": 2, "name": "NetEase next", "source": "netease"}],
        },
        track,
    )
    assert updated["current_song"]["id"] == 1
    assert [item["id"] for item in updated["queue"]] == [
        f"ai-generated-{asset.asset_id}",
        2,
    ]


def test_story_generation_falls_back_to_provider_when_library_lookup_fails(
    db_session,
    tmp_path,
    monkeypatch,
):
    from src.services.local_ai_music_library import LocalAiMusicLibraryService

    Base.metadata.create_all(bind=db_session.get_bind())
    target_game = _create_game(db_session)
    generated_path = Path(_write_audio(tmp_path, "provider-fallback.mp3"))

    def broken_lookup(self, *_args, **_kwargs):
        raise TimeoutError("local library lookup timed out")

    monkeypatch.setattr(LocalAiMusicLibraryService, "find_best_match", broken_lookup)

    class ProviderFallback:
        provider = "minimax"
        model = "music-2.6"
        config = MiniMaxConfig.from_env(
            {
                "MINIMAX_API_KEY": "test-key",
                "MINIMAX_MUSIC_PROMPT_MAX_CHARS": "900",
                "STORY_MUSIC_AI_GENERATION_ENABLED": "true",
            }
        )
        build_brief_from_story = staticmethod(
            MiniMaxMusicGenerationProvider.build_brief_from_story
        )
        to_playlist_track = staticmethod(MiniMaxMusicGenerationProvider.to_playlist_track)

        def generate_to_asset(self, _request, brief_hash=None):
            return GeneratedMusicFile(
                storage_path=str(generated_path),
                local_path=generated_path,
                duration_ms=91000,
                provider="minimax",
                model="music-2.6",
                media_type="audio/mpeg",
            )

    track = StoryMusicGenerationService(provider=ProviderFallback()).generate_ready_track(
        db=db_session,
        game_id=target_game.game_id,
        story_text="顾晨曦在会议室准备 AI 产品复盘，气氛紧张。",
        analysis={
            "mood": "紧张",
            "scene_type": "现代职场危机",
            "environment": "2020年代互联网公司会议室",
            "pacing": "紧凑",
            "energy": "中高",
            "instruments": ["电子合成器", "钢琴"],
            "negative_cues": ["人声", "歌词"],
        },
    )

    assert track["source"] == "ai_generated"
    assert track.get("library_reused") is not True
    assert track["url"] == str(generated_path)


def test_local_library_reuse_scope_can_limit_reuse_to_same_game(
    db_session,
    tmp_path,
):
    from src.services.local_ai_music_library import LocalAiMusicLibraryService

    Base.metadata.create_all(bind=db_session.get_bind())
    source_game = _create_game(db_session)
    target_game = _create_game(db_session)
    asset = _create_asset(
        db_session,
        game_id=source_game.game_id,
        storage_path=_write_audio(tmp_path, "scope.mp3"),
    )
    brief = MusicBrief.from_analysis(
        {
            "mood": "紧张",
            "scene_type": "现代职场危机",
            "environment": "2020年代互联网公司会议室",
            "pacing": "紧凑",
            "energy": "中高",
            "instruments": ["电子合成器", "钢琴"],
            "negative_cues": ["人声", "歌词"],
        }
    )

    global_decision = LocalAiMusicLibraryService(
        match_threshold=70,
        reuse_scope="global",
    ).find_best_match(
        db_session,
        requesting_game_id=target_game.game_id,
        brief=brief,
        provider="minimax",
        model="music-2.6",
        generation_settings=GENERATION_SETTINGS,
    )
    same_game_decision = LocalAiMusicLibraryService(
        match_threshold=70,
        reuse_scope="game",
    ).find_best_match(
        db_session,
        requesting_game_id=source_game.game_id,
        brief=brief,
        provider="minimax",
        model="music-2.6",
        generation_settings=GENERATION_SETTINGS,
    )
    cross_game_decision = LocalAiMusicLibraryService(
        match_threshold=70,
        reuse_scope="game",
    ).find_best_match(
        db_session,
        requesting_game_id=target_game.game_id,
        brief=brief,
        provider="minimax",
        model="music-2.6",
        generation_settings=GENERATION_SETTINGS,
    )

    assert global_decision.hit is True
    assert global_decision.asset_id == asset.asset_id
    assert same_game_decision.hit is True
    assert same_game_decision.asset_id == asset.asset_id
    assert cross_game_decision.hit is False
    assert "reuse_scope_mismatch" in cross_game_decision.rejection_reasons


def test_local_library_lookup_timeout_returns_miss(
    db_session,
    tmp_path,
):
    from src.services.local_ai_music_library import LocalAiMusicLibraryService

    Base.metadata.create_all(bind=db_session.get_bind())
    source_game = _create_game(db_session)
    target_game = _create_game(db_session)
    _create_asset(
        db_session,
        game_id=source_game.game_id,
        storage_path=_write_audio(tmp_path, "timeout.mp3"),
    )
    brief = MusicBrief.from_analysis(
        {
            "mood": "紧张",
            "scene_type": "现代职场危机",
            "environment": "2020年代互联网公司会议室",
            "pacing": "紧凑",
            "energy": "中高",
            "instruments": ["电子合成器", "钢琴"],
            "negative_cues": ["人声", "歌词"],
        }
    )

    decision = LocalAiMusicLibraryService(
        match_threshold=70,
        lookup_timeout_seconds=0.0,
    ).find_best_match(
        db_session,
        requesting_game_id=target_game.game_id,
        brief=brief,
        provider="minimax",
        model="music-2.6",
        generation_settings=GENERATION_SETTINGS,
    )

    assert decision.hit is False
    assert "lookup_timeout" in decision.rejection_reasons


def test_music_generate_and_async_routes_reuse_local_library_tracks(
    tmp_path,
):
    from src.api.routers.music import router

    init_db()
    db = SessionLocal()
    try:
        source_game = _create_game(db)
        sync_game = _create_game(db)
        async_game = _create_game(db)
        asset = _create_asset(
            db,
            game_id=source_game.game_id,
            storage_path=_write_audio(tmp_path, "route-reuse.mp3"),
        )
        source_asset_id = int(asset.asset_id)
        sync_game_id = int(sync_game.game_id)
        async_game_id = int(async_game.game_id)
    finally:
        db.close()

    previous_env = {
        name: os.environ.get(name)
        for name in [
            "MINIMAX_API_KEY",
            "STORY_MUSIC_LOCAL_LIBRARY_ENABLED",
            "STORY_MUSIC_LOCAL_LIBRARY_REUSE_SCOPE",
            "STORY_MUSIC_LOCAL_LIBRARY_MATCH_THRESHOLD",
        ]
    }
    os.environ["MINIMAX_API_KEY"] = "test-key"
    os.environ["STORY_MUSIC_LOCAL_LIBRARY_ENABLED"] = "true"
    os.environ["STORY_MUSIC_LOCAL_LIBRARY_REUSE_SCOPE"] = "global"
    os.environ["STORY_MUSIC_LOCAL_LIBRARY_MATCH_THRESHOLD"] = "70"
    try:
        app = FastAPI()
        app.include_router(router, prefix="/api")
        client = TestClient(app)
        analysis = {
            "mood": "紧张",
            "scene_type": "现代职场危机",
            "environment": "2020年代互联网公司会议室",
            "pacing": "紧凑",
            "energy": "中高",
            "instruments": ["电子合成器", "钢琴"],
            "negative_cues": ["人声", "歌词"],
        }

        sync_response = client.post(
            "/api/music/generate",
            json={
                "game_id": sync_game_id,
                "story_text": "顾晨曦在互联网公司会议室复盘用户数据，团队气氛陡然紧张。",
                "analysis": analysis,
            },
        )
        playlist_response = client.put(
            f"/api/music/playlist/{async_game_id}",
            json={
                "songs": [
                    {
                        "id": 501,
                        "name": "网易云 当前曲",
                        "artists": ["N"],
                        "album": "A",
                        "duration": 1000,
                        "url": "https://example.com/current.mp3",
                        "source": "netease",
                    },
                    {
                        "id": 502,
                        "name": "网易云 下一曲",
                        "artists": ["N"],
                        "album": "A",
                        "duration": 1000,
                        "url": "https://example.com/next.mp3",
                        "source": "netease",
                    },
                ]
            },
        )
        assert playlist_response.status_code == 200
        async_response = client.post(
            "/api/music/generate-async",
            json={
                "game_id": async_game_id,
                "story_text": "会议室里的 AI 产品复盘进入关键冲突，节奏紧凑。",
                "analysis": analysis,
            },
        )
        async_playlist = client.get(f"/api/music/playlist/{async_game_id}")
    finally:
        for name, value in previous_env.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    assert sync_response.status_code == 202
    sync_body = sync_response.json()
    assert sync_body["status"] == "queued"
    assert sync_body["game_id"] == sync_game_id
    sync_playlist_response = client.get(f"/api/music/playlist/{sync_game_id}")
    assert sync_playlist_response.status_code == 200
    sync_playlist = sync_playlist_response.json()
    assert sync_playlist["current_song"]["asset_id"] == source_asset_id
    assert sync_playlist["current_song"]["library_reused"] is True
    assert sync_playlist["current_song"]["match_reason"] == "scene_fit"
    assert "source_game_id" not in sync_playlist["current_song"]
    assert "prompt_text" not in sync_playlist["current_song"]

    assert async_response.status_code == 202
    assert async_playlist.status_code == 200
    playlist = async_playlist.json()
    assert playlist["current_song"]["id"] == 501
    assert playlist["queue"][0]["asset_id"] == source_asset_id
    assert playlist["queue"][0]["library_reused"] is True
    assert [item["id"] for item in playlist["queue"]] == [
        f"ai-generated-{source_asset_id}",
        502,
    ]
