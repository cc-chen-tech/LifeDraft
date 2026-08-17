from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
import json
from threading import RLock
from types import SimpleNamespace

import pytest

from src.ai.models import EventOption, GameEvent
from src.ai.option_generator import OptionGenerator
from src.api.schemas import ReadingContext
from src.database.models import (
    DailyRecommendedPrefetch,
    DailyWorldProjection,
    GeneratedVoiceAsset,
    Game,
    VoiceReadingJob,
    VoiceReadingSegment,
)
from src.game.daily_recommendation import prepare_daily_option_recommendation
from src.game.daily_timeline import build_daily_timeline
from src.game.round.daily_choice_processor import project_daily_choice
from src.game.round.daily_choice_processor import DailyChoiceProcessor
from src.game.round.event_generator import apply_daily_event_metadata
from src.game.state import PlayerState
from src.services.daily_recommended_prefetch_repository import (
    DailyRecommendedPrefetchRepository,
)
from src.services.daily_recommended_prefetch import (
    _prefetch_story_voice,
    _run_prefetch_worker,
    canonical_prefetch_fingerprint,
    cleanup_expired_daily_recommended_prefetch,
    ensure_daily_recommended_prefetch,
    generate_speculative_next_event,
    probe_demanded_prefetch,
    resolve_choice_prefetch,
)
from src.services.daily_world_projection import DailyWorldProjectionService
from src.services.story_tts_provider import DeterministicTTSProvider
from src.services.story_voice_reading import (
    ReadingContextValidator,
    normalize_text_hash,
)
from src.services.story_voice_repository import StoryVoiceReadingRepository

pytestmark = [pytest.mark.unit]



def _state() -> PlayerState:
    return PlayerState(
        player_name="林默",
        life_vision="经营一家让社区安心阅读的书店",
        energy=50,
        mood=50,
        knowledge=50,
        age=20,
        timeline=build_daily_timeline(start_date="2026-08-13", day_index=0),
        timeline_version=2,
        next_age_day=365,
    )


def _event() -> GameEvent:
    return GameEvent(
        event_id="day-0-event",
        revision=1,
        story_date="2026-08-13",
        event_description="社区书店的租约摆在桌上，林默必须作出选择。",
        options=[
            EventOption(text="关闭书店另寻出路", effects={"mood": -2}),
            EventOption(
                text="邀请邻居共建社区书店",
                effects={"energy": -3, "mood": 2},
            ),
            EventOption(text="暂时搁置租约", effects={"knowledge": 1}),
        ],
    )


def test_daily_recommendation_keeps_exactly_one_model_choice() -> None:
    state = _state()
    options = _event().options
    options[1].likely_choice = True

    prepared = prepare_daily_option_recommendation(options, state)

    assert [option.likely_choice for option in prepared] == [False, True, False]


def test_daily_recommendation_repairs_missing_or_multiple_flags_deterministically() -> (
    None
):
    state = _state()
    options = _event().options
    missing = prepare_daily_option_recommendation(options, state)

    options[0].likely_choice = True
    options[1].likely_choice = True
    multiple = prepare_daily_option_recommendation(options, state)

    assert [option.likely_choice for option in missing] == [False, True, False]
    assert [option.likely_choice for option in multiple] == [True, False, False]


def test_legacy_timeline_does_not_invent_a_recommendation() -> None:
    options = _event().options

    prepared = prepare_daily_option_recommendation(
        options,
        {"timeline": {"version": 1}, "life_vision": "经营社区书店"},
    )

    assert not any(option.likely_choice for option in prepared)


def test_project_daily_choice_matches_settlement_without_mutating_live_state() -> None:
    state = _state()
    event = _event()
    event.options[1].likely_choice = True
    before = deepcopy(state.model_dump())

    projection = project_daily_choice(
        state,
        event,
        option_index=1,
        language="zh",
    )

    assert state.model_dump() == before
    assert projection.state.timeline["day_index"] == 1
    assert projection.state.energy == 47
    assert projection.state.mood == 52
    assert projection.record["recommended_option_index"] == 1
    assert projection.record["recommendation_selected"] is True
    assert projection.result["next_timeline"]["current_date"] == "2026-08-14"
    assert projection.state.current_event_data is None


def test_daily_event_metadata_always_exposes_one_recommendation() -> None:
    state = _state()
    event = _event()

    prepared = apply_daily_event_metadata(event, state, language="zh")

    assert sum(option.likely_choice for option in prepared.options) == 1
    assert prepared.options[1].likely_choice is True


