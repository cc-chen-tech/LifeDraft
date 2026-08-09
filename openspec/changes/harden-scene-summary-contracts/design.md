## Context

`HistoricalSummarySelector` is a pure gameplay-state selector, while
`SceneImageService` has provider-backed entry points but also exposes pure
character-manifest helpers. The maintained gate currently reaches 34.97 percent
of the `src` denominator and does not execute the existing pure scene contract
suite. Existing historical selector coverage includes mocking and unrelated
game-loop tests, so it is not suitable for direct gate promotion.

## Goals / Non-Goals

**Goals:**
- Exercise summary selection with concrete `PlayerState` values only.
- Cover keyword sources, recency scoring, and exclusion of current or future
  summaries.
- Promote only a provider-free, twice-stable scene contract suite.
- Keep backend workflow selections and coverage results reproducible.

**Non-Goals:**
- Change story, scene, persistence, provider, or random-fallback behavior.
- Promote broad game-loop tests that use mocks or test unrelated paths.
- Claim that this incremental batch reaches the long-term 70 percent backend
  target.

## Decisions

- Use real `PlayerState` fixtures rather than mocks so state-field contracts
  fail when production shape changes. This is preferred over the existing
  broad game-loop suite because it keeps selection behavior isolated.
- Test deterministic relevance paths only. Random fallback needs a patched
  random source to be deterministic and remains outside this maintained batch.
- Promote `test_multi_character_scene_contract.py` unchanged because its
  thirteen tests instantiate helpers with `__new__`, use no provider or mock,
  and completed two independent runs.
- Update both maintained workflow lists in the same position and assert exact
  parity before commit.

## Risks / Trade-offs

- [State fixture drifts from persisted defaults] -> Build fixtures with the
  real `PlayerState` model and assert externally visible returned summaries.
- [Existing scene tests overfit prompt wording] -> Retain only the already
  stable suite and add no template-string tests beyond it in this batch.
- [Coverage varies between runs] -> Measure the expanded selection twice and
  retain the current 34 percent floor unless both runs prove a higher integer.
