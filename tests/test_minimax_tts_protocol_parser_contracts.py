"""Provider-free MiniMax TTS protocol parser contracts."""

import tarfile
from io import BytesIO

import pytest
from httpx import Response

from src.services.minimax_story_tts_provider import (
    _ensure_http_url,
    _extract_audio_file_bytes,
    _extract_audio_hex,
    _extract_file_download_url,
    _is_done_message,
    _json_dumps,
    _map_voice_id,
    _raise_for_base_resp,
    _safe_token,
)


def _tar_bytes(member_name: str, data: bytes) -> bytes:
    stream = BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        member = tarfile.TarInfo(member_name)
        member.size = len(data)
        archive.addfile(member, BytesIO(data))
    return stream.getvalue()


def test_tts_protocol_helpers_accept_nested_audio_and_completion_shapes() -> None:
    assert _map_voice_id("calm_male") == "male-qn-qingse"
    assert _map_voice_id("unlisted") == "female-shaonv"
    assert _safe_token(" story / hash ") == "story-hash"
    assert _json_dumps({"b": "林岚", "a": 1}) == '{"a": 1, "b": "林岚"}'
    assert _extract_audio_hex({"data": {"audio_hex": "0aff"}}) == "0aff"
    assert _extract_audio_hex({"audio": ""}) is None
    assert _is_done_message({"data": {"event": "finished"}}) is True
    assert _is_done_message({"status": "running"}) is False


def test_tts_protocol_rejects_provider_error_and_parses_nested_download_url() -> None:
    with pytest.raises(RuntimeError, match="1008 quota exhausted"):
        _raise_for_base_resp({"base_resp": {"status_code": 1008, "status_msg": "quota exhausted"}})

    response = Response(
        200,
        headers={"content-type": "application/json"},
        json={"data": {"file": {"download_url": "https://audio.example/story.mp3"}}},
    )
    assert _extract_file_download_url(response) == "https://audio.example/story.mp3"
    assert _extract_file_download_url(Response(200, content=b"audio/mpeg")) is None

    _ensure_http_url("https://audio.example/story.mp3")
    with pytest.raises(ValueError, match="http or https"):
        _ensure_http_url("file:///tmp/story.mp3")


def test_tts_tar_download_extracts_audio_member_and_preserves_non_audio_archive() -> None:
    audio_tar = _tar_bytes("nested/story.mp3", b"ID3-audio-bytes")
    text_tar = _tar_bytes("metadata.txt", b"not audio")

    assert _extract_audio_file_bytes(audio_tar, "application/x-tar") == b"ID3-audio-bytes"
    assert _extract_audio_file_bytes(text_tar, "application/x-tar") == text_tar
    assert _extract_audio_file_bytes(b"plain-mp3", "audio/mpeg") == b"plain-mp3"
