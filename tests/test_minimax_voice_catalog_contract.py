from src.services.minimax_voice_catalog import (
    canonical_voice_id,
    is_supported_voice,
    voice_options,
)


def test_voice_catalog_has_recommendations_and_language_groups() -> None:
    voices = voice_options()

    assert any(voice["recommended"] for voice in voices)
    assert {voice["language"] for voice in voices} >= {"中文", "English", "日本語", "한국어"}


def test_voice_catalog_searches_id_label_language_and_preserves_legacy_aliases() -> None:
    assert [voice["voice_id"] for voice in voice_options("captivating")] == [
        "English_CaptivatingStoryteller",
        "Spanish_CaptivatingStoryteller",
        "Portuguese_CaptivatingStoryteller",
    ]
    assert canonical_voice_id("warm_female") == "female-shaonv"
    assert is_supported_voice("warm_female") is True
    assert is_supported_voice("not-a-minimax-voice") is False
