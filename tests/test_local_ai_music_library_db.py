"""Real DB tests for local AI music library metadata."""

from datetime import datetime

import pytest

from src.database.models import Base, Game, GeneratedMusicAsset, SessionLocal, engine
from src.services.music_service import MusicBrief


class TestLocalAiMusicLibraryDB:
    @pytest.fixture(autouse=True)
    def setup_db(self):
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        yield
        Base.metadata.drop_all(engine)

    def test_library_entry_save_read_and_usage_update(self, tmp_path):
        from src.database.models import GeneratedMusicLibraryEntry
        from src.services.local_ai_music_library import LocalAiMusicLibraryService

        db = SessionLocal()
        game = Game(language="zh", initial_state={})
        requester = Game(language="zh", initial_state={})
        db.add_all([game, requester])
        db.commit()
        db.refresh(game)
        db.refresh(requester)

        audio_path = tmp_path / "stored.mp3"
        audio_path.write_bytes(b"ID3-db-library")
        asset = GeneratedMusicAsset(
            game_id=game.game_id,
            provider="minimax",
            model="music-2.6",
            status="ready",
            source="ai_generated",
            music_brief_json={
                "mood": "神秘",
                "scene_type": "城市探索",
                "environment": "未来城市雨夜",
                "pacing": "紧凑",
                "energy": "中",
                "instruments": ["合成器", "低音鼓"],
                "negative_cues": ["人声", "歌词"],
                "_generation_settings": {
                    "output_format": "url",
                    "format": "mp3",
                    "sample_rate": 44100,
                    "bitrate": 256000,
                    "is_instrumental": True,
                },
            },
            prompt_text="instrumental cyberpunk city exploration ambience, no vocals",
            brief_hash="city-explore-001",
            storage_path=str(audio_path),
            duration_ms=88000,
            loopable=True,
            created_at=datetime.utcnow(),
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)

        service = LocalAiMusicLibraryService(match_threshold=70)
        entry = service.upsert_ready_asset(db, asset)
        db.commit()
        db.refresh(entry)

        fetched = db.query(GeneratedMusicLibraryEntry).filter_by(asset_id=asset.asset_id).one()
        assert fetched.mood == "神秘"
        assert fetched.scene_type == "城市探索"
        assert fetched.environment == "未来城市雨夜"
        assert fetched.provider == "minimax"
        assert fetched.model == "music-2.6"
        assert fetched.usage_count == 0

        service.record_reuse(
            db,
            entry=fetched,
            requesting_game_id=requester.game_id,
            score=93,
            reason="scene_fit",
        )
        db.commit()
        db.refresh(fetched)

        assert fetched.usage_count == 1
        assert fetched.last_used_game_id == requester.game_id
        assert fetched.last_match_score == 93
        assert fetched.last_match_reason == "scene_fit"
        assert fetched.last_used_at is not None
        db.close()

    def test_library_lookup_uses_real_db_profile_and_provider_model_settings(
        self,
        tmp_path,
    ):
        from src.services.local_ai_music_library import LocalAiMusicLibraryService

        db = SessionLocal()
        source_game = Game(language="zh", initial_state={})
        requesting_game = Game(language="zh", initial_state={})
        db.add_all([source_game, requesting_game])
        db.commit()
        db.refresh(source_game)
        db.refresh(requesting_game)

        audio_path = tmp_path / "cross-game.mp3"
        audio_path.write_bytes(b"ID3-cross-game-library")
        settings = {
            "output_format": "url",
            "format": "mp3",
            "sample_rate": 44100,
            "bitrate": 256000,
            "is_instrumental": True,
        }
        asset = GeneratedMusicAsset(
            game_id=source_game.game_id,
            provider="minimax",
            model="music-2.6",
            status="ready",
            source="ai_generated",
            music_brief_json={
                "mood": "紧张",
                "scene_type": "现代职场危机",
                "environment": "2020年代互联网公司会议室",
                "pacing": "紧凑",
                "energy": "中高",
                "instruments": ["电子合成器", "钢琴"],
                "negative_cues": ["人声", "歌词"],
                "_generation_settings": settings,
            },
            prompt_text="tense modern workplace instrumental ambience, no vocals",
            brief_hash="cross-game-library-001",
            storage_path=str(audio_path),
            duration_ms=92000,
            loopable=True,
            created_at=datetime.utcnow(),
        )
        db.add(asset)
        db.commit()

        service = LocalAiMusicLibraryService(match_threshold=70)
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

        hit = service.find_best_match(
            db,
            requesting_game_id=requesting_game.game_id,
            brief=brief,
            provider="minimax",
            model="music-2.6",
            generation_settings=settings,
        )
        wrong_model = service.find_best_match(
            db,
            requesting_game_id=requesting_game.game_id,
            brief=brief,
            provider="minimax",
            model="music-2.5",
            generation_settings=settings,
        )
        wrong_settings = service.find_best_match(
            db,
            requesting_game_id=requesting_game.game_id,
            brief=brief,
            provider="minimax",
            model="music-2.6",
            generation_settings={**settings, "bitrate": 128000},
        )

        assert hit.hit is True
        assert hit.asset_id == asset.asset_id
        assert wrong_model.hit is False
        assert "provider_model_mismatch" in wrong_model.rejection_reasons
        assert wrong_settings.hit is False
        assert "generation_settings_mismatch" in wrong_settings.rejection_reasons
        db.close()
