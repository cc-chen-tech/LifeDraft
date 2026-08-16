"""MiniMax story text-to-speech provider."""

from __future__ import annotations

import hashlib
import json
import os
import re
import struct
import tarfile
import tempfile
import time
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, cast
from urllib.parse import urlparse

import httpx
import mutagen
from mutagen.mp3 import MP3
from mutagen.wave import WAVE

from src.database.models import VOICE_ASSET_VERSION
from src.services.minimax_config import MiniMaxConfig, build_minimax_config
from src.services.story_tts_provider import (
    GeneratedSpeech,
    ParagraphCue,
    ProgressCallback,
    StoryTTSProviderMetadata,
    TTSProviderUnavailableError,
    build_deterministic_wav,
)


@dataclass(frozen=True)
class SubtitleCue:
    start_ms: int
    end_ms: int
    text: str


@dataclass(frozen=True)
class SynthesisBundle:
    audio_bytes: bytes
    subtitle_text: Optional[str] = None


class MiniMaxWebSocketTTSClient:
    """Small boundary for MiniMax WebSocket TTS synthesis."""

    def __init__(self, config: MiniMaxConfig) -> None:
        self.config = config

    def synthesize_to_file(
        self,
        payload: Mapping[str, Any],
        output_path: Path,
        on_progress: Optional[ProgressCallback] = None,
    ) -> Optional[str]:
        """Write synthesized audio to `output_path`.

        The real network implementation is intentionally isolated here so provider
        contracts and DB tests can exercise all higher layers without credentials.
        """
        _report_progress(on_progress)
        if os.getenv("MINIMAX_E2E_LOCAL_AUDIO", "0") == "1":
            text = str(payload.get("text") or "minimax-local-audio")
            text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            output_path.write_bytes(build_deterministic_wav(text_hash, "warm_female"))
            return None
        from websockets.sync.client import connect

        audio_chunks: list[bytes] = []
        with connect(
            self.config.tts_websocket_url,
            additional_headers={"Authorization": f"Bearer {self.config.api_key or ''}"},
            open_timeout=self.config.request_timeout_seconds,
            close_timeout=self.config.request_timeout_seconds,
        ) as websocket:
            websocket.send(_json_dumps(payload))
            for message in websocket:
                payload_obj = json.loads(str(message))
                audio_hex = _extract_audio_hex(payload_obj)
                if audio_hex:
                    audio_chunks.append(bytes.fromhex(audio_hex))
                if _is_done_message(payload_obj):
                    break
        if not audio_chunks:
            raise RuntimeError("MiniMax WebSocket synthesis returned no audio")
        output_path.write_bytes(b"".join(audio_chunks))
        _report_progress(on_progress)
        return None


