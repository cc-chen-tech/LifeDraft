## Context

Smart recognition combines model output with regex fallback extraction. Before this change, model-provided character names pass `_validate_entity` when non-empty, while fallback candidates are only partly filtered. A production run therefore stored non-people and an invented full name. Gameplay state uses zero-based `current_round`, and the scene-image label renders that raw index directly to players.

## Goals / Non-Goals

**Goals:**

- Make character recognition evidence-based without losing explicitly configured or explicitly mentioned people.
- Retain role-title names verbatim when that is all the player supplied.
- Render zero-based current-round state as a visible one-based player-facing progress label.
- Protect both behaviors with regression tests based on the production failure report.

**Non-Goals:**

- This change does not infer real names from titles, correct already-persisted collections, or redesign item and landmark recognition.
- This change does not alter the backend round-state data model or how weeks advance.

## Decisions

1. Filter character proposals after parsing and before supplementation against a canonical candidate set. A candidate is allowed only when it is a configured eligible name that appears verbatim in the story, or when deterministic person extraction finds that exact text. This prevents the model from naming `周师傅` as `周建国` while retaining `周师傅`. Filtering only the fallback extractor would leave the model-output route vulnerable.

2. Explicit configured names still need story evidence for smart-recognition proposals. This preserves the existing rule that the panel shows characters encountered in the story, not every person on the character card.

3. Keep `round_number` zero-based in state and derive its scene-image label as `round_number + 1`. Changing persisted semantics would break history, scene images, and event selection. The general progress bar already uses a separate completion convention and is not changed.

## Risks / Trade-offs

- [A model returns a correct name that the regex cannot recognize] → Allow all configured names when their exact text appears in the story, and keep existing deterministic extraction for unconfigured names.
- [Legacy UI expectations hide initial progress] → Update the test contract to define the Monday state as player-visible round one.
- [Existing polluted collection rows remain] → Do not delete user data automatically; new recognitions no longer add those rows.

## Migration Plan

Deploy as a behavior-only change. No schema migration is required. Rollback consists of reverting the filtering helper and display derivation; persisted state remains compatible.

## Open Questions

None.
