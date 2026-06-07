"""MiniMax story-conditioned music generation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

import httpx
from sqlalchemy.orm import Session

from src.database.models import GeneratedMusicAsset
from src.services.minimax_config import MiniMaxConfig, build_minimax_config
from src.services.music_service import MusicBrief


@dataclass(frozen=True)
class MiniMaxMusicGenerationRequest:
    game_id: int
    brief: MusicBrief
    model: str
    output_format: str = "url"
    audio_format: str = "mp3"
    sample_rate: int = 44100
    bitrate: int = 256000
    is_instrumental: bool = True

    @classmethod
    def from_brief(
        cls,
        game_id: int,
        brief: MusicBrief,
        model: str,
    ) -> "MiniMaxMusicGenerationRequest":
        return cls(game_id=game_id, brief=brief, model=model)

    def to_payload(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "prompt": self.brief.generation_prompt,
            "output_format": self.output_format,
            "is_instrumental": self.is_instrumental,
            "audio_setting": {
                "sample_rate": self.sample_rate,
                "bitrate": self.bitrate,
                "format": self.audio_format,
            },
        }

    def generation_settings(self) -> Dict[str, Any]:
        return {
            "output_format": self.output_format,
            "format": self.audio_format,
            "sample_rate": self.sample_rate,
            "bitrate": self.bitrate,
            "is_instrumental": self.is_instrumental,
        }


@dataclass(frozen=True)
class GeneratedMusicFile:
    storage_path: str
    local_path: Path
    duration_ms: int
    provider: str
    model: str
    media_type: str


class MiniMaxMusicGenerationProvider:
    provider = "minimax"

    def __init__(self, config: Optional[MiniMaxConfig] = None) -> None:
        self.config = config or build_minimax_config()
        self.model = self.config.music_model

    def generate_to_asset(
        self,
        request: MiniMaxMusicGenerationRequest,
        brief_hash: str,
    ) -> GeneratedMusicFile:
        if not self.config.api_key:
            raise RuntimeError("MiniMax music generation requires MINIMAX_API_KEY")

        if self.config.local_audio_enabled:
            from src.services.story_voice_reading import build_deterministic_wav

            file_name = f"{brief_hash}-{request.model}.wav"
            self.config.music_asset_dir.mkdir(parents=True, exist_ok=True)
            local_path = self.config.music_asset_dir / file_name
            local_path.write_bytes(
                build_deterministic_wav(request.brief.generation_prompt, "music")
            )
            return GeneratedMusicFile(
                storage_path=f"/api/music/generated/{file_name}",
                local_path=local_path,
                duration_ms=2400,
                provider=self.provider,
                model=request.model,
                media_type="audio/wav",
            )

        response = httpx.post(
            self.config.music_generation_url,
            headers={"Authorization": f"Bearer {self.config.api_key}"},
            json=request.to_payload(),
            timeout=self.config.request_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        provider_error = _extract_provider_error(payload)
        if provider_error:
            raise RuntimeError(provider_error)

        audio_url = _extract_audio_url(payload)
        audio_bytes: Optional[bytes]
        if audio_url:
            audio_response = httpx.get(audio_url, timeout=self.config.request_timeout_seconds)
            audio_response.raise_for_status()
            audio_bytes = audio_response.content
        else:
            audio_bytes = _extract_audio_bytes(payload)

        if not audio_bytes:
            raise RuntimeError("MiniMax music generation response did not include playable audio")

        file_name = f"{brief_hash}-{request.model}.{request.audio_format}"
        self.config.music_asset_dir.mkdir(parents=True, exist_ok=True)
        local_path = self.config.music_asset_dir / file_name
        local_path.write_bytes(audio_bytes)
        return GeneratedMusicFile(
            storage_path=f"/api/music/generated/{file_name}",
            local_path=local_path,
            duration_ms=_extract_duration_ms(payload) or 60_000,
            provider=self.provider,
            model=request.model,
            media_type="audio/mpeg" if request.audio_format == "mp3" else "audio/wav",
        )

    @staticmethod
    def build_brief_from_story(
        story_text: str,
        analysis: Mapping[str, Any],
        max_prompt_chars: int,
    ) -> MusicBrief:
        brief = MusicBrief.from_analysis(dict(analysis))
        summary = _compact_story_summary(story_text, max(80, max_prompt_chars // 3))
        prompt = (
            "Create instrumental background music for narrative gameplay. "
            f"Story summary: {summary}. "
            f"Mood: {brief.mood}. Scene: {brief.scene_type}. "
            f"Setting: {brief.era_or_environment}. Pacing: {brief.pacing}. "
            f"Energy: {brief.energy}. Instruments: {', '.join(brief.instruments)}. "
            "No vocals, no lyrics, no dominant pop singing."
        )
        if len(prompt) > max_prompt_chars:
            prompt = prompt[: max_prompt_chars - 1].rstrip() + "."
        return MusicBrief(
            mood=brief.mood,
            scene_type=brief.scene_type,
            era_or_environment=brief.era_or_environment,
            pacing=brief.pacing,
            energy=brief.energy,
            instruments=brief.instruments,
            search_queries=brief.search_queries,
            negative_cues=brief.negative_cues,
            generation_prompt=prompt,
        )

    @staticmethod
    def to_playlist_track(
        asset_id: int,
        title: str,
        audio_url: str,
        duration_ms: int,
        provider: str,
        model: str,
        brief_hash: str,
    ) -> Dict[str, Any]:
        return {
            "id": f"ai-generated-{asset_id}",
            "name": title,
            "artists": ["MiniMax"],
            "album": "AI Generated",
            "duration": duration_ms,
            "url": audio_url,
            "source": "ai_generated",
            "provider": provider,
            "model": model,
            "asset_id": asset_id,
            "brief_hash": brief_hash,
        }


class StoryMusicGenerationService:
    """Coordinates story brief creation and provider-backed generation."""

    def __init__(self, provider: Optional[MiniMaxMusicGenerationProvider] = None) -> None:
        self.provider = provider or MiniMaxMusicGenerationProvider()

    def generate_ready_track(
        self,
        db: Session,
        game_id: int,
        story_text: str,
        analysis: Mapping[str, Any],
    ) -> Dict[str, Any]:
        brief = self.provider.build_brief_from_story(
            story_text=story_text,
            analysis=analysis,
            max_prompt_chars=self.provider.config.max_music_prompt_chars,
        )
        request = MiniMaxMusicGenerationRequest.from_brief(
            game_id=game_id,
            brief=brief,
            model=self.provider.model,
        )
        settings = request.generation_settings()
        brief_hash = music_brief_hash(brief, request.model, settings)
        repository = GeneratedMusicAssetRepository(db)
        ready_asset = repository.find_ready_asset(
            game_id=game_id,
            provider=self.provider.provider,
            model=request.model,
            brief_hash=brief_hash,
            generation_settings=settings,
        )
        if ready_asset is None:
            generated = self.provider.generate_to_asset(request, brief_hash=brief_hash)
            ready_asset = repository.create_ready_asset(
                game_id=game_id,
                provider=generated.provider,
                model=generated.model,
                music_brief=brief.to_analysis(),
                prompt_text=brief.generation_prompt,
                brief_hash=brief_hash,
                storage_path=generated.storage_path,
                duration_ms=generated.duration_ms,
                generation_settings=settings,
            )
            db.commit()
            db.refresh(ready_asset)

        asset_id = int(ready_asset.asset_id)
        title_scene = brief.scene_type if brief.scene_type else "故事配乐"
        return self.provider.to_playlist_track(
            asset_id=asset_id,
            title=f"AI MiniMax {title_scene}",
            audio_url=str(ready_asset.storage_path),
            duration_ms=int(ready_asset.duration_ms or 0),
            provider=str(ready_asset.provider),
            model=str(ready_asset.model),
            brief_hash=str(ready_asset.brief_hash),
        )


class GeneratedMusicAssetRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_ready_asset(
        self,
        game_id: int,
        provider: str,
        model: str,
        music_brief: Dict[str, Any],
        prompt_text: str,
        brief_hash: str,
        storage_path: str,
        duration_ms: int,
        generation_settings: Dict[str, Any],
    ) -> GeneratedMusicAsset:
        brief_with_settings = dict(music_brief)
        brief_with_settings["_generation_settings"] = generation_settings
        asset = GeneratedMusicAsset(
            game_id=game_id,
            provider=provider,
            model=model,
            status="ready",
            source="ai_generated",
            music_brief_json=brief_with_settings,
            prompt_text=prompt_text,
            brief_hash=brief_hash,
            storage_path=storage_path,
            duration_ms=duration_ms,
            loopable=True,
        )
        self.db.add(asset)
        self.db.flush()
        return asset

    def find_ready_asset(
        self,
        game_id: int,
        provider: str,
        model: str,
        brief_hash: str,
        generation_settings: Dict[str, Any],
    ) -> Optional[GeneratedMusicAsset]:
        candidates = (
            self.db.query(GeneratedMusicAsset)
            .filter(
                GeneratedMusicAsset.game_id == game_id,
                GeneratedMusicAsset.provider == provider,
                GeneratedMusicAsset.model == model,
                GeneratedMusicAsset.brief_hash == brief_hash,
                GeneratedMusicAsset.status == "ready",
            )
            .order_by(GeneratedMusicAsset.created_at.desc())
            .all()
        )
        for asset in candidates:
            settings = dict(asset.music_brief_json or {}).get("_generation_settings")
            if settings == generation_settings:
                return asset
        return None


def music_brief_hash(brief: MusicBrief, model: str, settings: Mapping[str, Any]) -> str:
    identity = {
        "brief": brief.to_analysis(),
        "model": model,
        "settings": dict(settings),
    }
    return sha256(repr(identity).encode("utf-8")).hexdigest()


def _compact_story_summary(story_text: str, max_chars: int) -> str:
    normalized = " ".join(story_text.split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 1].rstrip() + "."


def _extract_audio_url(payload: Mapping[str, Any]) -> Optional[str]:
    candidates = [
        payload.get("audio_url"),
        payload.get("url"),
        payload.get("audio"),
    ]
    data = payload.get("data")
    if isinstance(data, Mapping):
        candidates.extend([data.get("audio_url"), data.get("url"), data.get("audio")])
        audio = data.get("audio")
        if isinstance(audio, Mapping):
            candidates.extend([audio.get("audio_url"), audio.get("url")])
    for candidate in candidates:
        if isinstance(candidate, str) and _is_audio_url(candidate):
            return candidate
    return None


def _is_audio_url(value: str) -> bool:
    stripped = value.strip()
    return stripped.startswith("https://") or stripped.startswith("http://")


def _extract_provider_error(payload: Mapping[str, Any]) -> Optional[str]:
    base_resp = payload.get("base_resp")
    if not isinstance(base_resp, Mapping):
        return None

    status_code = base_resp.get("status_code")
    status_msg = base_resp.get("status_msg")
    if status_code in (None, 0, "0"):
        return None

    details = [f"status_code={status_code}"]
    if isinstance(status_msg, str) and status_msg.strip():
        details.append(status_msg.strip())
    return f"MiniMax music generation failed ({'; '.join(details)})"


def _extract_audio_bytes(payload: Mapping[str, Any]) -> Optional[bytes]:
    candidates: list[Any] = [payload.get("audio"), payload.get("audio_hex")]
    data = payload.get("data")
    if isinstance(data, Mapping):
        candidates.extend([data.get("audio"), data.get("audio_hex")])

    for candidate in candidates:
        if not isinstance(candidate, str) or not candidate.strip():
            continue
        normalized = "".join(candidate.split())
        try:
            audio = bytes.fromhex(normalized)
        except ValueError:
            continue
        if audio:
            return audio
    return None


def _extract_duration_ms(payload: Mapping[str, Any]) -> Optional[int]:
    candidates: list[Any] = [
        payload.get("duration_ms"),
        payload.get("duration"),
    ]
    data = payload.get("data")
    if isinstance(data, Mapping):
        candidates.extend([data.get("duration_ms"), data.get("duration")])
    extra_info = payload.get("extra_info")
    if isinstance(extra_info, Mapping):
        candidates.extend(
            [
                extra_info.get("duration_ms"),
                extra_info.get("duration"),
                extra_info.get("music_duration"),
            ]
        )

    for candidate in candidates:
        duration = _coerce_positive_int(candidate)
        if duration is not None:
            return duration
    return None


def _coerce_positive_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float):
        return int(value) if value > 0 else None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            parsed = float(stripped)
        except ValueError:
            return None
        return int(parsed) if parsed > 0 else None
    return None
