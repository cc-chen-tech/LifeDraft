# PR 2: Versioned Async World Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Start durable, revision-fenced world extraction immediately after each accepted daily story, precompute story/option patches during reading, apply settled patches in day order, and recover extraction failures without blocking player choice or the next story.

**Architecture:** Persist one projection job per accepted `(game, event, revision)`, claimed through database leases by a lifespan-managed worker. Store materialized derived world state separately in `PlayerState.world_projection_state`; existing mixed world fields remain legacy soft hints. Choice settlement consumes a ready projection if available or records the projection identity for the serial applier to finish later.

**Tech Stack:** Python 3, SQLAlchemy, Pydantic, FastAPI lifespan, threading, pytest, existing Story2 AI generator and game-state repository.

**Spec:** `docs/superpowers/specs/2026-08-16-versioned-async-world-projection-design.md`

## Global Constraints

- PR 1 must already be merged; its generation-intent and provisional freshness interfaces remain compatible.
- Story persistence completes before projection enqueue; enqueue failure must not turn an accepted story into generation failure.
- Projection identity is `(game_id, event_id, revision)` plus a source hash containing story, options, prompt version, and schema version.
- Projection failure never blocks choice settlement, date advancement, or next-story generation.
- `applied_through_day_index` never crosses a pending/failed day.
- Old revision results and expired lease owners cannot mutate state.
- No Redis, Celery, or other external queue dependency is introduced.

---

### Task 1: Add projection persistence and player-state materialization schema

**Files:**
- Modify: `src/database/models.py`
- Modify: `src/game/state/player_data.py`
- Create: `src/services/daily_world_projection_repository.py`
- Test: `tests/test_daily_world_projection_repository.py`
- Test: `tests/test_player_state_submodules_db.py`

**Interfaces:**
- Produces: SQLAlchemy `DailyWorldProjection`, `DailyWorldProjectionAttempt`, `default_world_projection_state()`, `DailyWorldProjectionRepository`, and repository claim/update methods used by later tasks.

- [ ] **Step 1: Write failing schema and repository tests**

```python
def test_projection_identity_is_unique(db_session) -> None:
    repo = DailyWorldProjectionRepository(db_session)
    first = repo.ensure_projection(identity(), source_hash="hash-a")
    second = repo.ensure_projection(identity(), source_hash="hash-a")
    db_session.commit()
    assert first.projection_id == second.projection_id


def test_claim_due_uses_lease_fencing(db_session, frozen_now) -> None:
    repo = DailyWorldProjectionRepository(db_session)
    task = repo.ensure_projection(identity(), source_hash="hash-a")
    claimed = repo.claim_due(now=frozen_now, worker_id="worker-a", limit=1)
    assert [row.projection_id for row in claimed] == [task.projection_id]
    assert repo.claim_due(now=frozen_now, worker_id="worker-b", limit=1) == []


def test_player_state_defaults_projection_watermarks() -> None:
    state = PlayerState()
    assert state.world_projection_state == {
        "version": 1,
        "projected_through_day_index": -1,
        "applied_through_day_index": -1,
        "pending_from_day_index": None,
        "oldest_pending_at": None,
        "applied_sources": [],
        "world": empty_world_patch(),
    }


def test_attempt_ledger_counts_only_requested_window(db_session, frozen_now) -> None:
    repo = DailyWorldProjectionRepository(db_session)
    task = repo.ensure_projection(identity(), source_hash="hash-a")
    attempt_id = repo.start_attempt(task.projection_id, task.game_id, frozen_now)
    repo.finish_attempt(attempt_id, "suspicious_empty", "suspicious_empty", frozen_now)
    assert repo.count_game_attempts_between(
        task.game_id,
        frozen_now - timedelta(minutes=1),
        frozen_now + timedelta(minutes=1),
    ) == 1
```

- [ ] **Step 2: Run the tests and verify missing model failures**

Run: `python -m pytest tests/test_daily_world_projection_repository.py tests/test_player_state_submodules_db.py -q`

Expected: missing model/repository/field failures.

- [ ] **Step 3: Add the SQLAlchemy model and state field**