def test_daily_option_generation_retries_missing_recommendation_contract() -> None:
    class Client:
        model = "test-model"

        def __init__(self) -> None:
            self.calls = 0

        def call(self, **_kwargs) -> str:
            self.calls += 1
            recommended = self.calls == 2
            return json.dumps(
                {
                    "options": [
                        {
                            "text": "签下社区书店租约",
                            "effects": {"energy": -2},
                            "likely_choice": recommended,
                        },
                        {
                            "text": "邀请邻居共同商量",
                            "effects": {"mood": 2},
                            "likely_choice": False,
                        },
                        {
                            "text": "暂缓决定继续观察",
                            "effects": {"knowledge": 2},
                            "likely_choice": False,
                        },
                    ]
                },
                ensure_ascii=False,
            )

    client = Client()
    event = OptionGenerator(client).generate_options_only(
        story_description="社区书店的租约摆在桌上。",
        player_state=_state().model_dump(mode="json"),
        language="zh",
        retry_count=2,
    )

    assert client.calls == 2
    assert sum(option.likely_choice for option in event.options) == 1


def test_prefetch_repository_deduplicates_and_fences_worker_writes(db_session) -> None:
    repository = DailyRecommendedPrefetchRepository(db_session)
    identity = {
        "game_id": 41,
        "user_id": 7,
        "event_id": "day-0-event",
        "revision": 1,
        "day_index": 0,
        "option_index": 1,
        "state_fingerprint": "state-v1",
    }

    first = repository.enqueue(**identity)
    duplicate = repository.enqueue(**identity)
    first_token = repository.claim(first.prefetch_id)

    assert duplicate.prefetch_id == first.prefetch_id
    assert first_token
    assert repository.claim(first.prefetch_id) is None

    task = db_session.get(DailyRecommendedPrefetch, first.prefetch_id)
    task.lease_expires_at = datetime.utcnow() - timedelta(seconds=1)
    db_session.flush()
    replacement_token = repository.claim(first.prefetch_id)

    assert replacement_token and replacement_token != first_token
    assert (
        repository.mark_story_ready(
            first.prefetch_id,
            str(first_token),
            _event().model_dump(),
        )
        is False
    )
    assert repository.mark_story_ready(
        first.prefetch_id,
        replacement_token,
        _event().model_dump(),
    )
    assert repository.find_valid(**identity).status == "story_ready"


def test_prefetch_repository_invalidates_other_choice_and_consumes_ready_hit(
    db_session,
) -> None:
    repository = DailyRecommendedPrefetchRepository(db_session)
    task = repository.enqueue(
        game_id=42,
        user_id=None,
        event_id="day-0-event",
        revision=1,
        day_index=0,
        option_index=1,
        state_fingerprint="state-v2",
    )
    token = repository.claim(task.prefetch_id)
    assert token
    repository.mark_story_ready(task.prefetch_id, token, _event().model_dump())

    assert (
        repository.consume_if_ready(
            game_id=42,
            event_id="day-0-event",
            revision=1,
            option_index=1,
            state_fingerprint="state-v2",
        )
        is not None
    )

    other = repository.enqueue(
        game_id=42,
        user_id=None,
        event_id="day-1-event",
        revision=1,
        day_index=1,
        option_index=2,
        state_fingerprint="state-v3",
    )
    repository.invalidate_event(
        game_id=42,
        event_id="day-1-event",
        revision=1,
        selected_option_index=0,
    )

    assert (
        db_session.get(DailyRecommendedPrefetch, other.prefetch_id).status
        == "invalidated"
    )


def test_prefetch_fingerprint_is_stable_and_tracks_canonical_changes() -> None:
    state = _state()
    event = _event()

    first = canonical_prefetch_fingerprint(state, event)
    restored = canonical_prefetch_fingerprint(
        state.model_copy(deep=True), event.model_copy(deep=True)
    )
    event.revision = 2

    assert restored == first
    assert canonical_prefetch_fingerprint(state, event) != first


