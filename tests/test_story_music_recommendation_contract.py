"""Contracts for story-aware music recommendations and premium AI queueing."""

from __future__ import annotations

from datetime import datetime

from src.database.models import Base, Game, GeneratedMusicAsset
from src.services.music_playlist_service import MusicPlaylistService
from src.services.music_service import (
    MusicBrief,
    MusicGenerationCoordinator,
    MusicProviderPolicy,
    Song,
)


def test_music_brief_from_analysis_contains_generation_and_search_intent():
    brief = MusicBrief.from_analysis(
        {
            "mood": "紧张",
            "scene_type": "夜袭",
            "environment": "古风山林",
            "pacing": "急促",
            "energy": "高",
            "instruments": ["鼓", "笛子"],
            "keywords": ["古风战斗", "山林夜雨"],
            "negative_cues": ["流行人声"],
        }
    )

    assert brief.mood == "紧张"
    assert brief.scene_type == "夜袭"
    assert brief.era_or_environment == "古风山林"
    assert brief.pacing == "急促"
    assert brief.energy == "高"
    assert brief.instruments == ["鼓", "笛子"]
    assert "古风战斗" in brief.search_queries
    assert "流行人声" in brief.negative_cues
    assert "instrumental" in brief.generation_prompt.lower()
    assert "no vocals" in brief.generation_prompt.lower()


def test_music_brief_default_is_safe_instrumental_background_music():
    brief = MusicBrief.default()

    assert brief.mood == "平静"
    assert brief.scene_type == "叙事"
    assert brief.search_queries[:3] == ["轻音乐", "背景音乐", "纯音乐"]
    assert "instrumental" in brief.generation_prompt.lower()
    assert "loop" in brief.generation_prompt.lower()


def test_provider_policy_keeps_netease_immediate_and_only_members_enqueue_ai():
    assert MusicProviderPolicy.select(
        is_member=False,
        ai_music_enabled=True,
    ) == MusicProviderPolicy(use_netease=True, enqueue_ai_generation=False)

    assert MusicProviderPolicy.select(
        is_member=True,
        ai_music_enabled=False,
    ) == MusicProviderPolicy(use_netease=True, enqueue_ai_generation=False)

    assert MusicProviderPolicy.select(
        is_member=True,
        ai_music_enabled=True,
    ) == MusicProviderPolicy(use_netease=True, enqueue_ai_generation=True)


def test_generated_track_insertion_preserves_current_and_first_upcoming_song():
    playlist = {
        "current_song": {"id": 1, "name": "Current", "source": "netease"},
        "queue": [
            {"id": 2, "name": "NearTerm", "source": "netease"},
            {"id": 3, "name": "Later", "source": "netease"},
        ],
    }
    generated = {
        "id": "asset-9",
        "name": "AI 山雨夜袭",
        "source": "ai_generated",
        "asset_id": 9,
    }

    updated = MusicPlaylistService.insert_generated_track(playlist, generated)

    assert updated["current_song"]["id"] == 1
    assert [item["id"] for item in updated["queue"]] == [2, "asset-9", 3]
    assert updated["queue"][1]["source"] == "ai_generated"


def test_ai_generation_failure_keeps_netease_songs_as_fallback():
    coordinator = MusicGenerationCoordinator()
    netease_songs = [
        Song(id=101, name="竹林", artists=["A"], album="X", duration=1000, url="u")
    ]

    result = coordinator.handle_generation_result(
        generated_track=None,
        netease_songs=netease_songs,
        error_message="provider unavailable",
    )

    assert result.songs == netease_songs
    assert result.generation_error == "provider unavailable"
    assert result.used_fallback is True


def test_generated_music_asset_metadata_round_trips(db_session):
    Base.metadata.create_all(bind=db_session.get_bind())
    game = Game(language="zh", initial_state={})
    db_session.add(game)
    db_session.commit()
    db_session.refresh(game)

    asset = GeneratedMusicAsset(
        game_id=game.game_id,
        provider="test-provider",
        model="loop-v1",
        status="ready",
        source="ai_generated",
        music_brief_json={"mood": "紧张", "scene_type": "夜袭"},
        prompt_text="instrumental ambience loop, no vocals",
        brief_hash="brief-123",
        storage_path="/tmp/music/brief-123.mp3",
        duration_ms=60000,
        loopable=True,
        created_at=datetime.utcnow(),
    )
    db_session.add(asset)
    db_session.commit()

    fetched = (
        db_session.query(GeneratedMusicAsset)
        .filter_by(brief_hash="brief-123", provider="test-provider")
        .one()
    )
    assert fetched.storage_path == "/tmp/music/brief-123.mp3"
    assert fetched.music_brief_json["mood"] == "紧张"
    assert fetched.loopable is True