```python
class DailyWorldProjection(Base):
    __tablename__ = "daily_world_projections"
    projection_id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False, index=True)
    event_id = Column(String(96), nullable=False)
    revision = Column(Integer, nullable=False)
    day_index = Column(Integer, nullable=False, index=True)
    story_date = Column(String(10), nullable=True)
    source_hash = Column(String(128), nullable=False)
    status = Column(String(32), nullable=False, default="pending", index=True)
    story_patch_json = Column(JSON, nullable=True)
    option_patches_json = Column(JSON, nullable=True)
    coverage_json = Column(JSON, nullable=True)
    attempt_count = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(DateTime, nullable=False, index=True)
    lease_owner = Column(String(96), nullable=True, index=True)
    lease_expires_at = Column(DateTime, nullable=True)
    error_code = Column(String(80), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    applied_at = Column(DateTime, nullable=True)
    __table_args__ = (
        Index("ix_daily_world_projection_identity", "game_id", "event_id", "revision", unique=True),
        Index("ix_daily_world_projection_due", "status", "next_attempt_at", "lease_expires_at"),
    )
```

Add the per-call ledger:

```python
class DailyWorldProjectionAttempt(Base):
    __tablename__ = "daily_world_projection_attempts"
    attempt_id = Column(Integer, primary_key=True, autoincrement=True)
    projection_id = Column(Integer, ForeignKey("daily_world_projections.projection_id"), nullable=False, index=True)
    game_id = Column(Integer, ForeignKey("games.game_id"), nullable=False, index=True)
    started_at = Column(DateTime, nullable=False, index=True)
    finished_at = Column(DateTime, nullable=True)
    outcome = Column(String(32), nullable=False, default="running", index=True)
    error_code = Column(String(80), nullable=True, index=True)
```

Add `world_projection_state: Dict[str, Any] = Field(default_factory=default_world_projection_state)` to `PlayerDataMixin`; sanitize it on load so missing legacy keys receive defaults without changing old saves.

- [ ] **Step 4: Implement repository CAS methods**

Provide exact methods:

```python
ensure_projection(identity: ProjectionIdentity, source_hash: str) -> DailyWorldProjection
claim_due(now: datetime, worker_id: str, limit: int) -> list[DailyWorldProjection]
renew_lease(projection_id: int, worker_id: str, now: datetime, lease_until: datetime) -> bool
mark_ready(projection_id: int, worker_id: str, source_hash: str, payload: WorldProjectionPayload, no_change: bool) -> bool
mark_retryable(projection_id: int, worker_id: str, error_code: str, next_attempt_at: datetime) -> bool
mark_applied(projection_id: int, source_hash: str, applied_at: datetime) -> bool
supersede(game_id: int, event_id: str, before_revision: int) -> int
start_attempt(projection_id: int, game_id: int, now: datetime) -> int
finish_attempt(attempt_id: int, outcome: str, error_code: str | None, now: datetime) -> None
count_game_attempts_between(game_id: int, start: datetime, end: datetime) -> int
```

Every state-changing update includes current status, lease owner when applicable, and source hash in its SQL WHERE clause. A zero-row update returns `False` and is logged as a fenced late write.

- [ ] **Step 5: Run schema/repository tests**

Run: `python -m pytest tests/test_daily_world_projection_repository.py tests/test_player_state_submodules_db.py tests/test_database.py -q`

Expected: all pass for SQLite test databases; `Base.metadata.create_all` creates the new table idempotently.

- [ ] **Step 6: Commit persistence**

```bash
git add src/database/models.py src/game/state/player_data.py src/services/daily_world_projection_repository.py tests/test_daily_world_projection_repository.py tests/test_player_state_submodules_db.py
git commit -m "feat: persist versioned daily world projections"
```

### Task 2: Define typed projection patches and suspicious-empty coverage

**Files:**
- Create: `src/game/world_projection_schema.py`
- Modify: `src/game/world_projection_coverage.py`
- Modify: `src/ai/summary_generator.py`
- Modify: `src/ai/generator.py`
- Modify: `src/game/story_service.py`
- Modify: `config/prompts/world_prompts.py`
- Test: `tests/test_world_projection_schema.py`
- Test: `tests/test_world_projection_coverage.py`
- Test: `tests/test_summary_generator_recovery_contracts.py`