def test_speculative_generation_uses_projected_next_day_without_live_mutation() -> None:
    state = _state()
    event = _event()
    event.options[1].likely_choice = True
    before = deepcopy(state.model_dump())
    captured = {}

    def generate(projected_state: PlayerState) -> GameEvent:
        captured["day_index"] = projected_state.timeline["day_index"]
        captured["choice"] = projected_state.day_history[-1]["choice"]
        return GameEvent(
            event_id="day-1-prefetched",
            revision=1,
            story_date="2026-08-14",
            event_description="次日清晨，书店门前已经有人等待。",
            options=[
                EventOption(text="开门迎接", effects={}, likely_choice=True),
                EventOption(text="先观察片刻", effects={}),
            ],
        )

    next_event = generate_speculative_next_event(
        state,
        event,
        option_index=1,
        language="zh",
        generate_event=generate,
    )

    assert state.model_dump() == before
    assert captured == {"day_index": 1, "choice": "邀请邻居共建社区书店"}
    assert next_event.event_id == "day-1-prefetched"


def test_ready_recommended_choice_resolves_event_while_other_choice_invalidates(
    db_session,
) -> None:
    state = _state()
    event = _event()
    event.options[1].likely_choice = True
    fingerprint = canonical_prefetch_fingerprint(state, event)
    repository = DailyRecommendedPrefetchRepository(db_session)
    task = repository.enqueue(
        game_id=51,
        user_id=8,
        event_id=event.event_id,
        revision=event.revision,
        day_index=0,
        option_index=1,
        state_fingerprint=fingerprint,
    )
    token = repository.claim(task.prefetch_id)
    assert token
    repository.mark_story_ready(task.prefetch_id, token, _event().model_dump())

    hit = resolve_choice_prefetch(
        repository,
        game_id=51,
        state=state,
        event=event,
        option_index=1,
    )

    assert hit.next_event is not None
    assert hit.task_id == task.prefetch_id
    assert hit.recommended_selected is True

    miss = resolve_choice_prefetch(
        repository,
        game_id=51,
        state=state,
        event=event,
        option_index=0,
    )

    assert miss.next_event is None
    assert miss.recommended_selected is False
    assert (
        db_session.get(DailyRecommendedPrefetch, task.prefetch_id).status
        == "invalidated"
    )


def test_inflight_recommended_choice_marks_task_demanded_without_duplicate(
    db_session,
) -> None:
    state = _state()
    event = _event()
    event.options[1].likely_choice = True
    repository = DailyRecommendedPrefetchRepository(db_session)
    task = repository.enqueue(
        game_id=52,
        user_id=None,
        event_id=event.event_id,
        revision=event.revision,
        day_index=0,
        option_index=1,
        state_fingerprint=canonical_prefetch_fingerprint(state, event),
    )

    resolution = resolve_choice_prefetch(
        repository,
        game_id=52,
        state=state,
        event=event,
        option_index=1,
    )

    assert resolution.next_event is None
    assert resolution.task_id == task.prefetch_id
    assert db_session.get(DailyRecommendedPrefetch, task.prefetch_id).demanded is True


def test_repository_finds_only_the_demanded_task_for_committed_choice(
    db_session,
) -> None:
    repository = DailyRecommendedPrefetchRepository(db_session)
    task = repository.enqueue(
        game_id=53,
        user_id=None,
        event_id="day-0-event",
        revision=1,
        day_index=0,
        option_index=1,
        state_fingerprint="committed-choice",
    )
    task.demanded = True
    db_session.flush()

    found = repository.find_demanded_after_choice(
        game_id=53,
        event_id="day-0-event",
        revision=1,
        option_index=1,
        day_index=0,
    )

    assert found is not None
    assert found.prefetch_id == task.prefetch_id
    assert (
        repository.find_demanded_after_choice(
            game_id=53,
            event_id="day-0-event",
            revision=1,
            option_index=0,
            day_index=0,
        )
        is None
    )


def test_terminal_prefetch_cleanup_keeps_recent_rows_for_seven_days(
    db_engine, monkeypatch
) -> None:
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=db_engine)
    setup = Session()
    repository = DailyRecommendedPrefetchRepository(setup)
    expired = repository.enqueue(
        game_id=54,
        user_id=None,
        event_id="expired",
        revision=1,
        day_index=0,
        option_index=1,
        state_fingerprint="expired",
    )
    recent = repository.enqueue(
        game_id=54,
        user_id=None,
        event_id="recent",
        revision=1,
        day_index=1,
        option_index=1,
        state_fingerprint="recent",
    )
    expired.status = "invalidated"
    recent.status = "failed"
    reference_time = datetime.utcnow()
    expired.updated_at = reference_time - timedelta(days=8)
    recent.updated_at = reference_time - timedelta(days=6)
    expired_id = expired.prefetch_id
    recent_id = recent.prefetch_id
    setup.commit()
    setup.close()
    monkeypatch.setattr("src.database.models.SessionLocal", Session)

    removed = cleanup_expired_daily_recommended_prefetch(now=reference_time)

    observer = Session()
    try:
        assert removed == 1
        assert observer.get(DailyRecommendedPrefetch, expired_id) is None
        assert observer.get(DailyRecommendedPrefetch, recent_id) is not None
    finally:
        observer.close()


