## Context

The frontend currently renders raw resource metrics in several runtime surfaces: the gameplay status bar, choice impact cards, the ending page, and life review cards. These fields still exist in the game state and API payloads, so the change should hide presentation only and avoid schema or persistence churn.

## Goals / Non-Goals

**Goals:**
- Remove visible runtime labels and values for `精力`, `情绪`, `学识`, and `财富`.
- Keep age/week/progress and story-oriented review content visible.
- Preserve API/state compatibility for existing saves and backend logic.
- Update frontend unit tests and E2E assertions before implementation.

**Non-Goals:**
- Removing resource fields from backend models, API responses, or saved game state.
- Changing character creation settings such as initial wealth.
- Redesigning unrelated gameplay controls.

## Decisions

- Hide at the presentation layer instead of deleting state fields.
  - Rationale: existing stores, saved games, and backend generation logic still depend on these values.
  - Alternative considered: remove fields end-to-end. This would be larger and conflicts with the requested frontend-first scope.
- Treat resource-only choice effects as non-renderable.
  - Rationale: exposing a resource-only card would preserve the same noisy metric surface under a different label.
  - Alternative considered: show generic text such as "状态变化". This still invites attention to hidden scores without adding story value.
- Keep tests focused on visible UI text and stable selectors.
  - Rationale: the requested behavior is presentation-level, so tests should assert absence from rendered surfaces while allowing API fields to remain.

## Risks / Trade-offs

- Hidden metrics may still appear in unrelated setup screens such as initial wealth configuration → Limit the contract to runtime story/play/ending/review surfaces.
- Older E2E specs may assert metric visibility → Update them to the new frontend contract.
- Backend may still generate text mentioning money or study naturally in story prose → This change only removes numeric resource UI, not narrative content.
