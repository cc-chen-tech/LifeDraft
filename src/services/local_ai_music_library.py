"""Local searchable library for ready AI-generated music assets."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from sqlalchemy.orm import Session

from src.database.models import GeneratedMusicAsset, GeneratedMusicLibraryEntry
from src.services.music_scene_matching import MusicSceneFitProfile, MusicSceneFitScorer
from src.services.music_service import MusicBrief
from src.services.music_track_title import generated_music_title


DEFAULT_LIBRARY_MATCH_THRESHOLD = 70
DEFAULT_LIBRARY_LOOKUP_TIMEOUT_SECONDS = 0.25


@dataclass(frozen=True)
class LocalAiMusicMatchDecision:
    hit: bool
    asset_id: Optional[int] = None
    entry_id: Optional[int] = None
    score: int = 0
    reason: Optional[str] = None
    rejection_reasons: list[str] = field(default_factory=list)
    entry: Optional[GeneratedMusicLibraryEntry] = None


class LocalAiMusicLibraryService:
    """Indexes and searches reusable generated background music profiles."""

    def __init__(
        self,
        match_threshold: Optional[int] = None,
        enabled: Optional[bool] = None,
        lookup_timeout_seconds: Optional[float] = None,
        reuse_scope: Optional[str] = None,
    ) -> None:
        self.match_threshold = (
            match_threshold
            if match_threshold is not None
            else int(
                os.getenv(
                    "STORY_MUSIC_LOCAL_LIBRARY_MATCH_THRESHOLD",
                    str(DEFAULT_LIBRARY_MATCH_THRESHOLD),
                )
            )
        )
        self.lookup_timeout_seconds = (
            lookup_timeout_seconds
            if lookup_timeout_seconds is not None
            else float(
                os.getenv(
                    "STORY_MUSIC_LOCAL_LIBRARY_TIMEOUT_SECONDS",
                    str(DEFAULT_LIBRARY_LOOKUP_TIMEOUT_SECONDS),
                )
            )
        )
        self.reuse_scope = (
            reuse_scope or os.getenv("STORY_MUSIC_LOCAL_LIBRARY_REUSE_SCOPE", "global")
        ).strip().lower()
        self.enabled = _truthy(
            os.getenv("STORY_MUSIC_LOCAL_LIBRARY_ENABLED", "true")
        ) if enabled is None else enabled

    def backfill_ready_assets(self, db: Session) -> int:
        """Ensure every ready generated asset has a sanitized library profile."""
        if not self.enabled:
            return 0
        ready_assets = (
            db.query(GeneratedMusicAsset)
            .filter(
                GeneratedMusicAsset.status == "ready",
                GeneratedMusicAsset.source == "ai_generated",
            )
            .all()
        )
        indexed = 0
        for asset in ready_assets:
            if self.upsert_ready_asset(db, asset) is not None:
                indexed += 1
        return indexed

    def upsert_ready_asset(
        self,
        db: Session,
        asset: GeneratedMusicAsset,
    ) -> Optional[GeneratedMusicLibraryEntry]:
        if not self.enabled or str(asset.status) != "ready":
            return None

        brief = _brief_dict(asset.music_brief_json)
        settings = _generation_settings(brief)
        existing = (
            db.query(GeneratedMusicLibraryEntry)
            .filter_by(asset_id=asset.asset_id)
            .one_or_none()
        )
        entry = existing or GeneratedMusicLibraryEntry(asset_id=asset.asset_id)
        entry.source_game_id = int(asset.game_id)
        entry.provider = str(asset.provider)
        entry.model = str(asset.model)
        entry.status = str(asset.status)
        entry.mood = _profile_text(brief, "mood", MusicBrief.default().mood)
        entry.scene_type = _profile_text(
            brief,
            "scene_type",
            MusicBrief.default().scene_type,
        )
        entry.environment = _profile_text(
            brief,
            "era_or_environment",
            str(brief.get("environment") or MusicBrief.default().era_or_environment),
        )
        entry.pacing = _profile_text(brief, "pacing", MusicBrief.default().pacing)
        entry.energy = _profile_text(brief, "energy", MusicBrief.default().energy)
        entry.instruments_json = _profile_list(
            brief,
            "instruments",
            MusicBrief.default().instruments,
        )
        entry.negative_cues_json = _profile_list(
            brief,
            "negative_cues",
            MusicBrief.default().negative_cues,
        )
        entry.generation_settings_json = settings
        entry.prompt_fingerprint = sha256(
            str(asset.prompt_text or "").encode("utf-8")
        ).hexdigest()
        entry.duration_ms = int(asset.duration_ms or 0)
        entry.loopable = bool(asset.loopable)
        if existing is None:
            entry.usage_count = 0
            db.add(entry)
        db.flush()
        return entry

    def find_best_match(
        self,
        db: Session,
        *,
        requesting_game_id: int,
        brief: MusicBrief,
        provider: str,
        model: str,
        generation_settings: Mapping[str, Any],
        excluded_asset_ids: Optional[Iterable[int]] = None,
    ) -> LocalAiMusicMatchDecision:
        if not self.enabled:
            return LocalAiMusicMatchDecision(hit=False, rejection_reasons=["disabled"])

        lookup_started_at = time.monotonic()
        self.backfill_ready_assets(db)
        if self._timed_out(lookup_started_at):
            return LocalAiMusicMatchDecision(
                hit=False,
                rejection_reasons=["lookup_timeout"],
            )
        entries = (
            db.query(GeneratedMusicLibraryEntry)
            .filter(GeneratedMusicLibraryEntry.status == "ready")
            .all()
        )
        rejection_reasons: set[str] = set()
        excluded_ids = {int(asset_id) for asset_id in excluded_asset_ids or []}
        best_entry: Optional[GeneratedMusicLibraryEntry] = None
        best_score = 0

        for entry in entries:
            if self._timed_out(lookup_started_at):
                rejection_reasons.add("lookup_timeout")
                break
            asset = entry.asset
            if asset is None:
                rejection_reasons.add("stale_audio")
                continue
            if int(entry.asset_id) in excluded_ids:
                rejection_reasons.add("already_in_playlist")
                continue
            if (
                self.reuse_scope == "game"
                and entry.source_game_id != requesting_game_id
            ):
                rejection_reasons.add("reuse_scope_mismatch")
                continue
            if entry.provider != provider or entry.model != model:
                rejection_reasons.add("provider_model_mismatch")
                continue
            if dict(entry.generation_settings_json or {}) != dict(generation_settings):
                rejection_reasons.add("generation_settings_mismatch")
                continue
            if not _asset_audio_exists(str(asset.storage_path)):
                rejection_reasons.add("stale_audio")
                continue
            if _conflicts_with_negative_cues(entry, asset, brief):
                rejection_reasons.add("negative_cue_conflict")
                continue

            score = self.score_entry(entry, brief)
            if score < self.match_threshold:
                rejection_reasons.add("low_scene_fit")
                continue
            if (
                best_entry is None
                or score > best_score
                or (
                    score == best_score
                    and _entry_recency_key(entry) > _entry_recency_key(best_entry)
                )
            ):
                best_entry = entry
                best_score = score

        if best_entry is None:
            return LocalAiMusicMatchDecision(
                hit=False,
                score=best_score,
                rejection_reasons=sorted(rejection_reasons),
            )

        return LocalAiMusicMatchDecision(
            hit=True,
            asset_id=int(best_entry.asset_id),
            entry_id=int(best_entry.entry_id),
            score=best_score,
            reason="scene_fit",
            rejection_reasons=sorted(rejection_reasons),
            entry=best_entry,
        )

    def _timed_out(self, lookup_started_at: float) -> bool:
        if self.lookup_timeout_seconds <= 0:
            return True
        return (time.monotonic() - lookup_started_at) > self.lookup_timeout_seconds

    def score_entry(self, entry: GeneratedMusicLibraryEntry, brief: MusicBrief) -> int:
        score = 0
        score += _field_score(entry.mood, brief.mood, exact=18, partial=8)
        score += _field_score(entry.scene_type, brief.scene_type, exact=28, partial=12)
        score += _field_score(entry.environment, brief.era_or_environment, exact=14, partial=8)
        score += _field_score(entry.pacing, brief.pacing, exact=10, partial=5)
        score += _field_score(entry.energy, brief.energy, exact=10, partial=5)

        entry_instruments = set(_casefold_all(entry.instruments_json or []))
        brief_instruments = set(_casefold_all(brief.instruments))
        score += min(20, len(entry_instruments & brief_instruments) * 10)
        if 30_000 <= int(entry.duration_ms or 0) <= 300_000:
            score += 5
        if entry.loopable:
            score += 5
        scene_score = _scene_fit_score_for_library_entry(entry, brief)
        if scene_score < 0:
            return 0
        return min(max(score, scene_score), 100)

    def reuse_match(
        self,
        db: Session,
        *,
        decision: LocalAiMusicMatchDecision,
        requesting_game_id: int,
        current_brief: MusicBrief,
    ) -> Dict[str, Any]:
        if not decision.hit or decision.entry is None or decision.entry.asset is None:
            raise ValueError("Cannot reuse a missing local AI music library match")
        entry = decision.entry
        asset = entry.asset
        self.record_reuse(
            db,
            entry=entry,
            requesting_game_id=requesting_game_id,
            score=decision.score,
            reason=decision.reason or "scene_fit",
        )
        db.flush()
        stored_brief = _brief_dict(asset.music_brief_json)
        track: Dict[str, Any] = {
            "id": f"ai-generated-{int(asset.asset_id)}",
            "name": generated_music_title(current_brief),
            "artists": ["MiniMax"],
            "album": "AI Generated",
            "duration": int(asset.duration_ms or 0),
            "url": str(asset.storage_path),
            "source": "ai_generated",
            "provider": str(asset.provider),
            "model": str(asset.model),
            "asset_id": int(asset.asset_id),
            "brief_hash": str(asset.brief_hash),
            "library_reused": True,
            "match_score": decision.score,
            "match_reason": decision.reason or "scene_fit",
        }
        prompt_version = stored_brief.get("prompt_version") or current_brief.prompt_version
        diagnostics = (
            stored_brief.get("scene_fit_diagnostics")
            or current_brief.scene_fit_diagnostics
        )
        if prompt_version:
            track["prompt_version"] = prompt_version
        if diagnostics:
            track["scene_fit_diagnostics"] = diagnostics
        return track

    def record_reuse(
        self,
        db: Session,
        *,
        entry: GeneratedMusicLibraryEntry,
        requesting_game_id: int,
        score: int,
        reason: str,
    ) -> None:
        entry.usage_count = int(entry.usage_count or 0) + 1
        entry.last_used_at = datetime.utcnow()
        entry.last_used_game_id = requesting_game_id
        entry.last_match_score = score
        entry.last_match_reason = reason
        db.add(entry)


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _brief_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _generation_settings(brief: Mapping[str, Any]) -> Dict[str, Any]:
    settings = brief.get("_generation_settings")
    return dict(settings) if isinstance(settings, Mapping) else {}


def _profile_text(brief: Mapping[str, Any], key: str, default: str) -> str:
    value = brief.get(key)
    return str(value).strip() if value else default


def _profile_list(
    brief: Mapping[str, Any],
    key: str,
    default: Iterable[str],
) -> list[str]:
    value = brief.get(key)
    if not isinstance(value, list):
        return [str(item) for item in default if item]
    return [str(item) for item in value if item]


def _casefold_all(values: Iterable[Any]) -> list[str]:
    return [str(value).strip().casefold() for value in values if str(value).strip()]


def _entry_recency_key(entry: GeneratedMusicLibraryEntry) -> tuple[datetime, int]:
    asset = entry.asset
    created_at = asset.created_at if asset is not None else entry.created_at
    if not isinstance(created_at, datetime):
        created_at = datetime.min
    return created_at, int(entry.asset_id or 0)


def _field_score(candidate: str, target: str, *, exact: int, partial: int) -> int:
    candidate_norm = str(candidate or "").casefold()
    target_norm = str(target or "").casefold()
    if not candidate_norm or not target_norm:
        return 0
    if candidate_norm == target_norm:
        return exact
    if candidate_norm in target_norm or target_norm in candidate_norm:
        return partial
    return 0


@dataclass(frozen=True)
class _LibrarySceneCandidate:
    id: int
    name: str
    artists: list[str]
    album: str


def _scene_fit_score_for_library_entry(
    entry: GeneratedMusicLibraryEntry,
    brief: MusicBrief,
) -> int:
    profile = (
        MusicSceneFitProfile.from_analysis(brief.scene_fit_profile)
        if isinstance(brief.scene_fit_profile, Mapping)
        else MusicSceneFitProfile.from_context(brief.to_analysis())
    )
    candidate = _LibrarySceneCandidate(
        id=int(entry.asset_id),
        name=" ".join(
            [
                str(entry.scene_type or ""),
                str(entry.mood or ""),
                str(entry.environment or ""),
            ]
        ),
        artists=[str(item) for item in entry.instruments_json or [] if item],
        album=" ".join(
            [
                str(entry.pacing or ""),
                str(entry.energy or ""),
                "纯音乐",
            ]
        ),
    )
    decision = MusicSceneFitScorer().score_candidate(candidate, profile)
    return -1 if decision.rejected else decision.score


def _asset_audio_exists(storage_path: str) -> bool:
    if storage_path.startswith(("https://", "http://", "/api/music/generated/")):
        return True
    return Path(storage_path).exists()


def _conflicts_with_negative_cues(
    entry: GeneratedMusicLibraryEntry,
    asset: GeneratedMusicAsset,
    brief: MusicBrief,
) -> bool:
    haystack = " ".join(
        [
            str(asset.prompt_text or ""),
            str(entry.mood or ""),
            str(entry.scene_type or ""),
            str(entry.environment or ""),
            str(entry.instruments_json or ""),
        ]
    ).casefold()
    for cue in _casefold_all(brief.negative_cues):
        if not cue or cue not in haystack:
            continue
        if f"no {cue}" in haystack or f"without {cue}" in haystack:
            continue
        if f"无{cue}" in haystack or f"不要{cue}" in haystack:
            continue
        return True
    return False