def test_expired_prefetch_cleanup_removes_audio_and_subtitle_sidecar(
    db_engine, monkeypatch, tmp_path
) -> None:
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=db_engine)
    asset_dir = tmp_path / "voice-assets"
    asset_dir.mkdir()
    audio_path = asset_dir / "prefetched-chapter.mp3"
    subtitle_path = asset_dir / "prefetched-chapter.srt"
    audio_path.write_bytes(b"ID3-prefetched-audio")
    subtitle_path.write_text("1\n00:00:00,000 --> 00:00:01,000\n故事。\n")
    monkeypatch.setenv("STORY_TTS_ASSET_DIR", str(asset_dir))

    setup = Session()
    task = DailyRecommendedPrefetchRepository(setup).enqueue(
        game_id=55,
        user_id=9,
        event_id="expired-ready",
        revision=1,
        day_index=0,
        option_index=1,
        state_fingerprint="expired-ready",
    )
    task.status = "ready"
    asset = GeneratedVoiceAsset(
        user_id=9,
        source_type="recommended_prefetch",
        context_json={"text_hash": "prefetched-text"},
        text_hash="prefetched-text",
        voice_id="warm_female",
        speed=1.0,
        provider="minimax",
        model="speech-2.8-turbo",
        storage_path="/api/voice-reading/audio/prefetched-chapter.mp3",
        duration_ms=1_000,
        status="ready",
    )
    setup.add(asset)
    setup.flush()
    job = VoiceReadingJob(
        user_id=9,
        asset_id=asset.asset_id,
        context_json={"text_hash": "prefetched-text"},
        text_hash="prefetched-text",
        voice_id="warm_female",
        speed=1.0,
        status="ready",
    )
    setup.add(job)
    setup.flush()
    setup.add(
        VoiceReadingSegment(
            job_id=job.job_id,
            asset_id=asset.asset_id,
            paragraph_index=0,
            text_hash="paragraph-text",
            text_content="故事。",
            status="ready",
        )
    )
    task.tts_job_id = job.job_id
    task.updated_at = datetime.utcnow() - timedelta(days=8)
    setup.commit()
    setup.close()
    monkeypatch.setattr("src.database.models.SessionLocal", Session)

    removed = cleanup_expired_daily_recommended_prefetch(now=datetime.utcnow())

    assert removed == 1
    assert not audio_path.exists()
    assert not subtitle_path.exists()


def test_ready_prefetch_is_promoted_inside_atomic_daily_settlement() -> None:
    state = _state()
    event = _event()
    event.options[1].likely_choice = True
    next_event = GameEvent(
        event_id="day-1-prefetched",
        revision=1,
        story_date="2026-08-14",
        event_description="第二天的故事已经准备好。",
        options=[
            EventOption(text="继续", effects={}, likely_choice=True),
            EventOption(text="停下", effects={}),
        ],
    )
    holder = {"event": event}
    persisted = []
    processor = DailyChoiceProcessor(
        player_state_getter=lambda: state,
        current_event_getter=lambda: holder["event"],
        current_event_setter=lambda value: holder.__setitem__("event", value),
    )

    result = processor.make_choice(
        event_id=event.event_id,
        revision=event.revision,
        option_index=1,
        persist_callback=lambda candidate: persisted.append(candidate.model_dump())
        or True,
        prefetched_event=next_event,
    )

    assert result["prefetch_hit"] is True
    assert persisted[0]["current_event_data"]["event_id"] == "day-1-prefetched"
    assert state.current_event_data["event_id"] == "day-1-prefetched"
    assert holder["event"].event_id == "day-1-prefetched"


