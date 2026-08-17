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

pytestmark = [pytest.mark.unit]



def _tar_bytes(member_name: str, data: bytes) -> bytes:
    stream = BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        member = tarfile.TarInfo(member_name)
        member.size = len(data)
        archive.addfile(member, BytesIO(data))
    return stream.getvalue()


def _tar_members(members: dict[str, bytes]) -> bytes:
    stream = BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        for member_name, data in members.items():
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


def test_tts_chapter_bundle_maps_sentence_subtitles_to_paragraph_cues() -> None:
    from src.services.minimax_story_tts_provider import (
        _align_paragraph_cues,
        _extract_synthesis_bundle,
        _parse_srt_cues,
    )

    archive = _tar_members(
        {
            "result/chapter.mp3": b"ID3-chapter-audio",
            "result/chapter.srt": (
                "1\n00:00:00,000 --> 00:00:01,200\n第一段第一句。\n\n"
                "2\n00:00:01,250 --> 00:00:02,400\n第一段第二句。\n\n"
                "3\n00:00:02,500 --> 00:00:04,000\n第二段第一句。\n"
            ).encode("utf-8"),
            "result/chapter.json": b'{"audio_length": 4500}',
        }
    )

    bundle = _extract_synthesis_bundle(archive, "application/x-tar")
    subtitle_cues = _parse_srt_cues(bundle.subtitle_text or "")
    paragraph_cues = _align_paragraph_cues(
        ["第一段第一句。第一段第二句。", "第二段第一句。"],
        subtitle_cues,
        audio_duration_ms=4_500,
    )

    assert bundle.audio_bytes == b"ID3-chapter-audio"
    assert [(cue.paragraph_index, cue.start_ms, cue.end_ms) for cue in paragraph_cues] == [
        (0, 0, 2_500),
        (1, 2_500, 4_500),
    ]

    octet_stream_bundle = _extract_synthesis_bundle(
        archive,
        "application/octet-stream",
    )
    assert octet_stream_bundle.audio_bytes == b"ID3-chapter-audio"
    assert octet_stream_bundle.subtitle_text == bundle.subtitle_text


def test_tts_chapter_alignment_rejects_subtitles_that_do_not_match_story_order() -> None:
    from src.services.minimax_story_tts_provider import (
        _align_paragraph_cues,
        _parse_srt_cues,
    )

    subtitles = _parse_srt_cues(
        "1\n00:00:00,000 --> 00:00:01,000\n完全不同的文本。\n"
    )

    with pytest.raises(ValueError, match="align MiniMax subtitles"):
        _align_paragraph_cues(["原始故事段落。"], subtitles, audio_duration_ms=1_200)


def test_tts_subtitle_parser_rejects_overlapping_cues() -> None:
    from src.services.minimax_story_tts_provider import _parse_srt_cues

    subtitles = (
        "1\n00:00:00,000 --> 00:00:02,000\n第一句。\n\n"
        "2\n00:00:01,500 --> 00:00:03,000\n第二句。\n"
    )

    with pytest.raises(ValueError, match="invalid timestamps"):
        _parse_srt_cues(subtitles)