**Interfaces:**
- Produces: `WorldPatch`, `WorldProjectionPayload`, `WorldProjectionExtractionError`, `compute_projection_source_hash(story, options)`, the extended `detect_world_change_signals(story, options, tracked_state)`, and `extract_daily_world_projection(...)`.

- [ ] **Step 1: Write failing schema, empty-result, and provider-failure tests**

```python
def test_movement_and_completed_commitment_make_empty_projection_suspicious() -> None:
    coverage = detect_world_change_signals(
        "黑袍人抵达东海，完成了与孙悟空同行的约定。", [], tracked_state()
    )
    assert coverage.requires_nonempty_patch is True
    assert set(coverage.categories) >= {"location_updates", "commitment_updates"}


def test_valid_no_change_can_be_ready_no_change() -> None:
    payload = validate_projection_payload(empty_payload(), "两人在院中闲谈天气。", [], tracked_state())
    assert payload.no_change is True


def test_provider_failure_raises_instead_of_returning_empty(mock_client) -> None:
    mock_client.call.side_effect = TimeoutError("provider timeout")
    with pytest.raises(WorldProjectionExtractionError) as caught:
        generator.extract_daily_world_projection(story(), options(), tracked_state())
    assert caught.value.code == "provider_timeout"
```

- [ ] **Step 2: Run focused tests and verify failures**

Run: `python -m pytest tests/test_world_projection_schema.py tests/test_world_projection_coverage.py tests/test_summary_generator_recovery_contracts.py -q`

Expected: missing schema/coverage APIs and current empty fallback assertion failures.

- [ ] **Step 3: Implement typed patch models**

```python
WORLD_PROJECTION_SCHEMA_VERSION = 1
WORLD_PROJECTION_PROMPT_VERSION = "daily-world-projection-v1"


class WorldPatch(BaseModel):
    fact_updates: list[dict[str, Any]] = Field(default_factory=list)
    foreshadowing_seeds: list[dict[str, Any]] = Field(default_factory=list)
    habit_updates: list[dict[str, Any]] = Field(default_factory=list)
    location_updates: list[dict[str, Any]] = Field(default_factory=list)
    career_updates: list[dict[str, Any]] = Field(default_factory=list)
    commitment_updates: list[dict[str, Any]] = Field(default_factory=list)
    causal_updates: list[dict[str, Any]] = Field(default_factory=list)


class WorldProjectionPayload(BaseModel):
    schema_version: Literal[1] = 1
    story_patch: WorldPatch
    option_patches: dict[int, WorldPatch]
    no_change: bool = False
```

Validate that every option index from the accepted event appears exactly once. Missing entries become empty typed patches; extra indexes are rejected.

`compute_projection_source_hash` serializes normalized story/options plus `WORLD_PROJECTION_SCHEMA_VERSION` and `WORLD_PROJECTION_PROMPT_VERSION` with sorted keys and returns SHA-256. Enqueue, worker validation, supersede fencing, and repair all call this one function.

- [ ] **Step 4: Implement the evidence-only coverage detector**

Return category/evidence spans for tracked-character movement, commitment lifecycle, explicit state/career/habit change, and known causal-chain resolution. The function never constructs a patch. If all patches are empty and evidence requires a non-empty category, raise `WorldProjectionExtractionError(code="suspicious_empty")`; otherwise set `no_change=True`.

- [ ] **Step 5: Replace the empty fallback extraction contract**

Add one prompt asking for `story_patch` and `option_patches`. Parse with `WorldProjectionPayload.model_validate`; on provider/JSON/schema error raise the typed exception after the existing two immediate parse attempts. Keep legacy `extract_world_updates` for weekly callers, but daily projection code must not call it.

- [ ] **Step 6: Run extraction tests**

Run: `python -m pytest tests/test_world_projection_schema.py tests/test_world_projection_coverage.py tests/test_summary_generator_recovery_contracts.py tests/test_daily_narrative_prompts.py -q`

Expected: all pass; no daily path converts an exception into an all-empty success.

- [ ] **Step 7: Commit extraction contracts**

```bash
git add src/game/world_projection_schema.py src/game/world_projection_coverage.py src/ai/summary_generator.py src/ai/generator.py src/game/story_service.py config/prompts/world_prompts.py tests/test_world_projection_schema.py tests/test_world_projection_coverage.py tests/test_summary_generator_recovery_contracts.py
git commit -m "feat: validate daily world projection extraction"
```