def test_tts_validator_accepts_internal_recommended_prefetch_source() -> None:
    text = "预生成语音只包含下一日故事正文。"
    context = ReadingContext(
        source_type="recommended_prefetch",
        game_id=61,
        week=0,
        round_number=1,
        stage="event",
        day_index=1,
        story_date="2026-08-14",
        text_hash=normalize_text_hash(text),
        text=text,
    )

    validated = ReadingContextValidator().validate(
        context, allow_recommended_prefetch=True
    )

    assert validated["source_type"] == "recommended_prefetch"

    with pytest.raises(Exception) as error:
        ReadingContextValidator().validate(context)
    assert (
        getattr(error.value, "detail", {}).get("error_code") == "internal_source_only"
    )


def test_prefetch_worker_persists_story_without_mutating_unselected_live_state(
    db_engine, monkeypatch
) -> None:
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=db_engine)
    setup = Session()
    state = _state()
    event = _event()
    event.options[1].likely_choice = True
    repository = DailyRecommendedPrefetchRepository(setup)
    task = repository.enqueue(
        game_id=71,
        user_id=None,
        event_id=event.event_id,
        revision=event.revision,
        day_index=0,
        option_index=1,
        state_fingerprint=canonical_prefetch_fingerprint(state, event),
    )
    task_id = task.prefetch_id
    setup.commit()
    setup.close()
    live_before = deepcopy(state.model_dump())
    source_loop = SimpleNamespace(
        language="zh",
        player_state=state,
        current_event=event,
        _daily_mutation_lock=RLock(),
    )
    next_event = GameEvent(
        event_id="day-1-prefetched",
        revision=1,
        story_date="2026-08-14",
        event_description="次日故事已在后台完成。",
        options=[
            EventOption(text="继续", effects={}, likely_choice=True),
            EventOption(text="停下", effects={}),
        ],
    )
    monkeypatch.setattr("src.database.models.SessionLocal", Session)
    monkeypatch.setattr(
        "src.services.daily_recommended_prefetch._generate_with_isolated_game_loop",
        lambda _loop, projected: next_event,
    )

    _run_prefetch_worker(
        task_id=task_id,
        source_loop=source_loop,
        snapshot_state=state.model_copy(deep=True),
        snapshot_event=event.model_copy(deep=True),
        option_index=1,
        language="zh",
        user_id=None,
        game_id=71,
    )

    observer = Session()
    try:
        stored = observer.get(DailyRecommendedPrefetch, task_id)
        assert stored.status == "story_ready"
        assert stored.next_event_json["event_id"] == "day-1-prefetched"
        assert state.model_dump() == live_before
    finally:
        observer.close()


def test_enqueue_snapshots_auto_read_voice_and_speed_at_task_creation(
    db_engine, monkeypatch
) -> None:
    from sqlalchemy.orm import sessionmaker

    from config.feature_flags import reset_features, set_feature

    Session = sessionmaker(bind=db_engine, expire_on_commit=False)
    setup = Session()
    StoryVoiceReadingRepository(setup).upsert_settings(12, "clear_neutral", True, 1.1)
    setup.commit()
    setup.close()
    state = _state()
    event = _event()
    event.options[1].likely_choice = True
    callbacks = []
    source_loop = SimpleNamespace(
        language="zh",
        player_state=state,
        current_event=event,
    )
    monkeypatch.setattr("src.database.models.SessionLocal", Session)
    set_feature("daily_recommended_prefetch", True)
    set_feature("daily_recommended_tts_prefetch", True)
    try:
        task_id = ensure_daily_recommended_prefetch(
            game_id=74,
            user_id=12,
            game_loop=source_loop,
            submitter=callbacks.append,
        )
    finally:
        reset_features()

    observer = Session()
    try:
        task = observer.get(DailyRecommendedPrefetch, task_id)
        assert task.voice_id == "clear_neutral"
        assert task.voice_speed == 1.1
        assert len(callbacks) == 1
    finally:
        observer.close()