class MiniMaxAsyncTTSClient:
    """Boundary for MiniMax async TTS task creation, polling, and download."""

    def __init__(self, config: MiniMaxConfig) -> None:
        self.config = config

    def synthesize_to_file(
        self,
        payload: Mapping[str, Any],
        output_path: Path,
        on_progress: Optional[ProgressCallback] = None,
    ) -> Optional[str]:
        _report_progress(on_progress)
        if self.config.local_audio_enabled:
            text = str(payload.get("text") or "minimax-local-audio")
            text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            output_path.write_bytes(build_deterministic_wav(text_hash, "warm_female"))
            _report_progress(on_progress)
            return None

        create_response = self._post_json(self.config.tts_async_create_url, payload)
        _report_progress(on_progress)
        _raise_for_base_resp(create_response)
        task_id = create_response.get("task_id")
        if task_id is None:
            raise RuntimeError("MiniMax async TTS create response did not include task_id")
        file_id = create_response.get("file_id")

        query_response: Mapping[str, Any] = create_response
        # P0-稳定性修复：
        # 1) 轮询以墙钟 deadline 为准。旧实现是"次数上限"（max(12, timeout/0.5) 次），
        #    而每次 HTTP 调用自身又带 request_timeout_seconds 超时，
        #    最坏总时长可达 次数上限 × 单次超时（如 360×180s），远超配置意图。
        # 2) 指数退避并封顶，避免高频轮询与重试雪崩。
        # 3) 查询接口的瞬时错误（429/5xx）按可重试处理继续轮询，4xx 立即抛出。
        deadline = time.monotonic() + self.config.request_timeout_seconds
        poll_interval_seconds = 0.5
        max_poll_interval_seconds = 5.0
        while True:
            try:
                query_response = self._get_json(
                    self.config.tts_async_query_url,
                    {"task_id": str(task_id)},
                )
                _report_progress(on_progress)
            except httpx.HTTPStatusError as exc:
                _report_progress(on_progress)
                if 400 <= exc.response.status_code < 500 and exc.response.status_code != 429:
                    raise
                # 429/5xx：瞬时错误，继续轮询直到 deadline
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        "MiniMax async TTS query kept failing until timeout"
                    ) from exc
                time.sleep(poll_interval_seconds)
                poll_interval_seconds = min(
                    max_poll_interval_seconds, poll_interval_seconds * 2
                )
                continue
            _raise_for_base_resp(query_response)
            status = str(query_response.get("status") or "").lower()
            if status == "success":
                file_id = query_response.get("file_id") or file_id
                break
            if status in {"failed", "expired"}:
                raise RuntimeError(f"MiniMax async TTS task ended with status {status}")
            if time.monotonic() >= deadline:
                raise RuntimeError("MiniMax async TTS task did not complete before timeout")
            time.sleep(poll_interval_seconds)
            poll_interval_seconds = min(max_poll_interval_seconds, poll_interval_seconds * 2)

        if file_id is None:
            raise RuntimeError("MiniMax async TTS query response did not include file_id")
        bundle = self._download_file(file_id, on_progress=on_progress)
        output_path.write_bytes(bundle.audio_bytes)
        _report_progress(on_progress)
        return bundle.subtitle_text

    def _post_json(self, url: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
        _ensure_http_url(url)
        response = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {self.config.api_key or ''}",
                "Content-Type": "application/json",
            },
            json=dict(payload),
            timeout=self.config.request_timeout_seconds,
        )
        response.raise_for_status()
        return cast(Mapping[str, Any], response.json())

    def _get_json(self, url: str, query: Mapping[str, str]) -> Mapping[str, Any]:
        _ensure_http_url(url)
        response = httpx.get(
            url,
            headers={"Authorization": f"Bearer {self.config.api_key or ''}"},
            params=dict(query),
            timeout=self.config.request_timeout_seconds,
        )
        response.raise_for_status()
        return cast(Mapping[str, Any], response.json())

    def _download_file(
        self,
        file_id: Any,
        on_progress: Optional[ProgressCallback] = None,
    ) -> SynthesisBundle:
        _report_progress(on_progress)
        _ensure_http_url(self.config.file_retrieve_url)
        response = httpx.get(
            self.config.file_retrieve_url,
            headers={"Authorization": f"Bearer {self.config.api_key or ''}"},
            params={"file_id": str(file_id)},
            timeout=self.config.request_timeout_seconds,
        )
        response.raise_for_status()
        _report_progress(on_progress)
        download_url = _extract_file_download_url(response)
        if download_url is not None:
            _ensure_http_url(download_url)
            _report_progress(on_progress)
            audio_response = httpx.get(
                download_url,
                headers={"Authorization": f"Bearer {self.config.api_key or ''}"},
                timeout=self.config.request_timeout_seconds,
            )
            audio_response.raise_for_status()
            _report_progress(on_progress)
            return _extract_synthesis_bundle(
                audio_response.content,
                audio_response.headers.get("content-type", ""),
            )
        return _extract_synthesis_bundle(
            response.content,
            response.headers.get("content-type", ""),
        )


