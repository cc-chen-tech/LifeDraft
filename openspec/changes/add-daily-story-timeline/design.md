## Context

The current authority is `(week, current_round)` with three rounds per week. Choice processing generates 200–400 characters of continuation, performs synchronous enrichment, saves multiple overlapping history collections, enters a result or weekly-summary phase, then waits for another click. Current events have no stable revision contract, and scene images are keyed by `(game, week, round, stage)`.

Player state is stored as JSON snapshots, so timeline fields and day history can migrate without a relational player-state migration. Scene images require additive nullable date/day columns because they are relational rows.

## Goals / Non-Goals

**Goals:**

- Make `start_date + day_index` the only time authority for v2 games and derive all display/progress fields.
- Generate one complete story and coherent options per day, atomically commit one generated choice, and automatically request the next day.
- Preserve exact save/recovery semantics and idempotency across disconnects.
- Upgrade legacy saves and media without rewriting their prose or inventing missing story days.
- Roll out behind a reversible entry flag while continuing to read migrated saves.

**Non-Goals:**

- Event-sourcing the entire game, supporting v2-to-v1 downgrade, editing completed history, or retaining custom choices in daily mode.
- Displaying weekly summaries or generating choice-result prose/images in daily mode.

## Decisions

### Timeline authority

Add a focused timeline module that validates ISO dates, derives current date/week/weekday/progress, advances one day, and migrates v1 JSON. `timeline.version == 2` always selects daily behavior even if the rollout flag is later disabled; the flag controls creation and first migration only. Compatibility `week/current_round` fields are derived on serialization during transition and never drive v2 progression.

New games store an exact start date selected during character creation. Legacy games anchor the era year at its first Monday. Each legacy round is assigned an offset of Monday=0, midweek=2, weekend=6. A pending current event retains its mapped date; a completed legacy round resumes from the following natural date. Migration is idempotent and preserves current age while recording the next 365-day age threshold.

### Versioned daily events and atomic choice commit

Daily current events carry `event_id = day:<day_index>`, an integer `revision`, and `story_date`. Generation creates revision 1. Rewrite/regenerate create a complete candidate, including fresh options, then swap it into player state and invalidate media only after validation succeeds.

Choice requests include `event_id`, `revision`, and `option_index`. The processor rejects stale versions, uses `choice:day:<day_index>` as the idempotency key, stages resource effects, appends one canonical `day_history` entry, clears the current event, advances the timeline, and saves in one request. Compatibility response fields remain empty/false. A duplicate request returns the saved settlement without applying effects again.

### One generation per day

The daily prompt includes the exact date, yesterday's complete story, selected option, and applied effects. It ends at one actionable decision point. Daily budgets are fast 350–500 Chinese characters, expert 500–800, and master 800–1200. Choice processing never calls story-continuation generation. Standard option effects are authoritative; custom-choice endpoints return `custom_choice_disabled` for v2 games.

Critical commit work remains synchronous. Narrative compression, world extraction, entity recognition, 28-day summaries, and 365-day summaries run as recoverable post-processing keyed by day entry and update only the matching pending record. Seven-day deterministic decay applies during choice commit without a user-visible weekly summary or AI bonus.

### API and frontend state machine

State responses add a normalized `timeline` object. Event payloads add version metadata. The v2 frontend has `generating -> options -> choosing -> generating` with `ending/error` branches. On settlement it briefly displays structured effects and immediately generates the next day. It removes custom choice, result confirmation, next-round, and weekly-summary UI. The main heading renders `公元 YYYY 年 MM 月 DD 日`.

The opening flow requests the first daily event and routes directly to `/play`; the old opening route remains a compatibility redirect for v2 games. Rewrite/regenerate routes retain their URLs but use candidate replacement semantics.

### History, scheduling, and media

`day_history` is canonical for v2 and contains date, story/options snapshots, choice, requested/applied effects, warnings, and post-processing status. Existing history lists remain read-only compatibility inputs after migration.

Scheduled events gain `scheduled_date`; daily matching and overdue checks use ISO dates. Relative-date parsing performs Gregorian arithmetic. Scene images gain nullable `story_date` and `day_index` plus a daily unique key. Legacy `(week, round, stage)` lookup remains available for v1 rows; daily mode uses a single story stage.

## Risks / Trade-offs

- [672 daily decisions increase total generation] → Remove continuation calls and shorten daily budgets.
- [A failed automatic next-day generation follows an already committed choice] → Persist the advanced empty day and expose safe generation retry without replaying the choice.
- [Background enrichment races with later saves] → Address records by immutable day/event id and merge only if their post-processing token still matches.
- [Legacy history has only three observations per week] → Preserve only real observations at Monday/Wednesday/Sunday and never synthesize the missing days.
- [Large cross-cutting rollout] → Ship additive reads/schema first, gate new creation/migration, and retain legacy endpoint shapes during transition.

## Migration Plan

1. Add timeline helpers, dual-format reads, nullable scene columns, and dry-run migration reporting with the flag disabled.
2. Enable v2 for test-created games and run backend contracts, generated types, Jest/TypeScript, and browser flows.
3. Enable new production games, then lazy-migrate owned legacy saves on restore; save a v2 snapshot only after validation.
4. Monitor migration failures, stale-choice rejects, generation recovery, and scene lookup misses before retiring v1 write paths.
5. Emergency rollback disables new v2 creation/migration. Existing v2 saves continue through the v2 reader; no destructive downgrade is attempted.

## Open Questions

None. Product decisions are fixed by the approved implementation plan.