### Task 3: Run durable projection jobs with leases and persisted backoff

**Files:**
- Create: `src/services/daily_world_projection.py`
- Modify: `config/feature_flags.py`
- Modify: `src/api/main.py`
- Test: `tests/test_daily_world_projection_service.py`
- Test: `tests/test_api_lifespan.py`

**Interfaces:**
- Consumes: repository from Task 1 and extraction contract from Task 2.
- Produces: `DailyWorldProjectionService.start()`, `stop()`, `wake()`, `run_once(now)`, `ensure_world_projection(...)`, and `get_daily_world_projection_service()`.

- [ ] **Step 1: Write failing scheduling and recovery tests with a fake clock**

```python
def test_retry_schedule_is_persisted(service, repo, clock) -> None:
    service.extractor.side_effect = WorldProjectionExtractionError("bad json", code="invalid_json")
    service.run_once(clock.now)
    assert repo.only().attempt_count == 1
    assert repo.only().next_attempt_at == clock.now + timedelta(seconds=5)


def test_expired_lease_is_reclaimed(service, repo, clock) -> None:
    task = repo.running_task(lease_owner="dead", lease_expires_at=clock.now - timedelta(seconds=1))
    service.run_once(clock.now)
    assert repo.get(task.projection_id).lease_owner == service.worker_id


def test_daily_call_cap_defers_without_failing_task(service, repo, clock) -> None:
    repo.record_eight_attempts_for_game(156, clock.today)
    service.run_once(clock.now)
    assert repo.only().status == "pending"
    assert repo.only().next_attempt_at.date() > clock.today
```

- [ ] **Step 2: Run service tests and verify missing service failures**

Run: `python -m pytest tests/test_daily_world_projection_service.py tests/test_api_lifespan.py -q`

Expected: missing service and lifespan hooks.

- [ ] **Step 3: Implement deterministic backoff and claim loop**

```python
FAST_RETRY_DELAYS = (5, 30, 120, 300)
MAINTENANCE_RETRY_DELAYS = (1800, 7200)
MAX_MODEL_CALLS_PER_GAME_DAY = 8
SCAN_INTERVAL_SECONDS = 15


def next_attempt_at(attempt_count: int, now: datetime) -> datetime:
    delays = FAST_RETRY_DELAYS + MAINTENANCE_RETRY_DELAYS
    if attempt_count <= len(delays):
        return now + timedelta(seconds=delays[attempt_count - 1])
    return start_of_next_day(now)
```

The service claims oldest due rows, loads the latest canonical game state, resolves the event revision from current event or day history, computes/validates the source hash, and writes an attempt-ledger row before the provider call. It renews the lease during the call, finishes the attempt row in `finally`, and uses repository fenced writes for all projection state transitions. Daily caps query attempt-ledger rows in the current local calendar-day window.

- [ ] **Step 4: Add lifecycle start/stop**

Add `daily_world_projection_v1` to the existing feature-flag registry, defaulting off until PR 2 deployment enables it. In FastAPI lifespan, call `service.start()` after `init_db()` only when the flag is enabled, and `service.stop(wait=False)` before shared thread pools shut down. The service owns one daemon scanner thread and a bounded extraction pool; importing the module does not start threads.

- [ ] **Step 5: Run scheduling/lifespan tests**

Run: `python -m pytest tests/test_daily_world_projection_service.py tests/test_api_lifespan.py -q`

Expected: backoff, lease recovery, cap, start, and shutdown tests pass without real provider calls.

- [ ] **Step 6: Commit the durable worker**

```bash
git add src/services/daily_world_projection.py config/feature_flags.py src/api/main.py tests/test_daily_world_projection_service.py tests/test_api_lifespan.py
git commit -m "feat: run durable daily world projection jobs"
```

### Task 4: Enqueue and supersede projections at every accepted-event boundary

**Files:**
- Modify: `src/api/routers/gameplay/sse_helpers.py`
- Modify: `src/game/daily_event_revision.py`
- Modify: `src/api/routers/story.py`
- Modify: `src/services/daily_recommended_prefetch.py`
- Modify: `src/game/game_loop.py`
- Test: `tests/test_daily_projection_enqueue.py`
- Test: `tests/test_daily_event_revision.py`
- Test: `tests/test_daily_recommended_prefetch.py`

