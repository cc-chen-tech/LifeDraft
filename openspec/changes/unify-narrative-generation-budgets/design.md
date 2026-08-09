## Context

Round prose partially uses `GenerationBudget`, but opening, continuation, rewrite, regeneration, Harness repair, and truncation recovery still carry their own length text, token ceilings, retry loops, or timeouts. Style manifests can also inject numeric chapter lengths that override product intent. The rollout must preserve the current behavior behind a default-off flag and keep old imports working while callers migrate.

## Goals / Non-Goals

**Goals:**

- Make product length targets, compression thresholds, absolute character limits, model output limits, provider-call allowances, and deadlines distinct typed concepts.
- Resolve one immutable budget at request entry and pass one mutable call tracker through every nested generation/repair path.
- Localize length measurement and prompt wording without allowing prompt builders or style manifests to invent numeric limits.
- Bound recovery and return the latest complete prose when optional repair work cannot run.

**Non-Goals:**

- Option-card repair and display layout, explicit request input limits, summary generation, and long-context compaction.
- Database migrations or changes to stored stories.
- Treating soft target-band drift as a terminal failure; phase 1 owns that behavior.

## Decisions

### One resolver with orthogonal dimensions

`src/ai/budgets.py` will define `NarrativeKind`, `GenerationOperation`, `LocalizedLengthBand`, `NarrativeBudget`, `DisplayBudget`, `InformationBudget`, and `GenerationCallTracker`. The resolver takes narrative kind, operation, quality level, language, and optional original length. Narrative kind selects the base target and output tokens; quality selects round targets, call allowances, and deadline; operation derives rewrite/regeneration behavior.

This is preferred over per-service configuration because nested repairs otherwise reconstruct incompatible limits. A generic dictionary was rejected because enum/dataclass contracts make unbudgeted call sites and invalid categories testable.

### Explicit language measurement

Chinese soft length is measured as Unicode code points after removing whitespace. English soft length is measured as Unicode-aware word tokens. The absolute technical ceiling always measures raw Unicode code points and is fixed at 32,000. Prompt text comes from `format_length_requirement(budget)` so runtime measurement and model instruction share the same unit and values.

### Rewrite budgets derive from the submitted story

A full-output rewrite targets 80%-120% of the measured original story, with its upper target capped at the base scenario's compression threshold. Regeneration ignores original length and resolves the active quality/kind budget. Segment rewrite returns a complete story, so it follows the same full-output rewrite band.

### One request-owned tracker

`GenerationCallTracker` records monotonic start time and category counters for prose, validation, and option calls. Every provider-facing narrative call must call `consume` immediately before invocation. Consumption fails before the provider call when its category allowance or total deadline is exhausted. Nested services accept an existing tracker; only a top-level entry point may create one.

Truncation continuation consumes prose allowance on the same tracker and is marked as recovery. A recovery response cannot recursively start another recovery sequence. Exhaustion returns the last complete candidate when one exists; it does not erase prose because validation or recovery was skipped.

### Staged compatibility

`generation_budget.py` re-exports compatibility names backed by the new resolver for one stable release. `ENABLE_UNIFIED_NARRATIVE_BUDGETS=false` leaves existing call-site behavior available during rollout, while contract tests exercise both paths. New or migrated code must not introduce raw 4096/8192 token ceilings in the critical narrative chain.

### Style manifests express density, not length

`ChapterRules.avg_length` remains readable for old manifests during the compatibility release but is excluded from generated prompts. Manifests are rewritten to relative density/pace language, and a contract rejects numeric length ranges in active style constraints.

## Risks / Trade-offs

- [Lower token ceilings expose provider truncation sooner] -> Share prose allowance with one bounded continuation and retain the latest complete candidate.
- [Default-off dual paths can drift] -> Run parameterized flag-on/flag-off contracts and remove the old path after one stable release.
- [English word tokenization differs from provider tokenization] -> Treat product length units and model token ceilings as intentionally separate metrics.
- [Mass manifest edits create review noise] -> Limit edits to `avg_length` semantics and enforce the result with one static contract.
- [Passing trackers through legacy APIs is invasive] -> Add optional keyword-only tracker/budget parameters first, then make request entry points authoritative without changing public API response schemas.

## Migration Plan

1. Add the typed module, compatibility re-exports, flag, and contract tests.
2. Migrate round/opening/continuation generation, then rewrite/regeneration, then Harness and truncation recovery.
3. Remove active numeric prompt lengths and convert manifest chapter length hints to relative density.
4. Deploy with the flag off, exercise deterministic E2E with both settings, then enable by environment during the phase-2 observation window.
5. Roll back by disabling the flag; no persisted data requires reversal.

## Open Questions

None. Defaults and rollout boundaries are fixed by the approved implementation plan.
