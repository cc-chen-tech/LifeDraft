"""Real DB integration tests for MiniMax generated audio metadata."""

from __future__ import annotations

from uuid import uuid4

from src.database.models import Game, GeneratedMusicAsset, GeneratedVoiceAsset, SessionLocal, User, init_db
from src.services.music_playlist_service import MusicPlaylistService
from src.services.story_voice_repository import StoryVoiceReadingRepository


def test_minimax_voice_asset_reuse_includes_provider_model_and_format() -> None:
    init_db()
    session = SessionLocal()
    try:
        user = User(
            private_id=f"priv_{uuid4().hex[:16]}",
            public_id=f"pub_{uuid4().hex[:6]}",
            display_name="MiniMax Voice",
        )
        session.add(user)
        session.flush()
        repository = StoryVoiceReadingRepository(session)
        text_hash = f"minimax-story-{uuid4().hex}"
        context = {
            "source_type": "current_story",
            "game_id": 7001,
            "week": 1,
            "round_number": 1,
            "stage": "event",
            "attempt_id": "minimax",
            "text_hash": text_hash,
            "text": "真正的 MiniMax 朗读资产应该被按 provider/model 复用。",
        }
        asset = repository.create_asset(
            user_id=int(user.user_id),
            context=context,
            voice_id="warm_female",
            speed=1.0,
            provider="minimax",
            model="speech-02-turbo",
            storage_path="/api/voice-reading/audio/minimax-story-hash.mp3",
            duration_ms=4200,
            status="ready",
        )
        session.commit()

        loaded = repository.find_ready_asset(
            text_hash=text_hash,
            voice_id="warm_female",
            speed=1.0,
            provider="minimax",
            model="speech-02-turbo",
        )
        wrong_model = repository.find_ready_asset(
            text_hash=text_hash,
            voice_id="warm_female",
            speed=1.0,
            provider="minimax",
            model="speech-02-hd",
        )

        assert loaded is not None
        assert loaded.asset_id == asset.asset_id
        assert loaded.storage_path.endswith(".mp3")
        assert wrong_model is None
        assert (
            session.query(GeneratedVoiceAsset)
            .filter_by(provider="minimax", text_hash=text_hash)
            .count()
            == 1
        )
    finally:
        session.rollback()
        session.close()


def test_minimax_music_asset_save_read_and_reuse_uses_real_database() -> None:
    from src.services.minimax_music_generation import GeneratedMusicAssetRepository

    init_db()
    session = SessionLocal()
    try:
        game = Game(language="zh", initial_state={"name": "MiniMax Music"})
        session.add(game)
        session.commit()
        session.refresh(game)

        repository = GeneratedMusicAssetRepository(session)
        brief_hash = f"brief-minimax-{uuid4().hex}"
        asset = repository.create_ready_asset(
            game_id=int(game.game_id),
            provider="minimax",
            model="music-2.6",
            music_brief={
                "mood": "紧张",
                "scene_type": "雨夜追逐",
                "energy": "高",
                "instruments": ["鼓", "大提琴"],
            },
            prompt_text="instrumental rainy chase, no vocals",
            brief_hash=brief_hash,
            storage_path=f"/api/music/generated/{brief_hash}.mp3",
            duration_ms=64000,
            generation_settings={"output_format": "url", "format": "mp3"},
        )
        session.commit()

        loaded = repository.find_ready_asset(
            game_id=int(game.game_id),
            provider="minimax",
            model="music-2.6",
            brief_hash=brief_hash,
            generation_settings={"output_format": "url", "format": "mp3"},
        )
        wrong_settings = repository.find_ready_asset(
            game_id=int(game.game_id),
            provider="minimax",
            model="music-2.6",
            brief_hash=brief_hash,
            generation_settings={"output_format": "hex", "format": "mp3"},
        )

        assert loaded is not None
        assert loaded.asset_id == asset.asset_id
        assert loaded.source == "ai_generated"
        assert loaded.storage_path.endswith(".mp3")
        assert loaded.music_brief_json["scene_type"] == "雨夜追逐"
        assert wrong_settings is None
        assert (
            session.query(GeneratedMusicAsset)
            .filter_by(provider="minimax", brief_hash=brief_hash)
            .count()
            == 1
        )
    finally:
        session.rollback()
        session.close()