**Interfaces:**
- Consumes: `ensure_world_projection(game_id, event, player_state)` and repository `supersede`.
- Produces: exactly-once enqueue after ordinary generation, replacement, rewrite, and promoted recommended prefetch.

- [ ] **Step 1: Write failing accepted-boundary tests**

```python
@pytest.mark.parametrize("path", ["normal", "regenerate", "rewrite", "promoted_prefetch"])
def test_each_accepted_daily_event_enqueues_projection_once(path, harness) -> None:
    event = harness.accept_event_through(path)
    assert harness.projection_repo.identity_count(156, event.event_id, event.revision) == 1


def test_successful_replacement_supersedes_old_revision(harness) -> None:
    old, new = harness.replace_event()
    assert harness.projection_repo.status(old.identity) == "superseded"
    assert harness.projection_repo.status(new.identity) == "pending"


def test_failed_replacement_does_not_supersede_old_projection(harness) -> None:
    old = harness.accepted_event()
    with pytest.raises(StoryGenerationFailure):
        harness.fail_replacement()
    assert harness.projection_repo.status(old.identity) != "superseded"
```

- [ ] **Step 2: Run focused tests and verify enqueue failures**

Run: `python -m pytest tests/test_daily_projection_enqueue.py tests/test_daily_event_revision.py tests/test_daily_recommended_prefetch.py -q`

Expected: no projection rows are created yet.

- [ ] **Step 3: Add post-commit notification hooks**

Call `ensure_world_projection` only after canonical persistence succeeds:

- normal generation: after `_set_generation_resume_view(..., "options")` succeeds;
- regeneration/rewrite: after atomic replacement persistence and old-media invalidation boundary;
- promoted prefetch: after `save_game_progress` succeeds;
- enqueue errors: log and schedule recovery scan, but do not fail the already accepted event.

For replacement/rewrite, call `supersede(game_id, event_id, before_revision=new.revision)` in the same database transaction that ensures the new projection row.

On daily game load, reconcile only two recoverable sources: the current accepted event, and day-history records explicitly carrying `world_projection_status="pending"`. This recreates a row lost to a post-commit enqueue error without implicitly backfilling every legacy day; controlled legacy backfill remains PR 3.

- [ ] **Step 4: Run accepted-boundary tests**

Run: `python -m pytest tests/test_daily_projection_enqueue.py tests/test_daily_event_revision.py tests/test_daily_recommended_prefetch.py tests/test_daily_generation_transaction.py -q`

Expected: all accepted paths enqueue exactly once; failed candidates create no row and supersede nothing.

- [ ] **Step 5: Commit lifecycle hooks**

```bash
git add src/api/routers/gameplay/sse_helpers.py src/game/daily_event_revision.py src/api/routers/story.py src/services/daily_recommended_prefetch.py src/game/game_loop.py tests/test_daily_projection_enqueue.py tests/test_daily_event_revision.py tests/test_daily_recommended_prefetch.py
git commit -m "feat: enqueue projections for accepted daily events"
```

### Task 5: Apply ready projections during or after immediate choice settlement

**Files:**
- Create: `src/game/world_projection_state.py`
- Modify: `src/game/round/daily_choice_processor.py`
- Modify: `src/game/round/system_mixin.py`
- Modify: `src/services/daily_world_projection.py`
- Test: `tests/test_world_projection_state.py`
- Test: `tests/test_daily_choice_processor.py`
- Test: `tests/test_daily_projection_serial_apply.py`

**Interfaces:**
- Produces: `apply_world_projection_patch(state, projection, option_index)`, `recompute_projection_watermarks(state, rows)`, and a choice-time projection lookup callback.

- [ ] **Step 1: Write failing immediate-choice and gap tests**

