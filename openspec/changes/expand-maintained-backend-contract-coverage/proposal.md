## Why

The maintained backend gate now proves 34.11% of the full `src` denominator,
but high-risk gameplay fallbacks, event-route safeguards, entity extraction,
and local music reuse still have sparse deterministic coverage. These paths
contain state and field contracts that should fail before a browser or provider
run reveals a regression.

## What Changes

- Add provider-free fallback-context tests for round event generation.
- Add event-route protocol tests for connection limits, saved-view protection,
  and resume-cursor parsing.
- Add parser contracts for item and landmark extraction edge cases.
- Add local music metadata eligibility contracts that do not require a database
  or music provider.
- Promote only suites that pass twice to both maintained backend workflows in
  identical order, then measure the full `src` result twice.

## Capabilities

### New Capabilities
- `maintained-backend-contract-expansion`: Deterministic contracts for
  gameplay fallback, route protocol, extraction, and local music reuse paths.

### Modified Capabilities
- `test-gates`: Require this stable contract batch to remain symmetric across
  maintained backend workflows.

## Impact

- New tests target `src/game/round/event_generator.py`, gameplay event router
  helpers, extraction services, and `src/services/local_ai_music_library.py`.
- The maintained test list grows only after repeatable local validation.
- No production code or existing tests are modified.