class MiniMaxTTSProvider:
    """MiniMax-backed story TTS provider without synthetic browser fallback."""

    provider = "minimax"

    def __init__(
        self,
        config: Optional[MiniMaxConfig] = None,
        client: Optional[MiniMaxAsyncTTSClient] = None,
    ) -> None:
        self.config = config or build_minimax_config()
        self.model = self.config.tts_model
        self.client = client or MiniMaxAsyncTTSClient(self.config)

    def metadata(self) -> StoryTTSProviderMetadata:
        available = bool(self.config.api_key) or self.config.local_audio_enabled
        media_type = "audio/wav" if self.config.local_audio_enabled else "audio/mpeg"
        return StoryTTSProviderMetadata(
            provider=self.provider,
            model=self.model,
            playback_mode="audio" if available else "unavailable",
            media_type=media_type if available else None,
            available=available,
            backend_audio_enabled=available,
        )

    def build_async_create_payload(
        self,
        text: str,
        voice_id: str,
        speed: float,
    ) -> Dict[str, Any]:
        return {
            "model": self.model,
            "text": text,
            "language_boost": "auto",
            "voice_setting": {
                "voice_id": _map_voice_id(voice_id),
                "speed": speed,
                "vol": 1.0,
                "pitch": 0,
            },
            "audio_setting": {
                "audio_sample_rate": 32000,
                "bitrate": 128000,
                "format": "mp3",
                "channel": 1,
            },
        }

    def build_websocket_start_payload(
        self,
        text: str,
        voice_id: str,
        speed: float,
    ) -> Dict[str, Any]:
        payload = self.build_async_create_payload(text, voice_id, speed)
        payload["stream"] = False
        payload.pop("language_boost", None)
        return payload

    def synthesize(
        self,
        context: Dict[str, Any],
        voice_id: str,
        speed: float,
        on_progress: Optional[ProgressCallback] = None,
    ) -> GeneratedSpeech:
        if not self.config.api_key and not self.config.local_audio_enabled:
            raise TTSProviderUnavailableError("MiniMax TTS is not configured")

        text = str(context["text"])
        if len(text) > self.config.tts_max_chars:
            raise TTSProviderUnavailableError("Story chapter exceeds MiniMax TTS limit")
        text_hash = str(context["text_hash"])
        extension = "wav" if self.config.local_audio_enabled else "mp3"
        media_type = "audio/wav" if extension == "wav" else "audio/mpeg"
        file_name = (
            f"{_safe_token(text_hash)}-{_safe_token(voice_id)}-"
            f"{_safe_token(self.provider)}-{_safe_token(self.model)}-"
            f"speed-{_normalized_speed_token(speed)}-cache-v{VOICE_ASSET_VERSION}.{extension}"
        )
        self.config.voice_asset_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.config.voice_asset_dir / file_name
        subtitle_path = output_path.with_suffix(".srt")
        duration_ms: Optional[int] = None
        subtitle_text: Optional[str] = None
        if output_path.exists():
            try:
                duration_ms = _validated_audio_duration_ms(output_path, extension)
            except Exception:
                output_path.unlink(missing_ok=True)
            if subtitle_path.exists():
                subtitle_text = subtitle_path.read_text(encoding="utf-8")
        if duration_ms is None:
            payload = self.build_async_create_payload(text, voice_id, speed)
            temporary_path: Optional[Path] = None
            temporary_subtitle: Optional[Path] = None
            try:
                descriptor, temporary_name = tempfile.mkstemp(
                    dir=self.config.voice_asset_dir,
                    prefix=f".{file_name}.",
                    suffix=f".{extension}",
                )
                os.close(descriptor)
                temporary_path = Path(temporary_name)
                subtitle_text = self.client.synthesize_to_file(
                    payload,
                    temporary_path,
                    on_progress=on_progress,
                )
                duration_ms = _validated_audio_duration_ms(temporary_path, extension)
                paragraph_cues = self._paragraph_cues(
                    context,
                    subtitle_text,
                    duration_ms,
                )
                if subtitle_text:
                    subtitle_descriptor, subtitle_name = tempfile.mkstemp(
                        dir=self.config.voice_asset_dir,
                        prefix=f".{subtitle_path.name}.",
                        suffix=".tmp",
                    )
                    os.close(subtitle_descriptor)
                    temporary_subtitle = Path(subtitle_name)
                    temporary_subtitle.write_text(subtitle_text, encoding="utf-8")
                    os.replace(temporary_subtitle, subtitle_path)
                    temporary_subtitle = None
                os.replace(temporary_path, output_path)
                temporary_path = None
            except Exception as error:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)
                if temporary_subtitle is not None:
                    temporary_subtitle.unlink(missing_ok=True)
                raise TTSProviderUnavailableError("MiniMax TTS generation failed") from error
        else:
            paragraph_cues = self._paragraph_cues(context, subtitle_text, duration_ms)

        return GeneratedSpeech(
            storage_path=f"/api/voice-reading/audio/{file_name}",
            duration_ms=duration_ms,
            provider=self.provider,
            model=self.model,
            media_type=media_type,
            playback_mode="audio",
            paragraph_cues=paragraph_cues,
        )

    def _paragraph_cues(
        self,
        context: Mapping[str, Any],
        subtitle_text: Optional[str],
        duration_ms: int,
    ) -> tuple[ParagraphCue, ...]:
        paragraphs = [
            str(value)
            for value in context.get("paragraphs", [])
            if str(value).strip()
        ]
        if not paragraphs:
            return ()
        if subtitle_text:
            return _align_paragraph_cues(
                paragraphs,
                _parse_srt_cues(subtitle_text),
                audio_duration_ms=duration_ms,
            )
        if len(paragraphs) == 1:
            return (ParagraphCue(paragraph_index=0, start_ms=0, end_ms=duration_ms),)
        if self.config.local_audio_enabled:
            from src.services.story_tts_provider import _proportional_paragraph_cues

            return _proportional_paragraph_cues(paragraphs, duration_ms)
        raise ValueError("MiniMax chapter bundle did not include paragraph subtitles")

    def is_valid_cached_asset(self, storage_path: str) -> bool:
        """Return whether a stored MiniMax asset is safe to reuse."""
        try:
            file_name = Path(urlparse(storage_path).path).name
            expected_extension = "wav" if self.config.local_audio_enabled else "mp3"
            if not file_name or not file_name.endswith(f".{expected_extension}"):
                return False
            asset_path = (self.config.voice_asset_dir / file_name).resolve()
            asset_path.relative_to(self.config.voice_asset_dir.resolve())
            if not asset_path.is_file():
                return False
            _validated_audio_duration_ms(asset_path, expected_extension)
        except (OSError, RuntimeError, ValueError):
            return False
        return True


