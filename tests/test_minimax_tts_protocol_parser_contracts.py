"""Provider-free MiniMax TTS protocol parser contracts."""

import tarfile
from io import BytesIO
from pathlib import Path

import pytest
from httpx import Response

from src.services.minimax_config import MiniMaxConfig
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
from src.services.story_tts_provider import ParagraphCue

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


def test_tts_chapter_bundle_without_subtitle_falls_back_to_proportional_cues() -> None:
    """Multi-paragraph chapters without SRT subtitles still emit valid cues.

    The MiniMax ``t2a_async_v2`` endpoint historically ships the synthesized
    audio inside a tar archive together with ``.titles``/``.extra`` JSON
    metadata.  ``_extract_synthesis_bundle`` only inspects the ``.srt`` member,
    so ``subtitle_text`` ends up ``None`` for those responses.  ``_paragraph_cues``
    must not raise on the multi-paragraph chapter in that case; instead it must
    fall back to a proportional split so gapless playback keeps working.

    Regression: previously ``_paragraph_cues`` raised
    ``ValueError("MiniMax chapter bundle did not include paragraph subtitles")``
    for any chapter with two or more paragraphs, which surfaced as
    ``TTSProviderUnavailableError("MiniMax TTS generation failed")`` and marked
    every multi-paragraph voice job as ``failed`` in production.
    """
    from src.services.minimax_story_tts_provider import MiniMaxTTSProvider

    provider = MiniMaxTTSProvider(
        config=MiniMaxConfig.from_env(
            env={"MINIMAX_API_KEY": "configured"},
            voice_asset_dir=_make_asset_dir(),
        )
    )
    # Three paragraphs of distinct weights so a regression that drops a
    # paragraph, returns a uniform split, or inverts the proportions is
    # caught immediately.
    paragraphs = [
        "雾气比昨日更浓，汴州城南的街巷在灰白中只露出模糊的轮廓。",
        "狄仁杰从赵府外的巷道离开后，并未径直去李记药铺，而是先拐入一条窄巷。",
        "他需要理清头绪。",
    ]
    cues = provider._paragraph_cues(
        {"paragraphs": paragraphs},
        subtitle_text=None,
        duration_ms=6_000,
    )

    assert len(cues) == len(paragraphs)
    assert [cue.paragraph_index for cue in cues] == [0, 1, 2]
    assert cues[0].start_ms == 0
    assert cues[-1].end_ms == 6_000
    widths = [cue.end_ms - cue.start_ms for cue in cues]
    # Paragraph 1 (index 1) carries the most non-whitespace characters so its
    # audio slice must be the widest; paragraph 2 (index 2) is the shortest
    # and must therefore own the narrowest slice.  Paragraph 0 sits between
    # the two.  This pins the proportional behaviour against accidental
    # regressions to a uniform split or to silent drops of trailing
    # paragraphs.
    assert widths[1] > widths[0] > widths[2]
    assert sum(widths) == 6_000


def test_tts_single_paragraph_without_subtitle_emits_full_duration_cue() -> None:
    """A one-paragraph chapter must yield a single cue covering the whole audio."""
    from src.services.minimax_story_tts_provider import MiniMaxTTSProvider

    provider = MiniMaxTTSProvider(
        config=MiniMaxConfig.from_env(
            env={"MINIMAX_API_KEY": "configured"},
            voice_asset_dir=_make_asset_dir(),
        )
    )

    cues = provider._paragraph_cues(
        {"paragraphs": ["唯一段落。"]},
        subtitle_text=None,
        duration_ms=4_200,
    )

    assert cues == (
        ParagraphCue(paragraph_index=0, start_ms=0, end_ms=4_200),
    )


def test_tts_synthesis_succeeds_when_subtitle_text_is_missing(tmp_path) -> None:
    """End-to-end: synthesize() must succeed when no subtitle text is returned.

    Reproduces the production failure observed on Aug 17 where every
    multi-paragraph voice job landed in the ``failed`` terminal state because
    the MiniMax API stopped returning an SRT member inside the audio tar.
    The stub client writes a tar containing the audio plus ``.titles`` and
    ``.extra`` metadata (matching the modern MiniMax response shape) and
    ``subtitle_text`` ends up ``None``.  The audio validation step is
    monkey-patched so the test does not depend on synthesizing a real MP3.
    """

    class TarWithoutSubtitleClient:
        """Simulates the modern MiniMax response: audio + .titles + .extra."""

        def synthesize_to_file(self, payload, output_path, on_progress=None):
            if on_progress is not None:
                on_progress()
            archive = _tar_members(
                {
                    "result/chapter.mp3": b"ID3-audio-bytes",
                    "result/chapter.titles": b'[{"text": "x", "time_begin": 0, "time_end": 100}]',
                    "result/chapter.extra": b'{"balance": 0}',
                }
            )
            output_path.write_bytes(archive)
            return None

    from src.services.minimax_story_tts_provider import (
        MiniMaxTTSProvider,
        _validated_audio_duration_ms,
    )
    import src.services.minimax_story_tts_provider as provider_module

    asset_dir = tmp_path / "voice"
    provider = MiniMaxTTSProvider(
        config=MiniMaxConfig.from_env(
            env={"MINIMAX_API_KEY": "configured"},
            voice_asset_dir=asset_dir,
        ),
        client=TarWithoutSubtitleClient(),
    )

    # The MiniMax tar carries the audio as one of its members and the tar
    # itself does not validate as an MP3.  Bypass the upstream validation so
    # the regression test focuses on the paragraph cue behaviour that
    # actually broke in production.
    original_validate = _validated_audio_duration_ms

    def fake_validate(audio_path, extension):
        del audio_path
        assert extension == "mp3"
        return 4_500

    provider_module._validated_audio_duration_ms = fake_validate
    try:
        speech = provider.synthesize(
            {
                "text_hash": "no-subtitles-chapter",
                "text": (
                    "雾气比昨日更浓，汴州城南的街巷在灰白中只露出模糊的轮廓。\n\n"
                    "狄仁杰从赵府外的巷道离开后，并未径直去李记药铺。"
                ),
                "paragraphs": [
                    "雾气比昨日更浓，汴州城南的街巷在灰白中只露出模糊的轮廓。",
                    "狄仁杰从赵府外的巷道离开后，并未径直去李记药铺。",
                ],
            },
            "warm_female",
            1.0,
        )
    finally:
        provider_module._validated_audio_duration_ms = original_validate

    assert speech.playback_mode == "audio"
    assert speech.duration_ms == 4_500
    assert len(speech.paragraph_cues) == 2
    assert speech.paragraph_cues[0].start_ms == 0
    assert speech.paragraph_cues[-1].end_ms == 4_500


def _make_asset_dir() -> "Path":
    """Return a unique, empty temp directory used by the regression tests.

    Importing ``tmp_path`` from pytest fixtures would require rewriting the
    tests as functions that take the fixture as an argument; using a helper
    keeps the contract tests self-contained while still exercising the same
    filesystem boundaries the real provider relies on.
    """
    import tempfile

    return Path(tempfile.mkdtemp(prefix="minimax-tts-paragraph-cues-"))