def test_ready_minimax_music_asset_inserts_into_future_playlist_slot() -> None:
    from src.services.minimax_music_generation import MiniMaxMusicGenerationProvider

    init_db()
    session = SessionLocal()
    try:
        game = Game(language="zh", initial_state={"name": "MiniMax Queue"})
        session.add(game)
        session.commit()
        session.refresh(game)

        playlist = MusicPlaylistService.merge_songs(
            db=session,
            game_id=int(game.game_id),
            songs=[
                {"id": 101, "name": "网易云 当前曲", "artists": ["N"], "album": "A", "duration": 1000, "source": "netease"},
                {"id": 102, "name": "网易云 下一曲", "artists": ["N"], "album": "A", "duration": 1000, "source": "netease"},
                {"id": 103, "name": "网易云 后续曲", "artists": ["N"], "album": "A", "duration": 1000, "source": "netease"},
            ],
        )
        assert playlist.current_song is not None
        assert playlist.current_song["id"] == 101

        generated_track = MiniMaxMusicGenerationProvider.to_playlist_track(
            asset_id=77,
            title="AI MiniMax 雨夜追逐",
            audio_url="/api/music/generated/brief-77.wav",
            duration_ms=60000,
            provider="minimax",
            model="music-2.6",
            brief_hash="brief-77",
        )
        updated = MusicPlaylistService.insert_generated_track_for_game(
            db=session,
            game_id=int(game.game_id),
            generated_track=generated_track,
        )

        reloaded = MusicPlaylistService.get_state(session, int(game.game_id))

        assert updated.current_song is not None
        assert updated.current_song["id"] == 101
        assert [item["id"] for item in updated.queue] == [102, "ai-generated-77", 103]
        assert reloaded.queue[1]["source"] == "ai_generated"
        assert reloaded.queue[1]["provider"] == "minimax"
    finally:
        session.rollback()
        session.close()


def test_story_music_generation_service_saves_reuses_and_returns_playlist_track(tmp_path) -> None:
    from src.services.minimax_config import MiniMaxConfig
    from src.services.minimax_music_generation import (
        MiniMaxMusicGenerationProvider,
        StoryMusicGenerationService,
    )

    init_db()
    session = SessionLocal()
    try:
        game = Game(language="zh", initial_state={"name": "MiniMax Story Music"})
        session.add(game)
        session.commit()
        session.refresh(game)

        provider = MiniMaxMusicGenerationProvider(
            config=MiniMaxConfig.from_env(
                env={
                    "MINIMAX_API_KEY": "test-key",
                    "MINIMAX_E2E_LOCAL_AUDIO": "1",
                    "MINIMAX_MUSIC_MODEL": "music-2.6",
                },
                voice_asset_dir=tmp_path / "voice",
                music_asset_dir=tmp_path / "music",
            )
        )
        service = StoryMusicGenerationService(provider=provider)

        track = service.generate_ready_track(
            db=session,
            game_id=int(game.game_id),
            story_text="雨夜码头的旧账册被风吹开，追逐从仓库一路延伸到江边。",
            analysis={"mood": "紧张", "scene_type": "雨夜追逐", "environment": "民国码头"},
        )
        reused = service.generate_ready_track(
            db=session,
            game_id=int(game.game_id),
            story_text="雨夜码头的旧账册被风吹开，追逐从仓库一路延伸到江边。",
            analysis={"mood": "紧张", "scene_type": "雨夜追逐", "environment": "民国码头"},
        )

        assert track["source"] == "ai_generated"
        assert track["provider"] == "minimax"
        assert track["model"] == "music-2.6"
        assert track["url"].startswith("/api/music/generated/")
        assert track["url"].endswith(".wav")
        assert reused["asset_id"] == track["asset_id"]
        assert (
            session.query(GeneratedMusicAsset)
            .filter_by(provider="minimax", game_id=int(game.game_id))
            .count()
            == 1
        )
    finally:
        session.rollback()
        session.close()
