"""Contracts for story-aware music recommendations and premium AI queueing."""

from __future__ import annotations

import inspect
import logging
from datetime import datetime

import httpx
import pytest

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


@pytest.mark.asyncio
async def test_netease_search_503_degrades_without_error_traceback(caplog):
    from src.services.music_service import NeteaseMusicClient

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request)

    client = NeteaseMusicClient(base_url="http://music-api:3001")
    await client.client.aclose()
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    with caplog.at_level(logging.WARNING):
        songs = await client.search("古风 纯音乐")

    await client.close()

    assert songs == []
    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert any("unavailable" in record.message.lower() for record in caplog.records)


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


def test_generated_track_insertion_preserves_current_and_prioritizes_ai_next():
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
    assert [item["id"] for item in updated["queue"]] == ["asset-9", 2, 3]
    assert updated["queue"][0]["source"] == "ai_generated"


def test_generated_track_insertion_makes_ai_music_next_after_current():
    playlist = {
        "current_song": {"id": 1, "name": "Current", "source": "netease"},
        "queue": [
            {"id": 2, "name": "Weak Netease Next", "source": "netease"},
            {"id": 3, "name": "Later", "source": "netease"},
        ],
    }
    generated = {
        "id": "asset-10",
        "name": "AI 产品经理晨会氛围",
        "source": "ai_generated",
        "asset_id": 10,
    }

    updated = MusicPlaylistService.insert_generated_track(playlist, generated)

    assert updated["current_song"]["id"] == 1
    assert [item["id"] for item in updated["queue"]] == ["asset-10", 2, 3]
    assert updated["queue"][0]["source"] == "ai_generated"


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


def test_modern_medical_chase_suspense_avoids_love_pop_search_leaders():
    builder = MusicContextBuilder()
    brief = builder.build_brief(
        {
            "mood": "紧张",
            "scene_type": "追捕逃亡",
            "environment": "现代医院",
            "story_style": "医疗悬疑",
            "music_style": "流行",
            "pacing": "急促",
            "energy": "高",
            "instruments": ["电子合成器", "低音弦乐"],
            "keywords": ["匆匆那年", "告白气球", "喜欢你", "医疗数据造假"],
            "search_queries": ["匆匆那年", "告白气球", "喜欢你"],
            "negative_cues": ["甜蜜流行", "人声"],
        }
    )

    queries = builder.build_search_queries(brief)
    joined_queries = " | ".join(queries)
    top_queries = " | ".join(queries[:3])
    love_pop_terms = {"匆匆那年", "告白气球", "喜欢你", "恋爱", "情歌", "甜蜜"}

    assert any(
        cue in joined_queries
        for cue in ["悬疑", "追捕", "逃亡", "医疗", "紧张", "氛围", "纯音乐", "无歌词"]
    )
    assert not any(term in top_queries for term in love_pop_terms)
    assert any(cue in brief.negative_cues for cue in ["恋爱", "情歌", "歌词", "流行人声"])


def test_modern_debt_crisis_searches_financial_suspense_not_love_pop_or_type_beats():
    builder = MusicContextBuilder()
    brief = builder.build_brief(
        {
            "mood": "压抑焦虑",
            "scene_type": "债务危机",
            "environment": "2020年代苏州贸易公司",
            "story_style": "现实主义职场危机",
            "music_style": "流行",
            "pacing": "沉重",
            "energy": "中高",
            "instruments": ["低音弦乐", "电子合成器"],
            "keywords": ["等你下课", "不再联系", "双截棍 type beat", "236万担保债务"],
            "search_queries": ["等你下课", "不再联系", "双截棍 type beat"],
            "negative_cues": ["甜蜜流行", "人声"],
        }
    )

    queries = builder.build_search_queries(brief)
    joined_queries = " | ".join(queries)
    top_queries = " | ".join(queries[:3])
    blocked_terms = {"等你下课", "不再联系", "双截棍", "type beat", "恋爱", "情歌", "流行"}

    assert any(cue in joined_queries for cue in ["债务危机", "金融危机", "商务悬疑", "紧张氛围"])
    assert not any(term in top_queries for term in blocked_terms)
    assert any(cue in brief.negative_cues for cue in ["type beat", "情歌", "歌词", "流行人声"])


def test_modern_product_workplace_searches_focus_ambience_not_vocal_pop_hits():
    builder = MusicContextBuilder()
    brief = builder.build_brief(
        {
            "mood": "专注夹杂焦虑",
            "scene_type": "用户访谈复盘",
            "environment": "2020年代互联网公司会议室",
            "story_style": "现代职场产品经理成长",
            "music_style": "流行",
            "pacing": "紧凑",
            "energy": "中",
            "instruments": ["电子合成器", "钢琴"],
            "keywords": ["AI协作", "产品设计", "用户数据", "说散就散", "匆匆那年"],
            "search_queries": ["说散就散", "匆匆那年", "夜曲", "一直很安静"],
            "negative_cues": ["人声"],
        }
    )

    queries = builder.build_search_queries(brief)
    joined_queries = " | ".join(queries)
    top_queries = " | ".join(queries[:4])
    blocked_terms = {"说散就散", "匆匆那年", "夜曲", "一直很安静", "情歌", "流行"}

    assert any(cue in joined_queries for cue in ["产品经理", "科技公司", "用户访谈", "数据分析", "办公室"])
    assert any(cue in joined_queries for cue in ["纯音乐", "氛围", "轻电子", "无歌词"])
    assert "现代医院" not in joined_queries
    assert "医疗悬疑" not in joined_queries
    assert not any(term in top_queries for term in blocked_terms)
    assert any(cue in brief.negative_cues for cue in ["说散就散", "匆匆那年", "夜曲", "一直很安静", "歌词"])


@pytest.mark.asyncio
async def test_music_service_derives_workplace_filter_from_story_when_ai_analysis_is_generic(
    monkeypatch,
):
    service = MusicService()

    async def generic_analysis(_story_text, _character_settings=None):
        return {
            "mood": "平静",
            "scene_type": "叙事",
            "environment": "通用",
            "pacing": "舒缓",
            "energy": "中低",
            "instruments": ["钢琴"],
            "keywords": ["轻音乐"],
            "search_queries": ["轻音乐"],
            "negative_cues": ["人声", "歌词"],
        }

    class FakeMusicClient:
        async def search(self, keyword, limit=10):
            return [
                Song(
                    id=9001,
                    name="都选C-乔杉版",
                    artists=["乔杉"],
                    album="缝纫机乐队电影插曲",
                    duration=180000,
                ),
                Song(
                    id=9002,
                    name="办公室 轻电子 氛围",
                    artists=["Focus Lab"],
                    album="现代职场 纯音乐",
                    duration=180000,
                ),
            ]

        async def get_song_url(self, song_id):
            return f"https://music.example.com/{song_id}.mp3"

    monkeypatch.setattr(service, "_analyze_story_mood", generic_analysis)
    service.music_client = FakeMusicClient()  # type: ignore[assignment]

    recommendation = await service.analyze_story_for_music(
        """
        周一早晨，产品经理顾晨曦在互联网公司的会议室整理用户数据和白皮书。
        她要和陆昊然、陈晓雨一起准备 AI 协作工具的里程碑计划。
        """,
        character_settings={
            "world_description": "2020年代中国互联网公司，AI协作工具创业项目",
        },
    )

    song_names = [song.name for song in recommendation.songs]
    assert "办公室 轻电子 氛围" in song_names
    assert "都选C-乔杉版" not in song_names
    assert any("产品经理" in query or "办公室" in query for query in recommendation.keywords)


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
