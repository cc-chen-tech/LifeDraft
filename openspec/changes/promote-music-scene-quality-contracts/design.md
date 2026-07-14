## Context

The maintained backend gate is at 45 percent and currently lacks deterministic music-quality contracts. The candidate suites exercise modern and historical settings, scene classification, candidate ranking, negative-cue rejection, prompt construction, and API request schema without network or provider calls.

## Goals / Non-Goals

**Goals:**
- Bring story-to-music quality regressions into fast maintained validation.
- Preserve ordered workflow-list parity.
- Increase the floor only from the full measured gate result.

**Non-Goals:**
- Test remote music availability, mutate provider configuration, or exercise live music generation.
- Change ranking, prompt, or era behavior.

## Decisions

- Promote both quality and era suites because one validates scene-fit behavior while the other validates the router/service interface that supplies era context.
- Use their existing fixed fixtures, which expose semantic regressions more reliably than network-dependent recommendation tests.
- Retain the existing gate unless the expanded selection reaches 46 percent.

## Risks / Trade-offs

- [Fixture assertions may be specific to current language rules] -> They intentionally lock user-facing music suitability and prompt constraints.
- [Broad service coverage remains partial] -> The promotion does not claim remote client or provider coverage.