```python
def test_pending_projection_does_not_delay_choice(daily_processor, clock) -> None:
    daily_processor.projection_lookup.return_value = None
    result = daily_processor.make_choice(event_id="e5", revision=1, option_index=0)
    assert result["next_timeline"]["day_index"] == 6
    assert daily_processor.state.day_history[-1]["world_projection_status"] == "pending"


def test_ready_projection_is_applied_inside_staged_choice(daily_processor) -> None:
    daily_processor.projection_lookup.return_value = ready_projection()
    daily_processor.make_choice(event_id="e5", revision=1, option_index=1)
    assert daily_processor.state.world_projection_state["applied_through_day_index"] == 5


def test_applier_does_not_cross_failed_day(applier) -> None:
    applier.repo.seed([ready(day=5), failed_retryable(day=6), ready(day=7)])
    applier.apply_ready_for_game(156)
    assert applier.state.world_projection_state["applied_through_day_index"] == 5
    assert applier.repo.status_for_day(7) == "ready"


def test_reapplying_same_source_is_idempotent(applier) -> None:
    projection = ready(day=5, event_id="e5", revision=1)
    applier.apply_projection(projection)
    first = deepcopy(applier.state.world_projection_state)
    applier.apply_projection(projection)
    assert applier.state.world_projection_state == first
```

- [ ] **Step 2: Run focused tests and verify failures**

Run: `python -m pytest tests/test_world_projection_state.py tests/test_daily_choice_processor.py tests/test_daily_projection_serial_apply.py -q`

Expected: missing state applier and projection callbacks.

- [ ] **Step 3: Implement provenance-preserving patch materialization**

`apply_world_projection_patch` applies the typed story patch and the selected option patch into `world_projection_state["world"]`. Every resulting record includes:

```python
"source": {
    "event_id": projection.event_id,
    "revision": projection.revision,
    "day_index": projection.day_index,
}
```

Reuse existing `NarrativeManager`/`WorldModelUpdater` semantics against a temporary projection-state adapter rather than mutating legacy `world_model_data`. Before applying, check the source identity ledger inside `world_projection_state`; an already-recorded `(event_id, revision, day_index)` is a no-op. This makes a crash between state save and repository `mark_applied` safe to replay.

- [ ] **Step 4: Add non-blocking choice integration**

Pass `projection_lookup` into `DailyChoiceProcessor`. If ready/ready_no_change, apply in the staged candidate before its one durable write. Otherwise record `world_projection_id`, `world_projection_status="pending"`, and the actual option index in day history. Never call the model from `make_choice`.

- [ ] **Step 5: Add the serial post-choice applier**

After a worker marks a projection ready, acquire the game state lock and apply contiguous settled-day projections beginning at `applied_through_day_index + 1`. Stop at the first absent, pending, running, or failed_retryable record. Save state with revision/CAS, then mark each included projection applied.

- [ ] **Step 6: Run choice/applier tests**

Run: `python -m pytest tests/test_world_projection_state.py tests/test_daily_choice_processor.py tests/test_daily_projection_serial_apply.py tests/test_custom_choice_persistence_db.py -q`

Expected: immediate settlement remains synchronous and gap-free application is enforced.

- [ ] **Step 7: Commit choice and materialization**

```bash
git add src/game/world_projection_state.py src/game/round/daily_choice_processor.py src/game/round/system_mixin.py src/services/daily_world_projection.py tests/test_world_projection_state.py tests/test_daily_choice_processor.py tests/test_daily_projection_serial_apply.py
git commit -m "feat: apply world projections after daily choices"
```

### Task 6: Replace provisional freshness with the projection resolver

**Files:**
- Create: `src/game/world_projection_resolver.py`
- Modify: `src/game/world_constraint_freshness.py`
- Modify: `src/game/world_model.py`
- Modify: `src/game/round/event_generator.py`
- Modify: `src/ai/story_generator.py`
- Modify: `src/game/historical_summary_selector.py`
- Test: `tests/test_world_projection_resolver.py`
- Test: `tests/test_long_story_context.py`
- Test: `tests/test_story_generation_budget_tracking.py`

**Interfaces:**
- Produces: `ResolvedWorldContext(hard_world_model, soft_context, canonical_tail, freshness)` and `resolve_world_context(player_state)`.
- Replaces PR 1's legacy-only freshness calculation while preserving its call sites.

- [ ] **Step 1: Write failing precedence and canonical-tail tests**

