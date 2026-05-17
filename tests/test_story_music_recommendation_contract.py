"""Contracts for story-aware music recommendations and premium AI queueing."""

from __future__ import annotations

import inspect
from datetime import datetime

from src.database.models import Base, Game, GeneratedMusicAsset
from src.services.music_playlist_service import MusicPlaylistService, PlaylistQueuePolicy
from src.services.music_service import (
    MusicBrief,
    MusicContextBuilder,
    MusicGenerationCoordinator,
    MusicGenerationJob,
    MusicProviderPolicy,
    MusicRecommendation,
    MusicResultRanker,
    MusicService,
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
    netease_songs = [Song(id=101, name="竹林", artists=["A"], album="X", duration=1000, url="u")]

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


def test_context_builder_maps_analysis_to_brief_and_search_queries():
    builder = MusicContextBuilder()
    brief = builder.build_brief(
        {
            "mood": "紧张",
            "scene_type": "雨夜追逐",
            "environment": "民国码头",
            "pacing": "急促",
            "energy": "高",
            "instruments": ["鼓", "大提琴"],
            "search_queries": ["民国 雨夜 追逐 鼓点"],
            "negative_cues": ["甜蜜流行", "人声"],
        }
    )
    queries = builder.build_search_queries(brief)
    joined_queries = " | ".join(queries)

    assert brief.scene_type == "雨夜追逐"
    assert brief.era_or_environment == "民国码头"
    assert "instrumental" in brief.generation_prompt.lower()
    assert "no vocals" in brief.generation_prompt.lower()
    assert queries[0] == "民国 雨夜 追逐 鼓点"
    assert "民国码头" in joined_queries
    assert "雨夜追逐" in joined_queries
    assert "急促" in joined_queries or "高" in joined_queries
    assert "鼓" in joined_queries or "大提琴" in joined_queries
    assert "甜蜜流行" not in joined_queries
    assert "人声" not in joined_queries


def test_analyze_story_mood_uses_full_story_text_without_service_truncation():
    source = inspect.getsource(MusicService._analyze_story_mood)

    assert "story_text[:" not in source
    assert "story_preview" not in source
    assert "{story_text}" in source


def test_context_builder_creates_tight_multidimensional_search_pairs():
    builder = MusicContextBuilder()
    brief = builder.build_brief(
        {
            "mood": "紧张",
            "scene_type": "夜袭",
            "environment": "古风",
            "pacing": "急促",
            "energy": "高",
            "instruments": ["鼓", "笛子"],
            "search_queries": ["夜袭战场"],
            "negative_cues": ["流行人声"],
        }
    )

    queries = builder.build_search_queries(brief)

    assert "紧张 夜袭" in queries
    assert "古风 鼓" in queries
    assert all("流行人声" not in query for query in queries)
    assert queries != ["紧张"]


def test_music_result_ranker_prefers_brief_matches_and_penalizes_negative_cues():
    brief = MusicBrief(
        mood="紧张",
        scene_type="雨夜追逐",
        era_or_environment="民国码头",
        pacing="急促",
        energy="高",
        instruments=["鼓", "大提琴"],
        search_queries=["民国 雨夜 追逐 鼓点"],
        negative_cues=["甜蜜", "人声"],
        generation_prompt="instrumental ambience loop, no vocals",
    )
    songs = [
        Song(id=1, name="甜蜜人声情歌", artists=["Vocal"], album="流行", duration=1000),
        Song(id=2, name="民国码头雨夜追逐", artists=["鼓点"], album="影视配乐", duration=1000),
        Song(id=3, name="普通轻音乐", artists=["Piano"], album="背景音乐", duration=1000),
    ]

    ranked = MusicResultRanker().rank(songs, brief)

    assert [song.id for song in ranked] == [2, 3, 1]


def test_music_result_ranker_preserves_order_when_only_weak_terms_match():
    brief = MusicBrief(
        mood="紧张",
        scene_type="夜袭",
        era_or_environment="古风",
        pacing="急促",
        energy="高",
        instruments=["鼓"],
        search_queries=["紧张 夜袭", "古风 鼓"],
        negative_cues=["流行人声"],
        generation_prompt="instrumental ambience loop, no vocals",
    )
    songs = [
        Song(id=1, name="海风入梦", artists=["Piano"], album="背景音乐", duration=1000),
        Song(id=2, name="高楼夜色", artists=["Piano"], album="背景音乐", duration=1000),
        Song(id=3, name="远山回声", artists=["Piano"], album="背景音乐", duration=1000),
    ]

    ranked = MusicResultRanker().rank(songs, brief)

    assert [song.id for song in ranked] == [1, 2, 3]


def test_music_recommendation_keeps_legacy_fields_and_exposes_music_brief():
    from src.api.routers.music import MusicRecommendationResponse, SongResponse

    brief = MusicBrief.default()
    recommendation = MusicRecommendation(
        keywords=brief.search_queries,
        mood=brief.mood,
        scene_type=brief.scene_type,
        songs=[Song(id=11, name="背景曲", artists=["A"], album="B", duration=1000)],
        environment=brief.era_or_environment,
        music_brief=brief,
    )
    response = MusicRecommendationResponse(
        keywords=recommendation.keywords,
        mood=recommendation.mood,
        scene_type=recommendation.scene_type,
        environment=recommendation.environment,
        music_brief=recommendation.music_brief.to_analysis(),
        songs=[
            SongResponse(
                id=11,
                name="背景曲",
                artists=["A"],
                album="B",
                duration=1000,
                url="https://music.example/11.mp3",
                source="netease",
            )
        ],
    )

    assert response.keywords == ["轻音乐", "背景音乐", "纯音乐"]
    assert response.environment == "通用"
    assert response.music_brief["energy"] == "中低"
    assert response.songs[0].source == "netease"


def test_playlist_queue_policy_preserves_current_and_replaces_upcoming_on_merge():
    policy = PlaylistQueuePolicy()
    current = {"id": 1, "name": "Current", "source": "netease"}
    near_term = {"id": 2, "name": "NearTerm", "source": "netease"}
    incoming = [
        {"id": 1, "name": "Current from backend", "source": "netease"},
        {"id": 3, "name": "Fresh", "source": "netease"},
        {"id": "asset-9", "name": "AI 雨夜码头", "source": "ai_generated"},
    ]

    merged = policy.merge_recommendations(current, [near_term], incoming)

    assert merged.current_song == current
    assert [item["id"] for item in merged.queue] == [3, "asset-9"]
    assert merged.queue[1]["source"] == "ai_generated"


def test_generation_job_interface_defaults_to_pending_background_ai_music():
    brief = MusicBrief.default()
    job = MusicGenerationJob.create(
        game_id=42,
        brief=brief,
        provider="test-provider",
        model="loop-v1",
    )

    assert job.game_id == 42
    assert job.status == "pending"
    assert job.source == "ai_generated"
    assert job.prompt_text == brief.generation_prompt
    assert job.brief_hash
    assert job.model == "loop-v1"