def _report_progress(on_progress: Optional[ProgressCallback]) -> None:
    if on_progress is not None:
        on_progress()


def _map_voice_id(voice_id: str) -> str:
    return {
        "warm_female": "female-shaonv",
        "calm_male": "male-qn-qingse",
        "clear_neutral": "female-yujie",
    }.get(voice_id, "female-shaonv")


def _safe_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-_")
    return token or "unknown"


def _normalized_speed_token(speed: float) -> str:
    if speed <= 0:
        raise ValueError("MiniMax TTS speed must be positive")
    return f"float64-{struct.pack('!d', float(speed)).hex()}"


def _validated_audio_duration_ms(audio_path: Path, extension: str) -> int:
    try:
        mutagen_file = cast(Any, getattr(mutagen, "File"))
        audio = mutagen_file(audio_path)
        expected_type = MP3 if extension == "mp3" else WAVE
        if not isinstance(audio, expected_type):
            raise ValueError(f"expected valid {extension} audio")
        duration_seconds = getattr(audio.info, "length", None)
        if duration_seconds is None or duration_seconds <= 0:
            raise ValueError("audio duration is missing or invalid")
    except Exception as error:
        raise RuntimeError("MiniMax TTS generated invalid audio") from error
    return max(1, int(round(float(duration_seconds) * 1000)))


def _json_dumps(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _extract_audio_hex(payload: Mapping[str, Any]) -> Optional[str]:
    candidates = [payload.get("audio")]
    data = payload.get("data")
    if isinstance(data, Mapping):
        candidates.extend([data.get("audio"), data.get("audio_hex")])
    for candidate in candidates:
        if isinstance(candidate, str) and candidate:
            return candidate
    return None


def _is_done_message(payload: Mapping[str, Any]) -> bool:
    candidates = [payload.get("status"), payload.get("event")]
    data = payload.get("data")
    if isinstance(data, Mapping):
        candidates.extend([data.get("status"), data.get("event")])
    return any(str(candidate).lower() in {"done", "finished", "complete"} for candidate in candidates)


def _raise_for_base_resp(payload: Mapping[str, Any]) -> None:
    base_resp = payload.get("base_resp")
    if not isinstance(base_resp, Mapping):
        return
    status_code = int(base_resp.get("status_code") or 0)
    if status_code != 0:
        status_msg = str(base_resp.get("status_msg") or "unknown")
        raise RuntimeError(f"MiniMax async TTS request failed: {status_code} {status_msg}")


def _extract_file_download_url(response: httpx.Response) -> Optional[str]:
    content_type = response.headers.get("content-type", "").lower()
    if "json" not in content_type:
        return None
    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, Mapping):
        return None

    candidates: list[Any] = [
        payload.get("download_url"),
        payload.get("url"),
    ]
    file_payload = payload.get("file")
    if isinstance(file_payload, Mapping):
        candidates.extend([file_payload.get("download_url"), file_payload.get("url")])
    data_payload = payload.get("data")
    if isinstance(data_payload, Mapping):
        candidates.extend([data_payload.get("download_url"), data_payload.get("url")])
        data_file = data_payload.get("file")
        if isinstance(data_file, Mapping):
            candidates.extend([data_file.get("download_url"), data_file.get("url")])

    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _extract_audio_file_bytes(content: bytes, content_type: str) -> bytes:
    return _extract_synthesis_bundle(content, content_type).audio_bytes