```python
def test_projection_layer_overrides_legacy_location_as_hard_context() -> None:
    state = state_with_legacy_location("东海（途中）")
    state.world_projection_state = projected_location("花果山", applied_through=5)
    resolved = resolve_world_context(state)
    assert resolved.hard_world_model.character_locations["孙悟空"].location == "花果山"
    assert "东海（途中）" in resolved.soft_context


def test_pending_gap_adds_accepted_story_and_choice_to_canonical_tail() -> None:
    state = state_with_applied_watermark(3, history_through=5)
    resolved = resolve_world_context(state)
    assert "黑袍人抵达东海" in resolved.canonical_tail
    assert "返回花果山" in resolved.canonical_tail
```

- [ ] **Step 2: Run resolver and generation tests and verify failures**

Run: `python -m pytest tests/test_world_projection_resolver.py tests/test_long_story_context.py tests/test_story_generation_budget_tracking.py -q`

Expected: missing resolver and legacy model still wins.

- [ ] **Step 3: Implement deterministic precedence**

Build the hard model from immutable/base facts plus `world_projection_state.world`. Render legacy derived records that lack current provenance into `soft_context`. Build `canonical_tail` from accepted day-history entries after `applied_through_day_index`, including story, actual choice, event ID, revision, and date within the existing long-context token budget.

- [ ] **Step 4: Wire all daily prompt/validator consumers**

Replace direct daily reads of `world_model_data` in event generation, story generation, and historical summary selection with `resolve_world_context`. Legacy weekly paths continue using `WorldModel.from_player_state` unchanged. Log `stale_world_constraint_downgraded` when legacy records are excluded from hard validation.

When `daily_world_projection_v1` is off, `resolve_world_context` delegates to PR 1's provisional freshness implementation and never reads projection rows/state as hard authority. This is the schema-independent rollback path.

- [ ] **Step 5: Run resolver and validation suites**

Run: `python -m pytest tests/test_world_projection_resolver.py tests/test_long_story_context.py tests/test_story_generation_budget_tracking.py tests/test_world_model_constraint_matrix_contracts.py tests/test_story_validation_findings.py -q`

Expected: projection data wins, accepted ledger gaps remain canonical, and stale derived data never spends candidate budget.

- [ ] **Step 6: Commit the resolver**

```bash
git add src/game/world_projection_resolver.py src/game/world_constraint_freshness.py src/game/world_model.py src/game/round/event_generator.py src/ai/story_generator.py src/game/historical_summary_selector.py tests/test_world_projection_resolver.py tests/test_long_story_context.py tests/test_story_generation_budget_tracking.py
git commit -m "feat: resolve world context from projection watermarks"
```

### Task 7: Verify PR 2 independently

**Files:**
- Modify only for defects found inside PR 2 scope.

**Interfaces:**
- Produces: evidence that projection workers can be enabled or disabled without changing visible story/choice behavior.

- [ ] **Step 1: Run the full projection regression set**

Run: `python -m pytest tests/test_daily_world_projection_repository.py tests/test_world_projection_schema.py tests/test_world_projection_coverage.py tests/test_daily_world_projection_service.py tests/test_daily_projection_enqueue.py tests/test_world_projection_state.py tests/test_daily_projection_serial_apply.py tests/test_world_projection_resolver.py -q`

Expected: exit 0.

- [ ] **Step 2: Run daily generation/choice compatibility tests**

Run: `python -m pytest tests/test_daily_generation_transaction.py tests/test_daily_event_revision.py tests/test_daily_choice_processor.py tests/test_daily_recommended_prefetch.py tests/test_game_loop_load_recovery_contracts.py -q`

Expected: exit 0.

- [ ] **Step 3: Run repository gates**

Run: `./test.sh preflight && ./test.sh contract && ./test.sh db && ./test.sh frontend`

Expected: every command exits 0. Run `./test.sh all` only in the designated integration worktree.

- [ ] **Step 4: Exercise restart and rollback contracts**

Run the service test that leaves one row running, expires its lease, creates a fresh service instance, and confirms exactly one successful reclaim. Then set the projection service feature flag off and confirm daily generation/choice uses canonical history plus PR 1 freshness behavior without reading projection rows.

Expected: no duplicate application and no visible state change.

- [ ] **Step 5: Record a verification-only fix commit when needed**

```bash
git add src tests
git commit -m "test: close async projection regressions"
```

Skip this commit only when `git status --short` is empty.
