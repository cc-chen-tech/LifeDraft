"""MiniMax provider configuration helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from config.settings import PROJECT_ROOT


@dataclass(frozen=True)
class MiniMaxConfig:
    """Runtime configuration for MiniMax-backed audio generation."""

    api_key: Optional[str]
    group_id: Optional[str]
    tts_model: str
    tts_websocket_url: str
    tts_async_create_url: str
    tts_async_query_url: str
    file_retrieve_url: str
    request_timeout_seconds: float
    tts_max_chars: int
    story_auto_read_default_enabled: bool
    local_audio_enabled: bool
    voice_asset_dir: Path

    @classmethod
    def from_env(
        cls,
        env: Optional[Mapping[str, str]] = None,
        voice_asset_dir: Optional[Path] = None,
    ) -> "MiniMaxConfig":
        source = env if env is not None else os.environ
        configured_voice_dir = source.get("STORY_TTS_ASSET_DIR")
        return cls(
            api_key=_blank_to_none(source.get("MINIMAX_API_KEY")),
            group_id=_blank_to_none(source.get("MINIMAX_GROUP_ID")),
            tts_model=source.get("MINIMAX_TTS_MODEL", "speech-02-turbo"),
            tts_websocket_url=source.get(
                "MINIMAX_TTS_WEBSOCKET_URL",
                "wss://api.minimax.chat/ws/v1/t2a_v2",
            ),
            tts_async_create_url=source.get(
                "MINIMAX_TTS_ASYNC_CREATE_URL",
                "https://api.minimaxi.com/v1/t2a_async_v2",
            ),
            tts_async_query_url=source.get(
                "MINIMAX_TTS_ASYNC_QUERY_URL",
                "https://api.minimaxi.com/v1/query/t2a_async_query_v2",
            ),
            file_retrieve_url=source.get(
                "MINIMAX_FILE_RETRIEVE_URL",
                "https://api.minimaxi.com/v1/files/retrieve_content",
            ),
            request_timeout_seconds=float(source.get("MINIMAX_TIMEOUT_SECONDS", "180")),
            tts_max_chars=int(source.get("MINIMAX_TTS_MAX_CHARS", "50000")),
            story_auto_read_default_enabled=_truthy(
                source.get("STORY_TTS_AUTO_READ_DEFAULT_ENABLED", "true")
            ),
            local_audio_enabled=_truthy(source.get("MINIMAX_E2E_LOCAL_AUDIO", "false")),
            voice_asset_dir=voice_asset_dir
            or (Path(configured_voice_dir) if configured_voice_dir else PROJECT_ROOT / "data" / "voice_assets"),
        )


def build_minimax_config() -> MiniMaxConfig:
    return MiniMaxConfig.from_env()


def _blank_to_none(value: Optional[str]) -> Optional[str]:
    if value is None or not value.strip():
        return None
    return value


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}
