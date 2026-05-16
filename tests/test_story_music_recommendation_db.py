"""Real DB save-read tests for generated music assets."""

from datetime import datetime

import pytest

from src.database.models import (Base, Game, GeneratedMusicAsset, SessionLocal,
                                 engine)


class TestGeneratedMusicAssetDB:
    @pytest.fixture(autouse=True)
    def setup_db(self):
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        yield
        Base.metadata.drop_all(engine)

    def test_generated_music_asset_save_read_by_brief_provider_hash(self):
        db = SessionLocal()
        game = Game(language="zh", initial_state={})
        db.add(game)
        db.commit()
        db.refresh(game)

        asset = GeneratedMusicAsset(
            game_id=game.game_id,
            provider="test-provider",
            model="loop-v1",
            status="ready",
            source="ai_generated",
            music_brief_json={
                "mood": "神秘",
                "scene_type": "探索",
                "search_queries": ["神秘 古风 轻音乐"],
            },
            prompt_text="instrumental ambience loop, no vocals",
            brief_hash="brief-provider-001",
            storage_path="/tmp/generated/brief-provider-001.mp3",
            duration_ms=90000,
            loopable=True,
            created_at=datetime.utcnow(),
        )
        db.add(asset)
        db.commit()
        db.close()

        verify_db = SessionLocal()
        fetched = (
            verify_db.query(GeneratedMusicAsset)
            .filter_by(brief_hash="brief-provider-001", provider="test-provider")
            .one()
        )

        assert fetched.game_id == game.game_id
        assert fetched.status == "ready"
        assert fetched.source == "ai_generated"
        assert fetched.music_brief_json["scene_type"] == "探索"
        assert fetched.storage_path.endswith(".mp3")
        assert fetched.duration_ms == 90000
        assert fetched.loopable is True
        verify_db.close()