def _extract_synthesis_bundle(content: bytes, content_type: str) -> SynthesisBundle:
    try:
        archive = tarfile.open(fileobj=BytesIO(content), mode="r:*")
    except tarfile.ReadError:
        return SynthesisBundle(audio_bytes=content)
    with archive:
        regular_members = [member for member in archive.getmembers() if member.isfile()]
        audio_member = next(
            (
                member
                for member in regular_members
                if member.name.lower().endswith((".mp3", ".wav", ".flac"))
            ),
            None,
        )
        if audio_member is None:
            return SynthesisBundle(audio_bytes=content)
        extracted_audio = archive.extractfile(audio_member)
        if extracted_audio is None:
            return SynthesisBundle(audio_bytes=content)
        subtitle_member = next(
            (member for member in regular_members if member.name.lower().endswith(".srt")),
            None,
        )
        subtitle_text: Optional[str] = None
        if subtitle_member is not None:
            extracted_subtitle = archive.extractfile(subtitle_member)
            if extracted_subtitle is not None:
                subtitle_text = extracted_subtitle.read().decode("utf-8-sig")
        return SynthesisBundle(
            audio_bytes=extracted_audio.read(),
            subtitle_text=subtitle_text,
        )


_SRT_TIMESTAMP = re.compile(
    r"^(?P<start_h>\d{2}):(?P<start_m>\d{2}):(?P<start_s>\d{2})[,.](?P<start_ms>\d{3})"
    r"\s+-->\s+"
    r"(?P<end_h>\d{2}):(?P<end_m>\d{2}):(?P<end_s>\d{2})[,.](?P<end_ms>\d{3})$"
)


def _parse_srt_cues(subtitle_text: str) -> list[SubtitleCue]:
    cues: list[SubtitleCue] = []
    normalized_subtitles = subtitle_text.replace("\r\n", "\n").strip()
    for block in re.split(r"\n\s*\n", normalized_subtitles):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        timestamp_index = next(
            (index for index, line in enumerate(lines) if _SRT_TIMESTAMP.match(line)),
            None,
        )
        if timestamp_index is None or timestamp_index + 1 >= len(lines):
            continue
        match = _SRT_TIMESTAMP.match(lines[timestamp_index])
        if match is None:
            continue
        start_ms = _srt_timestamp_ms(match, "start")
        end_ms = _srt_timestamp_ms(match, "end")
        if end_ms <= start_ms or (cues and start_ms < cues[-1].end_ms):
            raise ValueError("MiniMax subtitles contain invalid timestamps")
        cues.append(
            SubtitleCue(
                start_ms=start_ms,
                end_ms=end_ms,
                text=" ".join(lines[timestamp_index + 1 :]),
            )
        )
    if not cues:
        raise ValueError("MiniMax subtitles contain no sentence cues")
    return cues


def _srt_timestamp_ms(match: re.Match[str], prefix: str) -> int:
    return (
        int(match.group(f"{prefix}_h")) * 3_600_000
        + int(match.group(f"{prefix}_m")) * 60_000
        + int(match.group(f"{prefix}_s")) * 1_000
        + int(match.group(f"{prefix}_ms"))
    )


def _align_paragraph_cues(
    paragraphs: list[str],
    subtitle_cues: list[SubtitleCue],
    *,
    audio_duration_ms: int,
) -> tuple[ParagraphCue, ...]:
    if not paragraphs or audio_duration_ms <= 0:
        raise ValueError("Cannot align MiniMax subtitles without chapter content")
    starts: list[int] = []
    subtitle_index = 0
    for paragraph in paragraphs:
        normalized_paragraph = _normalize_alignment_text(paragraph)
        if not normalized_paragraph or subtitle_index >= len(subtitle_cues):
            raise ValueError("Could not align MiniMax subtitles to story paragraphs")
        starts.append(subtitle_cues[subtitle_index].start_ms)
        accumulated = ""
        while subtitle_index < len(subtitle_cues):
            accumulated += _normalize_alignment_text(subtitle_cues[subtitle_index].text)
            subtitle_index += 1
            if accumulated == normalized_paragraph:
                break
            if not normalized_paragraph.startswith(accumulated):
                raise ValueError("Could not align MiniMax subtitles to story paragraphs")
        else:
            raise ValueError("Could not align MiniMax subtitles to story paragraphs")
    if starts != sorted(starts) or starts[-1] >= audio_duration_ms:
        raise ValueError("MiniMax paragraph cues are outside the chapter duration")
    return tuple(
        ParagraphCue(
            paragraph_index=index,
            start_ms=start,
            end_ms=starts[index + 1] if index + 1 < len(starts) else audio_duration_ms,
        )
        for index, start in enumerate(starts)
    )


def _normalize_alignment_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _ensure_http_url(url: str) -> None:
    scheme = urlparse(url).scheme.lower()
    if scheme not in {"http", "https"}:
        raise ValueError("MiniMax async TTS URLs must use http or https")
