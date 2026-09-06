from src.services import minimax_voice_catalog
from src.services.minimax_voice_catalog import canonical_voice_id, is_supported_voice, voice_options


def test_story_voice_catalog_only_exposes_chinese_display_names() -> None:
    voices = voice_options()

    assert any(voice["recommended"] for voice in voices)
    assert {voice["language"] for voice in voices} == {"普通话", "粤语"}
    assert any(voice["label"] == "沉稳高管" for voice in voices)
    assert any(voice["label"] == "温润男声" for voice in voices)
    assert all("_" not in voice["label"] for voice in voices)
    assert all(not any(character.isascii() and character.isalpha() for character in voice["label"]) for voice in voices)
    assert all(voice["voice_id"] not in voice["label"] for voice in voices)


def test_voice_catalog_searches_chinese_names_without_returning_other_languages() -> None:
    assert [voice["voice_id"] for voice in voice_options("温润")] == [
        "Chinese (Mandarin)_Gentleman",
        "Chinese (Mandarin)_Gentle_Youth",
    ]
    assert voice_options("captivating") == []


def test_story_voice_support_keeps_legacy_aliases_but_rejects_non_chinese_voices() -> None:
    assert canonical_voice_id("warm_female") == "female-shaonv"
    assert is_supported_voice("warm_female") is True
    story_voice_support = getattr(minimax_voice_catalog, "is_story_voice_supported", None)
    assert callable(story_voice_support)
    assert story_voice_support("warm_female") is True
    assert story_voice_support("English_CalmWoman") is False
    assert is_supported_voice("not-a-minimax-voice") is False