def test_demanded_prefetch_recovers_from_committed_state_without_second_pipeline(
    db_engine, monkeypatch
) -> None:
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=db_engine)
    original = _state()
    event = _event()
    event.options[1].likely_choice = True
    projected = project_daily_choice(
        original, event, option_index=1, language="zh"
    ).state
    setup = Session()
    task = DailyRecommendedPrefetchRepository(setup).enqueue(
        game_id=73,
        user_id=None,
        event_id=event.event_id,
        revision=event.revision,
        day_index=0,
        option_index=1,
        state_fingerprint=canonical_prefetch_fingerprint(original, event),
    )
    task.demanded = True
    task_id = task.prefetch_id
    setup.commit()
    setup.close()
    source_loop = SimpleNamespace(
        language="zh",
        player_state=projected,
        current_event=None,
        _daily_mutation_lock=RLock(),
    )
    next_event = GameEvent(
        event_id="day-1-recovered",
        revision=1,
        story_date="2026-08-14",
        event_description="重启后仍接管同一个推荐分支任务。",
        options=[
            EventOption(text="继续", effects={}, likely_choice=True),
            EventOption(text="停下", effects={}),
        ],
    )
    callbacks = []
    saves = []
    monkeypatch.setattr("src.database.models.SessionLocal", Session)
    monkeypatch.setattr(
        "src.services.daily_recommended_prefetch._generate_with_isolated_game_loop",
        lambda _loop, state: next_event,
    )
    monkeypatch.setattr(
        "src.database.singletons.get_game_db",
        lambda: SimpleNamespace(
            save_game_progress=lambda game_id, state: saves.append(
                (game_id, state.current_event_data["event_id"])
            )
            or True
        ),
    )

    pending = probe_demanded_prefetch(
        game_id=73,
        game_loop=source_loop,
        submitter=callbacks.append,
    )
    assert pending.pending is True
    assert len(callbacks) == 1

    callbacks[0]()

    observer = Session()
    try:
        stored = observer.get(DailyRecommendedPrefetch, task_id)
        assert stored.status == "consumed"
        assert stored.next_event_json["event_id"] == "day-1-recovered"
        assert source_loop.current_event.event_id == "day-1-recovered"
        assert saves == [(73, "day-1-recovered")]
    finally:
        observer.close()


@pytest.mark.parametrize(
    ("save_result", "expected_promoted", "expected_projection_rows"),
    [(False, False, 0), (True, True, 1)],
)
def test_promoted_prefetch_enqueues_only_after_successful_save(
    db_engine,
    monkeypatch,
    save_result: bool,
    expected_promoted: bool,
    expected_projection_rows: int,
) -> None:
    """A failed promotion save must not create a projection for an absent event."""
    from sqlalchemy.orm import sessionmaker

    from src.services.daily_recommended_prefetch import _promote_demanded_prefetch

    Session = sessionmaker(bind=db_engine)
    with Session() as setup:
        setup.add(Game(game_id=158, initial_state={}))
        task = DailyRecommendedPrefetchRepository(setup).enqueue(
            game_id=158,
            user_id=None,
            event_id="day-0-event",
            revision=1,
            day_index=0,
            option_index=1,
            state_fingerprint="accepted-choice",
        )
        task.demanded = True
        task.status = "story_ready"
        task.next_event_json = GameEvent(
            event_id="day-1-event",
            revision=1,
            story_date="2026-08-14",
            event_description="清晨，林默打开书店的门。",
            options=[
                EventOption(text="整理新书", effects={}),
                EventOption(text="招呼邻居", effects={}),
            ],
        ).model_dump()
        task_id = task.prefetch_id
        setup.commit()

    state = project_daily_choice(
        _state(), _event(), option_index=1, language="zh"
    ).state
    source_loop = SimpleNamespace(
        language="zh",
        player_state=state,
        current_event=None,
        _daily_mutation_lock=RLock(),
    )
    service = DailyWorldProjectionService(session_factory=Session)
    monkeypatch.setattr("src.database.models.SessionLocal", Session)
    monkeypatch.setattr(
        "src.database.singletons.get_game_db",
        lambda: SimpleNamespace(save_game_progress=lambda *_args: save_result),
    )
    monkeypatch.setattr(
        "src.services.daily_world_projection.get_daily_world_projection_service",
        lambda: service,
    )

    assert (
        _promote_demanded_prefetch(task_id=task_id, game_id=158, game_loop=source_loop)
        is expected_promoted
    )

    with Session() as observer:
        assert observer.query(DailyWorldProjection).count() == expected_projection_rows


