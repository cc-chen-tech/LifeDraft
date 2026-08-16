# Task 5 Report: Immediate Choice Settlement and Serial Projection Apply

## Status

Implemented on base `cbaf383b` without changing the Task 1–4 repository or
enqueue interfaces. Choice settlement remains model-free: it performs at most a
short projection-row lookup, applies an already-ready patch to the staged
candidate, and persists the choice plus projection state in the existing single
durable write.

## TDD evidence

The first focused RED run was:

```text
python -m pytest tests/test_world_projection_state.py tests/test_daily_choice_processor.py tests/test_daily_projection_serial_apply.py -q
ERROR tests/test_world_projection_state.py
ModuleNotFoundError: No module named 'src.game.world_projection_state'
```

Subsequent behavior-level RED runs established:

- `DailyChoiceProcessor.__init__()` rejected `projection_lookup`.
- `DailyWorldProjectionService` lacked `apply_ready_for_game()` and choice lookup.
- an `applied` repository row did not repair a stale staged choice candidate.
- an absent settled-day row incorrectly cleared `pending_from_day_index`.
- a failed `mark_applied` was not replayed by the next `run_once()` scan.

Each failure was observed before its production change. The final focused run is
27 passed, and the Task 1–4 affected run is 275 passed.

## Implemented behavior

- Added deterministic projection materialization through a temporary adapter
  that reuses `NarrativeManager` and `WorldModelUpdater` without mutating legacy
  `world_model_data`.
- Added source provenance to every materialized record and an applied-source
  ledger fenced by event, revision, day, source hash, and selected option.
- Added choice-time lookup with strict event/revision/day/source fencing.
  Pending, running, retryable-failed, superseded, mismatched, and absent rows do
  not delay settlement; the history record retains the canonical identity,
  actual option index, optional projection id, and `pending` status.
- Ready, ready-no-change, and already-applied rows are materialized inside the
  staged candidate before its one existing persistence callback. A failed save
  publishes neither choice state nor projection state to the live object.
- Added a per-game serial applier. It locks the game mutation boundary, loads the
  latest state snapshot, checks the latest `GameState.state_id` as a CAS token,
  and applies only the contiguous settled prefix beginning at
  `applied_through_day_index + 1`.
- Absent, pending, running, retryable-failed, superseded, identity-mismatched,
  source-mismatched, or option-mismatched days stop the scan immediately.
- Projection state commits before repository rows are marked applied. A crash or
  failed marker is replayed from durable ready rows; the applied-source ledger
  makes the replay a no-op on materialized world records.
- Worker publication triggers serial application, while choice completion only
  schedules a model-free background apply/wake. No provider session is created
  by the choice path.

## Verification

```text
python -m pytest tests/test_world_projection_state.py tests/test_daily_choice_processor.py tests/test_daily_projection_serial_apply.py -q
27 passed

python -m pytest tests/test_daily_world_projection_service.py tests/test_daily_world_projection_repository.py tests/test_daily_projection_enqueue.py tests/test_daily_recommended_prefetch.py tests/test_daily_event_revision.py tests/test_api_lifespan.py tests/test_player_state_submodules_db.py tests/test_world_constraint_freshness.py tests/test_world_projection_schema.py tests/test_world_projection_coverage.py -q
275 passed, 1 deprecation warning

python -m pytest tests/test_custom_choice_persistence_db.py -q -k 'not test_custom_choice_preserved_after_save_and_load'
5 passed, 1 deselected
```

The exact brief command including all of
`tests/test_custom_choice_persistence_db.py` has one unrelated failure:
`test_custom_choice_preserved_after_save_and_load` expects retired
`effects.wealth == -100`, while current mainline persistence strips wealth and
returns only `mood`. Task 5 does not touch custom-choice or wealth code.

## Coverage highlights

- pending/failed lookup and absent producer followed by reload reconciliation
- ready projection inside the staged choice plus persistence rollback
- duplicate choice and duplicate source replay
- day 5 ready / day 6 failed / day 7 ready gap stop
- injected state-save failure before the projection snapshot commit
- injected `mark_applied` failure recovered by the next scanner pass
- concurrent worker and choice persistence with one final materialized source
- stale live choice repaired from an already-applied repository row

## Concerns

- The unrelated custom-choice wealth assertion remains red as described above.
- Choice-time lookup is a short local database transaction when the feature flag
  is enabled; it never invokes or waits for a model provider. Lookup errors are
  downgraded to an immediately persisted pending projection record.
