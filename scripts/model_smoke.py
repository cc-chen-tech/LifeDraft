#!/usr/bin/env python3
"""Protected release smoke for real text, image, TTS, and projection providers.

This script intentionally records only check metadata.  Model prompts and
responses are never written to the report or to the smoke log.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional
from urllib.request import Request, urlopen


# Direct CLI execution sets sys.path[0] to scripts/, not the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPORT_SCHEMA_VERSION = 1
FIXTURE_PREFIX = "release-model-smoke"


class ModelEventCollector(logging.Handler):
    """Mirror safe model events to stdout and retain aggregate evidence."""

    def __init__(self, event_log_path: Optional[Path] = None) -> None:
        super().__init__(level=logging.INFO)
        self.events: List[Dict[str, Any]] = []
        self._event_log = (
            event_log_path.open("a", encoding="utf-8") if event_log_path is not None else None
        )

    def emit(self, record: logging.LogRecord) -> None:
        event = getattr(record, "model_event", None)
        if not isinstance(event, dict):
            return
        self.events.append(dict(event))
        line = json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
        sys.stdout.write(line)
        sys.stdout.flush()
        if self._event_log is not None:
            self._event_log.write(line)
            self._event_log.flush()

    def close(self) -> None:
        if self._event_log is not None:
            self._event_log.close()
            self._event_log = None
        super().close()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_error(error: BaseException) -> Dict[str, Any]:
    try:
        from src.observability.model_telemetry import classify_model_error, sanitize_error_message

        return {
            "error_kind": classify_model_error(error),
            "error_message": sanitize_error_message(error),
        }
    except Exception:
        # Startup failures must still produce a report, without raw error text.
        return {"error_kind": "unknown", "error_message": type(error).__name__}


def _check(
    checks: List[Dict[str, Any]],
    name: str,
    provider: str,
    model: str,
    callback: Callable[[], Dict[str, Any]],
) -> None:
    started = time.monotonic()
    result: Dict[str, Any] = {
        "name": name,
        "provider": provider,
        "model": model,
        "outcome": "failed",
    }
    try:
        details = callback()
        if details:
            result["details"] = details
        result["outcome"] = "passed"
    except Exception as error:
        result.update(_safe_error(error))
    result["duration_ms"] = round((time.monotonic() - started) * 1000, 2)
    checks.append(result)
    print(json.dumps({"smoke_check": result}, ensure_ascii=False), flush=True)


def _require_real_credentials() -> None:
    if os.getenv("MODEL_SMOKE_ENABLED") != "1":
        raise RuntimeError("MODEL_SMOKE_ENABLED=1 is required")
    required = ("OPENAI_API_KEY", "MINIMAX_API_KEY")
    for name in required:
        value = os.getenv(name, "").strip()
        if not value or value.lower() in {"dummy", "test-key", "dummy-key-for-testing"}:
            raise RuntimeError(f"{name} must be a real provider secret")
    if any(token in os.getenv(name, "").lower() for name in required for token in ("dummy", "test-key")):
        raise RuntimeError("deterministic or dummy provider credentials are forbidden")
    if os.getenv("E2E_DETERMINISTIC_STORY", "0").lower() in {"1", "true", "yes", "on"}:
        raise RuntimeError("E2E_DETERMINISTIC_STORY must be disabled for model smoke")
    if os.getenv("MINIMAX_E2E_LOCAL_AUDIO", "0").lower() in {"1", "true", "yes", "on"}:
        raise RuntimeError("MINIMAX_E2E_LOCAL_AUDIO must be disabled for model smoke")
    if os.getenv("MINIMAX_E2E_LOCAL_IMAGE", "0").lower() in {"1", "true", "yes", "on"}:
        raise RuntimeError("MINIMAX_E2E_LOCAL_IMAGE must be disabled for model smoke")


def _configure_safe_logging(event_log_path: Optional[Path] = None) -> ModelEventCollector:
    from config.logging_config import setup_logging
    from src.observability.model_telemetry import configure_model_logging

    setup_logging(log_level=os.getenv("LOG_LEVEL", "INFO"), log_to_file=False, json_output=True)
    model_logger = configure_model_logging()
    if event_log_path is not None:
        event_log_path.parent.mkdir(parents=True, exist_ok=True)
    collector = ModelEventCollector(event_log_path)
    for handler in model_logger.handlers[:]:
        model_logger.removeHandler(handler)
        handler.close()
    model_logger.addHandler(collector)
    return collector


def _run_text_checks(generator: Any) -> Dict[str, Any]:
    from src.observability.request_context import RequestContext, request_context

    context = RequestContext(
        request_id=f"{FIXTURE_PREFIX}-{uuid.uuid4().hex}",
        operation_id=f"{FIXTURE_PREFIX}:text",
        feature="release_model_smoke",
    )
    with request_context(context):
        story = generator.generate_completion(
            "Write a short fictional opening about a traveler finding a sealed observatory."
            " Return only the story text.",
            system_prompt="You are a production story writer. Do not mention this test.",
            language="en",
            retry_count=1,
            max_tokens=240,
            thinking=False,
        )
        if not story or not story.strip():
            raise ValueError("empty story output")
        continuation = generator.generate_completion(
            "Continue the fictional story in two concise sentences, preserving the observatory setting.",
            system_prompt="You are continuing a production story.",
            language="en",
            retry_count=1,
            max_tokens=180,
            thinking=False,
        )
        if not continuation or not continuation.strip():
            raise ValueError("empty continuation output")
        options = generator.generate_options_only(
            story_description=story,
            player_state={"week": 0, "age": 22, "energy": 70, "mood": 60, "knowledge": 50},
            character_settings={"name": "Release Smoke Traveler"},
            language="en",
            retry_count=1,
        )
        if options is None or len(options.options) < 2 or len(options.options) > 4:
            raise ValueError("invalid options structure")
        if any(not option.text.strip() or not isinstance(option.effects, dict) for option in options.options):
            raise ValueError("option constraint validation failed")
        parsed = generator.generate_completion_json(
            'Return exactly this JSON shape with a boolean ok field and one short item: '
            '{"ok": true, "items": ["ready"]}.',
            system_prompt="Return valid JSON only.",
            max_tokens=120,
            thinking=False,
        )
        if not isinstance(parsed, dict) or parsed.get("ok") is not True:
            raise ValueError("invalid JSON output")
    return {"story_nonempty": True, "continuation_nonempty": True, "options": len(options.options), "json_ok": True}


def _create_owned_fixture() -> tuple[int, int]:
    from src.database.models import Game, SessionLocal, User

    with SessionLocal() as session:
        user = User(private_id=uuid.uuid4().hex, public_id=uuid.uuid4().hex[:8],
                    display_name="Release Smoke Traveler")
        session.add(user)
        session.flush()
        game = Game(user_id=user.user_id, language="en", initial_state={})
        session.add(game)
        session.commit()
        return int(user.user_id), int(game.game_id)


def _read_owned_resource(base_url: str, resource_path: str, user_id: int) -> None:
    from src.api.deps import create_token

    request = Request(
        f"{base_url.rstrip('/')}{resource_path}",
        headers={"Authorization": f"Bearer {create_token(user_id)}"},
    )
    with urlopen(request, timeout=20) as response:  # nosec B310 - isolated smoke API
        if response.status != 200 or not response.read(32):
            raise IOError("generated resource is not accessible")


def _run_image_check(generator: Any, storage_dir: Path, base_url: Optional[str]) -> Dict[str, Any]:
    from src.database.models import Image, SessionLocal
    from src.observability.request_context import RequestContext, request_context
    from src.services.image_storage import ImageStorageService

    with request_context(
        RequestContext(
            request_id=f"{FIXTURE_PREFIX}-{uuid.uuid4().hex}",
            operation_id=f"{FIXTURE_PREFIX}:image",
            feature="release_model_smoke",
        )
    ):
        image_bytes, _ = generator.generate_image(
            "A simple red paper kite against a clear blue sky, minimal composition.",
            size="512*512",
            extra_params={"response_format": "base64"},
        )
        if not image_bytes:
            raise ValueError("empty image output")
        user_id, game_id = _create_owned_fixture()
        storage = ImageStorageService(storage_type="local", local_path=storage_dir)
        storage_path, storage_type = storage.save_image(
            image_bytes,
            game_id=game_id,
            image_type="release_smoke",
            entity_name="fixed-fixture",
        )
        if storage_type != "local" or not storage.image_exists(storage_path, storage_type):
            raise IOError("image was not persisted")
        loaded = storage.get_image_data(storage_path, storage_type)
        if not loaded:
            raise IOError("persisted image could not be read")
        resource_path = storage.get_image_url(storage_path, storage_type)
        with SessionLocal() as session:
            row = Image(game_id=game_id, image_type="release_smoke", entity_name="fixed-fixture",
                        prompt_text="Fixed synthetic kite fixture", storage_path=storage_path,
                        storage_type=storage_type)
            session.add(row)
            session.commit()
            session.refresh(row)
            if row.storage_path != storage_path:
                raise IOError("image database persistence failed")
        if base_url:
            _read_owned_resource(base_url, resource_path, user_id)
    return {"bytes": len(image_bytes), "persisted": True, "resource_accessible": bool(base_url)}


def _run_tts_check(provider: Any, base_url: Optional[str] = None) -> Dict[str, Any]:
    from src.api.schemas import StoryVoiceReadingRequest
    from src.database.models import GeneratedVoiceAsset, SessionLocal
    from src.services.story_voice_reading import StoryVoiceReadingService, normalize_text_hash
    from src.services.story_voice_repository import StoryVoiceReadingRepository
    from src.observability.request_context import RequestContext, request_context

    with request_context(
        RequestContext(
            request_id=f"{FIXTURE_PREFIX}-{uuid.uuid4().hex}",
            operation_id=f"{FIXTURE_PREFIX}:tts",
            feature="release_model_smoke",
        )
    ):
        user_id, game_id = _create_owned_fixture()
        text = "旅人推开观星台的门，星光照亮了桌上的地图。"
        with SessionLocal() as session:
            service = StoryVoiceReadingService(StoryVoiceReadingRepository(session), provider=provider)
            queued = service.request_reading(user_id, StoryVoiceReadingRequest(context={
                "source_type": "current_story", "game_id": game_id, "week": 1,
                "round_number": 1, "stage": "event", "attempt_id": "release-smoke",
                "text_hash": normalize_text_hash(text), "text": text,
            }))
            completed = service.process_job(user_id, int(queued.job_id))
            if completed.status != "ready" or completed.asset_id is None:
                raise RuntimeError("production scene narration job did not finish ready")
            asset = session.query(GeneratedVoiceAsset).filter_by(asset_id=completed.asset_id).one()
            if asset.status != "ready" or not provider.is_valid_cached_asset(asset.storage_path):
                raise ValueError("persisted narration audio is not playable")
            if base_url:
                _read_owned_resource(base_url, asset.storage_path, user_id)
            duration_ms = int(asset.duration_ms)
    return {"duration_ms": duration_ms, "persisted": True, "playable": True, "job_status": "ready"}


def _run_projection_check(generator: Any) -> Dict[str, Any]:
    from src.database.models import (
        DailyWorldProjection,
        DailyWorldProjectionAttempt,
        Game,
        SessionLocal,
        init_db,
    )
    from src.services.daily_world_projection import DailyWorldProjectionService

    init_db()
    session = SessionLocal()
    game: Optional[Game] = None
    try:
        story = "The traveler opens the observatory and records a new star map."
        options = [
            {"text": "Record the map", "effects": {}},
            {"text": "Leave the observatory", "effects": {}},
        ]
        event = SimpleNamespace(
            event_id="release-smoke-event",
            revision=1,
            day_index=0,
            story_date="2099-01-01",
            event_description=story,
            options=options,
        )
        state = SimpleNamespace(
            timeline={"version": 2, "day_index": 0, "current_date": "2099-01-01"}
        )
        game = Game(
            user_id=None,
            language="en",
            initial_state={
                "player_name": "Release Smoke Traveler",
                "timeline": state.timeline,
                "current_event_data": {
                    "event_id": event.event_id,
                    "revision": event.revision,
                    "event_description": story,
                    "options": options,
                },
            },
        )
        session.add(game)
        session.commit()
        game_id = int(game.game_id)
    finally:
        session.close()

    source = {"revision": 1, "story": story, "options": options, "tracked_state": {"player_name": "Release Smoke Traveler"}}
    service = DailyWorldProjectionService(
        extractor=lambda source_story, source_options, tracked_state: generator.extract_daily_world_projection(
            source_story, list(source_options), tracked_state, language="en", retry_count=1
        ),
        canonical_loader=lambda _game_id, _event_id, _revision: source,
        scan_seconds=0.01,
    )
    service.ensure_world_projection(game_id, event, state)
    if service.run_once() != 1:
        raise RuntimeError("daily projection claim was not processed")

    session = SessionLocal()
    try:
        projection = (
            session.query(DailyWorldProjection)
            .filter(DailyWorldProjection.game_id == game_id)
            .one()
        )
        attempt = (
            session.query(DailyWorldProjectionAttempt)
            .filter(DailyWorldProjectionAttempt.game_id == game_id)
            .order_by(DailyWorldProjectionAttempt.attempt_id.desc())
            .first()
        )
        if projection.status not in {"ready", "ready_no_change"}:
            raise RuntimeError("daily projection was not persisted as ready")
        if attempt is None or attempt.outcome != "success":
            raise RuntimeError("daily projection attempt did not finish successfully")
        if not isinstance(projection.story_patch_json, dict) or not isinstance(
            projection.option_patches_json, dict
        ):
            raise ValueError("daily projection payload was not persisted")
    finally:
        session.close()
    return {"projection_status": projection.status, "attempt_outcome": attempt.outcome}


def _build_report(
    checks: List[Dict[str, Any]],
    events: List[Dict[str, Any]],
    started_at: str,
) -> Dict[str, Any]:
    """Build the stable, payload-free report consumed by CI and Playwright."""

    fallback_events = [event for event in events if event.get("fallback_from")]
    failed_events = [event for event in events if event.get("outcome") == "failure"]
    provider_failures = [event for event in failed_events if event.get("phase") == "provider"]
    unknown_events = [event for event in failed_events if event.get("error_kind") == "unknown"]
    warnings: List[str] = []
    errors: List[str] = []
    if provider_failures and not unknown_events:
        warnings.append("provider_retry_observed")
    if fallback_events:
        errors.append("fallback_requires_manual_confirmation")
    if unknown_events:
        errors.append("unclassified_model_error")
    if not all(check.get("outcome") == "passed" for check in checks):
        errors.append("one_or_more_smoke_checks_failed")

    status = "passed" if not errors else "failed"
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "status": status,
        "started_at": started_at,
        "finished_at": _utc_now(),
        "fixture": FIXTURE_PREFIX,
        "checks": checks,
        "warnings": sorted(set(warnings)),
        "errors": sorted(set(errors)),
        "model_events": {
            "count": len(events),
            "success_count": sum(event.get("outcome") == "success" for event in events),
            "failure_count": len(failed_events),
            "fallback_count": len(fallback_events),
            "unknown_error_count": len(unknown_events),
        },
    }


def run(
    report_path: Path,
    artifact_dir: Path,
    base_url: Optional[str],
    event_log_path: Optional[Path] = None,
) -> int:
    _require_real_credentials()

    from src.ai.generator import EventGenerator
    from src.ai.image_generator import ImageGenerator
    from src.services.minimax_story_tts_provider import MiniMaxTTSProvider

    report_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    collector = _configure_safe_logging(event_log_path)
    checks: List[Dict[str, Any]] = []
    started_at = _utc_now()
    generator = EventGenerator(use_cache=False)
    image_generator = ImageGenerator()
    tts_provider = MiniMaxTTSProvider()

    _check(checks, "text_generation_and_constraints", "openai-compatible", generator.ai_client.model, lambda: _run_text_checks(generator))
    _check(checks, "image_generation_persistence_and_resource", "minimax", image_generator.model, lambda: _run_image_check(image_generator, artifact_dir / "images", base_url))
    _check(checks, "tts_generation_persistence_and_playability", "minimax", tts_provider.model, lambda: _run_tts_check(tts_provider, base_url))
    _check(checks, "daily_world_projection_persistence", "openai-compatible", generator.ai_client.model, lambda: _run_projection_check(generator))

    report = _build_report(checks, collector.events, started_at)
    status = report["status"]
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if status == "passed" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=Path("smoke-summary.json"))
    parser.add_argument("--artifact-dir", type=Path, default=Path("model-smoke-artifacts"))
    parser.add_argument("--events", type=Path, default=None)
    parser.add_argument("--base-url", default=os.getenv("MODEL_SMOKE_BASE_URL"))
    args = parser.parse_args()
    try:
        return run(args.report, args.artifact_dir, args.base_url, args.events)
    except Exception as error:
        report = {
            "schema_version": REPORT_SCHEMA_VERSION,
            "status": "failed",
            "started_at": _utc_now(),
            "finished_at": _utc_now(),
            "fixture": FIXTURE_PREFIX,
            "checks": [],
            "warnings": [],
            "errors": ["smoke_runner_failed"],
            "runner_error": _safe_error(error),
            "model_events": {"count": 0, "success_count": 0, "failure_count": 0, "fallback_count": 0, "unknown_error_count": 0},
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
