"""Offline contracts for explainable story-to-music scene matching quality."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from src.services.minimax_music_generation import MiniMaxMusicGenerationProvider
from src.services.music_service import MusicBrief, MusicContextBuilder, MusicResultRanker, Song


@dataclass(frozen=True)
class SceneFixture:
    story: str
    expected_scene_type: str
    expected_action: str
    expected_instrument: str
    expected_negative: str


SCENE_FIXTURES: Dict[str, SceneFixture] = {
    "modern_workplace": SceneFixture(
        story=(
            "顾晨曦在互联网公司会议室复盘用户数据，AI 协作工具突然给出相互矛盾的结论，"
            "团队在白板前陷入紧张争执。"
        ),
        expected_scene_type="现代职场冲突",
        expected_action="workplace_conflict",
        expected_instrument="电子合成器",
        expected_negative="流行人声",
    ),
    "suspense_chase": SceneFixture(
        story="雨夜码头的旧账册被风吹开，主角在汽笛声里躲避追捕，沿着仓库一路冲向江边。",
        expected_scene_type="悬疑追逐",
        expected_action="suspense_chase",
        expected_instrument="低音鼓",
        expected_negative="甜蜜流行",
    ),
    "recovery": SceneFixture(
        story="手术后的清晨，病房窗帘被轻轻拉开，主角第一次能够慢慢站起来练习行走。",
        expected_scene_type="安静康复",
        expected_action="quiet_recovery",
        expected_instrument="钢琴",
        expected_negative="强烈舞曲",
    ),
    "family_conflict": SceneFixture(
        story="晚饭桌上父亲突然提起欠款，母亲沉默地收起碗筷，兄妹之间的旧怨再次爆发。",
        expected_scene_type="家庭冲突",
        expected_action="family_conflict",
        expected_instrument="弦乐",
        expected_negative="甜蜜情歌",
    ),
    "romance": SceneFixture(
        story="黄昏的天桥上，两个人终于说出多年误会，雨后的城市灯光映在伞面。",
        expected_scene_type="克制浪漫",
        expected_action="restrained_romance",
        expected_instrument="钢琴",
        expected_negative="强节拍舞曲",
    ),
    "action_conflict": SceneFixture(
        story="仓库门被撞开，保安和追兵同时冲入，主角抓起背包穿过货架，警报声撕裂夜色。",
        expected_scene_type="动作冲突",
        expected_action="action_conflict",
        expected_instrument="打击乐",
        expected_negative="舒缓民谣",
    ),
    "reflective_ending": SceneFixture(
        story="多年以后，主角回到旧办公室门口，把第一张产品草图放进抽屉，安静地关灯离开。",
        expected_scene_type="反思结尾",
        expected_action="reflective_ending",
        expected_instrument="钢琴",
        expected_negative="搞笑梗曲",
    ),
    "generic_fallback": SceneFixture(
        story="这一天平稳地过去，角色在路上看见普通的街景，准备进入下一段生活。",
        expected_scene_type="日常过渡",
        expected_action="daily_transition",
        expected_instrument="钢琴",
        expected_negative="人声",
    ),
}


def test_scene_fit_profile_extracts_offline_fixture_contexts() -> None:
    from src.services.music_scene_matching import MusicSceneFitProfile

    for fixture in SCENE_FIXTURES.values():
        profile = MusicSceneFitProfile.from_context(
            analysis={"mood": "平静", "scene_type": "叙事", "environment": "通用"},
            story_text=fixture.story,
            character_settings={
                "era": {"era_name": "现代", "era_description": "当代都市"},
                "world_description": "现实主义 Story101",
            },
        )

        assert profile.scene_type == fixture.expected_scene_type
        assert profile.scene_action == fixture.expected_action
        assert fixture.expected_instrument in profile.instruments
        assert fixture.expected_negative in profile.negative_cues
        assert profile.selected_strategy


def test_context_builder_exposes_scene_fit_profile_without_breaking_brief() -> None:
    builder = MusicContextBuilder()
    fixture = SCENE_FIXTURES["modern_workplace"]

    profile = builder.build_scene_fit_profile(
        analysis={"mood": "平静", "scene_type": "叙事", "environment": "通用"},
        story_text=fixture.story,
        character_settings={"world_description": "现代互联网创业公司"},
    )
    brief = builder.build_brief(profile.to_analysis())
    analysis = brief.to_analysis()

    assert profile.scene_type == "现代职场冲突"
    assert brief.scene_type == "现代职场冲突"
    assert analysis["scene_fit_profile"]["scene_action"] == "workplace_conflict"
    assert analysis["scene_fit_diagnostics"]["selected_strategy"] == "modern_workplace"
    assert analysis["prompt_version"]


def test_scene_fit_scorer_ranks_compatible_candidates_and_rejects_negative_cues() -> None:
    from src.services.music_scene_matching import MusicSceneFitProfile, MusicSceneFitScorer

    profile = MusicSceneFitProfile.from_context(
        analysis={},
        story_text=SCENE_FIXTURES["modern_workplace"].story,
    )
    candidates: List[Song] = [
        Song(id=1, name="告白气球", artists=["Vocal"], album="甜蜜流行", duration=180000),
        Song(id=2, name="办公室 轻电子 氛围", artists=["Focus Lab"], album="现代职场 纯音乐", duration=180000),
        Song(id=3, name="普通钢琴背景", artists=["Piano"], album="轻音乐", duration=180000),
    ]

    decisions = [MusicSceneFitScorer().score_candidate(song, profile) for song in candidates]
    ranked = MusicSceneFitScorer().rank_candidates(candidates, profile)

    assert decisions[0].rejected is True
    assert "negative_cue_conflict" in decisions[0].reason_codes
    assert decisions[1].score > decisions[2].score
    assert [song.id for song in ranked] == [2, 3, 1]


def test_low_confidence_candidate_pool_uses_safe_background_fallbacks() -> None:
    from src.services.music_scene_matching import MusicSceneFitProfile, MusicSceneFitScorer

    profile = MusicSceneFitProfile.from_context(
        analysis={},
        story_text=SCENE_FIXTURES["suspense_chase"].story,
    )
    weak_candidates = [
        Song(id=11, name="甜蜜告白", artists=["Vocal"], album="情歌", duration=180000),
        Song(id=12, name="夏日舞曲", artists=["DJ"], album="强节拍流行", duration=180000),
        Song(id=13, name="安全背景音乐", artists=["Score Lab"], album="纯音乐 背景音乐", duration=180000),
    ]

    selected, diagnostics = MusicSceneFitScorer().select_safe_candidates(
        weak_candidates,
        profile,
        min_score=55,
    )

    assert [song.id for song in selected] == [13]
    assert diagnostics["fallback_reason"] == "low_confidence_candidate_pool"
    assert "negative_cue_conflict" in diagnostics["rejection_reasons"]


def test_versioned_minimax_prompt_builder_is_structured_bounded_and_negative() -> None:
    from src.services.music_scene_matching import (
        MUSIC_SCENE_PROMPT_VERSION,
        MiniMaxMusicPromptBuilder,
        MusicSceneFitProfile,
    )

    story = SCENE_FIXTURES["suspense_chase"].story * 20
    profile = MusicSceneFitProfile.from_context(analysis={}, story_text=story)
    brief = MusicBrief.from_analysis(profile.to_analysis())

    built = MiniMaxMusicPromptBuilder().build(
        story_text=story,
        brief=brief,
        profile=profile,
        max_chars=360,
    )

    assert built.prompt_version == MUSIC_SCENE_PROMPT_VERSION
    assert len(built.prompt) <= 360
    assert "Instrumental narrative gameplay background" in built.prompt
    assert "Scene action: suspense_chase" in built.prompt
    assert "No vocals" in built.prompt
    assert "No lyrics" in built.prompt
    assert story not in built.prompt


def test_minimax_generation_brief_uses_prompt_version_and_diagnostics() -> None:
    from src.services.music_scene_matching import MUSIC_SCENE_PROMPT_VERSION

    story = SCENE_FIXTURES["family_conflict"].story * 12
    brief = MiniMaxMusicGenerationProvider.build_brief_from_story(
        story_text=story,
        analysis={"mood": "平静", "scene_type": "叙事", "environment": "通用"},
        max_prompt_chars=420,
    )
    analysis = brief.to_analysis()

    assert brief.prompt_version == MUSIC_SCENE_PROMPT_VERSION
    assert analysis["prompt_version"] == MUSIC_SCENE_PROMPT_VERSION
    assert analysis["scene_fit_profile"]["scene_action"] == "family_conflict"
    assert analysis["scene_fit_diagnostics"]["selected_strategy"] == "family_conflict"
    assert len(brief.generation_prompt) <= 420
    assert story not in brief.generation_prompt


def test_music_result_ranker_emits_fit_diagnostics_without_field_breakage() -> None:
    brief = MusicBrief.from_analysis(
        {
            **SCENE_FIXTURES["recovery"].__dict__,
            "mood": "温柔",
            "environment": "现代病房清晨",
            "search_queries": ["康复 病房 钢琴"],
        }
    )
    songs = [
        Song(id=31, name="夜店快歌", artists=["DJ"], album="强烈舞曲", duration=180000),
        Song(id=32, name="病房清晨钢琴", artists=["Piano Lab"], album="安静康复 纯音乐", duration=180000),
    ]

    ranked = MusicResultRanker().rank(songs, brief)
    diagnostics = MusicResultRanker().diagnose(songs, brief)
    analysis = brief.to_analysis()

    assert ranked[0].id == 32
    assert diagnostics["fit_score_by_id"]["32"] >= 55
    assert "negative_cue_conflict" in diagnostics["rejection_reasons_by_id"]["31"]
    assert analysis["scene_fit_profile"]["scene_action"] == "quiet_recovery"
    assert "mood" in analysis
    assert "scene_type" in analysis


def test_instrumental_prompt_rejects_anime_theme_song_candidates() -> None:
    """Instrumental-only story background should reject anime theme-song results."""
    brief = MusicBrief.from_analysis(
        {
            "mood": "专注",
            "scene_type": "现代职场",
            "environment": "办公室",
            "instruments": ["电子合成器"],
            "search_queries": ["办公室 轻电子 氛围"],
            "negative_cues": [],
            "generation_prompt": "instrumental ambience loop for focused workplace scene",
        }
    )
    songs = [
        Song(id=41, name="打上花火", artists=["DAOKO"], album="动画电影主题曲", duration=180000),
        Song(id=42, name="办公室 轻电子 氛围", artists=["Focus Lab"], album="现代职场 纯音乐", duration=180000),
    ]

    filtered = MusicResultRanker().filter_and_dedupe(songs, brief)

    assert [song.id for song in filtered] == [42]
