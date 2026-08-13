"""Provider-free MiniMax music protocol parser contracts."""

from src.services.minimax_music_generation import (
    _compact_story_summary,
    _coerce_positive_int,
    _extract_audio_bytes,
    _extract_audio_url,
    _extract_duration_ms,
    _extract_provider_error,
    _is_audio_url,
)


def test_music_protocol_parses_nested_url_bytes_and_duration() -> None:
    payload = {
        "data": {
            "audio": {"url": " https://audio.example/generated.mp3 "},
            "audio_hex": "49 44 33",
            "duration": "2410.8",
        }
    }

    assert _extract_audio_url(payload) == " https://audio.example/generated.mp3 "
    assert _extract_audio_bytes(payload) == b"ID3"
    assert _extract_duration_ms(payload) == 2410
    assert _is_audio_url("http://audio.example/clip.mp3") is True
    assert _is_audio_url("file:///tmp/clip.mp3") is False


def test_music_protocol_skips_invalid_audio_values_and_formats_provider_error() -> None:
    assert _extract_audio_url({"audio_url": "ftp://audio.example/clip.mp3"}) is None
    assert _extract_audio_bytes({"audio_hex": "not hex", "data": {"audio": ""}}) is None
    assert _extract_duration_ms({"duration": False, "data": {"duration_ms": "0"}}) is None
    assert _extract_provider_error({"base_resp": {"status_code": 0}}) is None
    assert _extract_provider_error(
        {"base_resp": {"status_code": 429, "status_msg": " rate limited "}}
    ) == "MiniMax music generation failed (status_code=429; rate limited)"


def test_music_summary_normalizes_and_bounds_story_context() -> None:
    assert _compact_story_summary("  雨夜\n  工作室   停电  ", 40) == "雨夜 工作室 停电"
    assert _compact_story_summary("one two three four", 8) == "one two."
    assert _coerce_positive_int(12) == 12
    assert _coerce_positive_int(3.8) == 3
    assert _coerce_positive_int(" 5.5 ") == 5
    assert _coerce_positive_int(True) is None
    assert _coerce_positive_int("invalid") is None
