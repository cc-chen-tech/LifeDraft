"""Contracts for 2026-06-08 story quality, music quality, and currency regressions."""

from src.game.game_initializer import GameInitializer
from src.game.state import PlayerState
from src.game.world_model import WorldModel
from src.services.music_service import MusicBrief, Song, _matches_negative_music_cue


def _modern_product_manager_settings() -> dict:
    return {
        "era": {"era_description": "2026 年现代互联网职场"},
        "occupation": {"occupation": "产品经理", "employer": "AI 协作平台"},
        "wealth": {
            "wealth": 50000,
            "currency": "¥",
            "currency_name": "元",
            "wealth_description": "个人储蓄和家庭支持合计五万元。",
        },
        "relationships": {
            "key_people": [
                {
                    "name": "陆昊然",
                    "role": "导师",
                    "relationship": "产品导师",
                    "relationship_desc": "资深产品负责人，指导主角建立职业判断。",
                },
                {
                    "name": "陈晓雨",
                    "role": "闺蜜",
                    "relationship": "大学好友",
                    "relationship_desc": "主角最信任的朋友，擅长数据分析。",
                },
                {
                    "name": "林一凡",
                    "role": "同期",
                    "relationship": "同期产品经理",
                    "relationship_desc": "同一届入职的同事，与主角互相竞争也互相扶持。",
                },
            ]
        },
    }


def test_required_cast_constraints_include_all_preset_people() -> None:
    from src.game.relationship_authority import build_required_cast_constraints

    text = build_required_cast_constraints(_modern_product_manager_settings(), language="zh")

    assert "【预设人物关系" in text
    assert "陆昊然" in text and "导师" in text
    assert "陈晓雨" in text and "闺蜜" in text
    assert "林一凡" in text and "同期" in text
    assert "不得改名" in text or "不得替换" in text


def test_world_model_constraints_include_required_cast_from_character_settings() -> None:
    player_state = PlayerState(
        player_name="测试小可",
        age=24,
        week=1,
        character_settings=_modern_product_manager_settings(),
    )

    text = WorldModel.from_player_state(player_state).build_constraints_text("zh")

    assert "陆昊然" in text
    assert "陈晓雨" in text
    assert "林一凡" in text
    assert "预设人物" in text


def test_cast_coverage_validator_rejects_invented_friend_substitute() -> None:
    from src.game.relationship_authority import validate_required_cast_coverage

    result = validate_required_cast_coverage(
        "苏婉清把一份投资协议推到你面前，像大学闺蜜一样提醒你别错过这次机会。",
        _modern_product_manager_settings(),
        language="zh",
        minimum_required_mentions=1,
    )

    assert not result.passed
    assert "陈晓雨" in " ".join(result.issues)
    assert "苏婉清" in " ".join(result.issues)


def test_canonicalize_key_person_candidate_preserves_preset_friend_name() -> None:
    from src.game.relationship_authority import canonicalize_key_person_candidate

    candidate = {
        "name": "苏婉清",
        "role": "闺蜜",
        "relationship_desc": "大学好友，擅长数据分析。",
    }

    canonical = canonicalize_key_person_candidate(candidate, _modern_product_manager_settings())

    assert canonical["name"] == "陈晓雨"
    assert canonical["role"] == "闺蜜"


def test_minimax_music_negative_cue_matching_normalizes_variants() -> None:
    song = Song(
        id=8801,
        name="断 了 的 弦 - Live Remix",
        artists=["热门翻唱"],
        album="流行人声精选",
        duration=180000,
    )

    assert _matches_negative_music_cue(song, ["断了的弦", "流行人声"])


def test_music_candidate_dedupe_collapses_same_song_under_different_ids() -> None:
    from src.services.music_service import dedupe_music_candidates

    songs = [
        Song(id=1, name="断了的弦", artists=["周杰伦"], album="A", duration=1000),
        Song(id=2, name="断了的弦 - Live", artists=["周杰伦"], album="B", duration=1000),
        Song(id=3, name="现代职场低调配乐", artists=["Score Lab"], album="影视配乐", duration=1000),
    ]

    deduped = dedupe_music_candidates(songs)

    assert [song.id for song in deduped] == [1, 3]


def test_game_initializer_uses_configured_wealth_amount() -> None:
    game_loop, _ = GameInitializer(game_db=None, language="zh").initialize_game_from_settings(
        character_settings=_modern_product_manager_settings(),
        player_name="测试小可",
        life_vision="成为可靠的产品经理",
    )

    state = game_loop.get_state()
    assert state is not None
    assert state.wealth == 50000


def test_music_brief_workplace_negative_cues_include_reported_bad_matches() -> None:
    brief = MusicBrief.from_analysis(
        {
            "mood": "紧张",
            "scene_type": "产品经理成长与应收账款危机",
            "environment": "现代互联网公司",
            "search_queries": ["产品经理 工作配乐", "等你下课", "小幸运 type beat"],
            "negative_cues": ["等你下课", "小幸运", "断了的弦", "type beat"],
            "instruments": ["低调电子", "钢琴"],
        }
    )

    assert "等你下课" in brief.negative_cues
    assert "小幸运" in brief.negative_cues
    assert "断了的弦" in brief.negative_cues
    assert "type beat" in brief.negative_cues
    assert all("等你下课" not in query for query in brief.search_queries)
    assert all("小幸运" not in query for query in brief.search_queries)
