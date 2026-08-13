"""Provider-free eligibility contracts for reusable local AI music."""

from types import SimpleNamespace

from src.services.local_ai_music_library import (
    LocalAiMusicLibraryService,
    _asset_audio_exists,
    _brief_dict,
    _casefold_all,
    _conflicts_with_negative_cues,
    _field_score,
    _generation_settings,
    _profile_list,
    _profile_text,
    _truthy,
)
from src.services.music_service import MusicBrief


def _brief() -> MusicBrief:
    return MusicBrief.from_analysis(
        {
            "mood": "紧张",
            "scene_type": "现代职场危机",
            "environment": "互联网公司会议室",
            "pacing": "紧凑",
            "energy": "中高",
            "instruments": ["钢琴", "电子合成器"],
            "negative_cues": ["vocals", "lyrics", "人声", "歌词"],
        }
    )


def test_music_metadata_helpers_normalize_values_without_database_state():
    metadata = {
        "mood": "  紧张  ",
        "instruments": ["钢琴", None, 7],
        "_generation_settings": {"format": "mp3"},
    }

    assert _truthy(" YES ") is True
    assert _truthy("off") is False
    assert _brief_dict(metadata) == metadata
    assert _brief_dict([metadata]) == {}
    assert _generation_settings(metadata) == {"format": "mp3"}
    assert _profile_text(metadata, "mood", "平静") == "紧张"
    assert _profile_list(metadata, "instruments", ["弦乐"]) == ["钢琴", "7"]
    assert _casefold_all([" Piano ", "", "钢琴"]) == ["piano", "钢琴"]
    assert _field_score("紧张", "紧张", exact=18, partial=8) == 18
    assert _field_score("职场", "现代职场危机", exact=18, partial=8) == 8


def test_compatible_music_metadata_receives_bounded_scene_fit_score():
    entry = SimpleNamespace(
        asset_id=7,
        mood="紧张",
        scene_type="现代职场危机",
        environment="互联网公司会议室",
        pacing="紧凑",
        energy="中高",
        instruments_json=["钢琴", "电子合成器"],
        duration_ms=90_000,
        loopable=True,
    )

    score = LocalAiMusicLibraryService(match_threshold=70).score_entry(entry, _brief())

    assert 70 <= score <= 100


def test_negative_cue_filter_honors_explicit_negation_and_conflicts():
    entry = SimpleNamespace(
        mood="紧张",
        scene_type="现代职场危机",
        environment="办公室",
        instruments_json=["钢琴"],
    )
    conflicting_asset = SimpleNamespace(prompt_text="tense pop track with vocals and lyrics")
    safe_asset = SimpleNamespace(prompt_text="instrumental ambience, no vocals, no lyrics")

    assert _conflicts_with_negative_cues(entry, conflicting_asset, _brief()) is True
    assert _conflicts_with_negative_cues(entry, safe_asset, _brief()) is False


def test_audio_eligibility_accepts_remote_or_existing_local_assets(tmp_path):
    local_audio = tmp_path / "ambient.mp3"
    local_audio.write_bytes(b"ID3")

    assert _asset_audio_exists("https://cdn.example.test/ambient.mp3") is True
    assert _asset_audio_exists("/api/music/generated/12") is True
    assert _asset_audio_exists(str(local_audio)) is True
    assert _asset_audio_exists(str(tmp_path / "missing.mp3")) is False
