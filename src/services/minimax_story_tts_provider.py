"""MiniMax story text-to-speech provider."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tarfile
import time
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, cast
from urllib.parse import urlparse

import httpx

from src.services.minimax_config import MiniMaxConfig, build_minimax_config
from src.services.story_tts_provider import (
    GeneratedSpeech,
    StoryTTSProviderMetadata,
    TTSProviderUnavailableError,
    build_deterministic_wav,
)


class MiniMaxWebSocketTTSClient:
    """Small boundary for MiniMax WebSocket TTS synthesis."""

    def __init__(self, config: MiniMaxConfig) -> None:
        self.config = config

    def synthesize_to_file(
        self,
        payload: Mapping[str, Any],
        output_path: Path,
    ) -> None:
        """Write synthesized audio to `output_path`.

        The real network implementation is intentionally isolated here so provider
        contracts and DB tests can exercise all higher layers without credentials.
        """
        if os.getenv("MINIMAX_E2E_LOCAL_AUDIO", "0") == "1":
            text = str(payload.get("text") or "minimax-local-audio")
            text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            output_path.write_bytes(build_deterministic_wav(text_hash, "warm_female"))
            return
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


class MiniMaxAsyncTTSClient:
    """Boundary for MiniMax async TTS task creation, polling, and download."""

    def __init__(self, config: MiniMaxConfig) -> None:
        self.config = config

    def synthesize_to_file(
        self,
        payload: Mapping[str, Any],
        output_path: Path,
    ) -> None:
        if self.config.local_audio_enabled:
            text = str(payload.get("text") or "minimax-local-audio")
            text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            output_path.write_bytes(build_deterministic_wav(text_hash, "warm_female"))
            return

        create_response = self._post_json(self.config.tts_async_create_url, payload)
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
            except httpx.HTTPStatusError as exc:
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
        output_path.write_bytes(self._download_file(file_id))

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

    def _download_file(self, file_id: Any) -> bytes:
        _ensure_http_url(self.config.file_retrieve_url)
        response = httpx.get(
            self.config.file_retrieve_url,
            headers={"Authorization": f"Bearer {self.config.api_key or ''}"},
            params={"file_id": str(file_id)},
            timeout=self.config.request_timeout_seconds,
        )
        response.raise_for_status()
        download_url = _extract_file_download_url(response)
        if download_url is not None:
            _ensure_http_url(download_url)
            audio_response = httpx.get(
                download_url,
                headers={"Authorization": f"Bearer {self.config.api_key or ''}"},
                timeout=self.config.request_timeout_seconds,
            )
            audio_response.raise_for_status()
            return _extract_audio_file_bytes(
                audio_response.content,
                audio_response.headers.get("content-type", ""),
            )
        return _extract_audio_file_bytes(response.content, response.headers.get("content-type", ""))


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

    def synthesize(self, context: Dict[str, Any], voice_id: str, speed: float) -> GeneratedSpeech:
        if not self.config.api_key and not self.config.local_audio_enabled:
            raise TTSProviderUnavailableError("MiniMax TTS is not configured")

        text = str(context["text"])
        if len(text) > self.config.tts_max_chars:
            raise TTSProviderUnavailableError("Story paragraph exceeds MiniMax TTS limit")
        text_hash = str(context["text_hash"])
        extension = "wav" if self.config.local_audio_enabled else "mp3"
        media_type = "audio/wav" if extension == "wav" else "audio/mpeg"
        file_name = (
            f"{_safe_token(text_hash)}-{_safe_token(voice_id)}-"
            f"{_safe_token(self.provider)}-{_safe_token(self.model)}.{extension}"
        )
        self.config.voice_asset_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.config.voice_asset_dir / file_name
        if not output_path.exists():
            payload = self.build_async_create_payload(text, voice_id, speed)
            try:
                self.client.synthesize_to_file(payload, output_path)
            except Exception as error:
                raise TTSProviderUnavailableError("MiniMax TTS generation failed") from error

        return GeneratedSpeech(
            storage_path=f"/api/voice-reading/audio/{file_name}",
            duration_ms=max(1_000, int(len(text) * 120 / speed)),
            provider=self.provider,
            model=self.model,
            media_type=media_type,
            playback_mode="audio",
        )


def _map_voice_id(voice_id: str) -> str:
    return {
        "warm_female": "female-shaonv",
        "calm_male": "male-qn-qingse",
        "clear_neutral": "female-yujie",
    }.get(voice_id, "female-shaonv")


def _safe_token(value: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-_")
    return token or "unknown"


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
    if "tar" not in content_type.lower():
        return content
    with tarfile.open(fileobj=BytesIO(content), mode="r:*") as archive:
        members = [
            member
            for member in archive.getmembers()
            if member.isfile() and member.name.lower().endswith((".mp3", ".wav"))
        ]
        if not members:
            return content
        extracted = archive.extractfile(members[0])
        if extracted is None:
            return content
        return extracted.read()


def _ensure_http_url(url: str) -> None:
    scheme = urlparse(url).scheme.lower()
    if scheme not in {"http", "https"}:
        raise ValueError("MiniMax async TTS URLs must use http or https")