def test_promoted_prefetch_stays_promoted_when_task_bookkeeping_commit_fails(
    db_engine, monkeypatch
) -> None:
    """A post-save task failure must not report a second-generation retry path."""
    from sqlalchemy.orm import Session, sessionmaker

    from src.services.daily_recommended_prefetch import _promote_demanded_prefetch

    SessionFactory = sessionmaker(bind=db_engine)
    with SessionFactory() as setup:
        setup.add(Game(game_id=163, initial_state={}))
        task = DailyRecommendedPrefetchRepository(setup).enqueue(
            game_id=163,
            user_id=None,
            event_id="day-0-event",
            revision=1,
            day_index=0,
            option_index=1,
            state_fingerprint="accepted-choice",
        )
        task.demanded = True
        task.status = "story_ready"
        task.next_event_json = GameEvent(
            event_id="day-1-event",
            revision=1,
            story_date="2026-08-14",
            event_description="清晨，林默打开书店的门。",
            options=[
                EventOption(text="整理新书", effects={}),
                EventOption(text="招呼邻居", effects={}),
            ],
        ).model_dump()
        task_id = task.prefetch_id
        setup.commit()

    class CommitFailsSession(Session):
        def commit(self) -> None:
            raise RuntimeError("task bookkeeping commit failed")

    failing_sessions = sessionmaker(bind=db_engine, class_=CommitFailsSession)
    state = project_daily_choice(
        _state(), _event(), option_index=1, language="zh"
    ).state
    source_loop = SimpleNamespace(
        language="zh",
        player_state=state,
        current_event=None,
        _daily_mutation_lock=RLock(),
    )
    service = DailyWorldProjectionService(session_factory=SessionFactory)
    monkeypatch.setattr("src.database.models.SessionLocal", failing_sessions)
    monkeypatch.setattr(
        "src.database.singletons.get_game_db",
        lambda: SimpleNamespace(save_game_progress=lambda *_args: True),
    )
    monkeypatch.setattr(
        "src.services.daily_world_projection.get_daily_world_projection_service",
        lambda: service,
    )

    assert (
        _promote_demanded_prefetch(task_id=task_id, game_id=163, game_loop=source_loop)
        is True
    )
    assert source_loop.current_event is not None
    assert source_loop.current_event.event_id == "day-1-event"

    with SessionFactory() as observer:
        assert observer.get(DailyRecommendedPrefetch, task_id).status == "story_ready"
        assert observer.query(DailyWorldProjection).count() == 1


def test_tts_prefetch_uses_saved_auto_read_voice_and_marks_task_ready(
    db_engine, monkeypatch
) -> None:
    from sqlalchemy.orm import sessionmaker

    from config.feature_flags import reset_features, set_feature

    Session = sessionmaker(bind=db_engine)
    setup = Session()
    repository = DailyRecommendedPrefetchRepository(setup)
    task = repository.enqueue(
        game_id=72,
        user_id=9,
        event_id="day-0-event",
        revision=1,
        day_index=0,
        option_index=1,
        state_fingerprint="tts-state",
        voice_id="calm_male",
        voice_speed=1.25,
    )
    task.status = "story_ready"
    task.next_event_json = _event().model_dump()
    StoryVoiceReadingRepository(setup).upsert_settings(9, "calm_male", True, 1.25)
    # The task owns a creation-time snapshot; later user changes must not
    # silently retarget already queued speculative work.
    StoryVoiceReadingRepository(setup).upsert_settings(9, "warm_female", False, 0.9)
    task_id = task.prefetch_id
    setup.commit()
    setup.close()
    projected = project_daily_choice(
        _state(), _event(), option_index=1, language="zh"
    ).state
    next_event = GameEvent(
        event_id="day-1-prefetched",
        revision=1,
        story_date="2026-08-14",
        event_description="第一段已经准备好。\n\n第二段也会继续生成。",
        options=[
            EventOption(text="继续", effects={}, likely_choice=True),
            EventOption(text="停下", effects={}),
        ],
    )
    monkeypatch.setattr("src.database.models.SessionLocal", Session)
    monkeypatch.setattr(
        "src.services.story_voice_reading.build_story_tts_provider",
        lambda: DeterministicTTSProvider(),
    )
    set_feature("daily_recommended_tts_prefetch", True)
    try:
        _prefetch_story_voice(
            task_id=task_id,
            user_id=9,
            game_id=72,
            projected_state=projected,
            event=next_event,
            voice_id="calm_male",
            speed=1.25,
        )
    finally:
        reset_features()

    observer = Session()
    try:
        stored = observer.get(DailyRecommendedPrefetch, task_id)
        job = observer.get(VoiceReadingJob, stored.tts_job_id)
        assert stored.status == "ready"
        assert stored.voice_id == "calm_male"
        assert stored.voice_speed == 1.25
        assert job.context_json["source_type"] == "recommended_prefetch"
        assert job.status == "ready"
    finally:
        observer.close()
