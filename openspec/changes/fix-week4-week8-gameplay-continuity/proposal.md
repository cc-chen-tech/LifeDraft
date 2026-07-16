## Why

Long-running saves can lose completed player actions when a session is restored: the
continuity ledger only seeds identities, generated fallback prose can be committed as
real story, and the next event falls back to the original setup. The same stale story
then propagates to weekly summaries, scene images, and music. Life-summary requests
also have no bounded client or server wait, leaving the page stuck during a provider
stall.

## What Changes

- Rebuild missing continuity evidence from durable historical rounds before a restored
  game generates a new event, and retain the committed player choice alongside the
  compressed summary.
- Treat a failed continuation or custom-choice evaluation as a failed operation: do not
  advance the round, mutate resources, or persist a fabricated result.
- Reject repeated generated events and repeated fallback option sets when they duplicate
  recent committed decision points; expose an actionable generation failure instead.
- Bound life-summary generation on both the browser and backend paths, show a retryable
  error, and preserve the playable game state.
- Feed the recovered committed-story evidence into media requests so scene images and
  music reflect the current event rather than stale opening text.

## Capabilities

### New Capabilities

- `committed-story-recovery`: reconstructs authoritative committed-story context for
  legacy saves before further generation.

### Modified Capabilities

- `gameplay-continuity`: completed choices, generated events, and options must preserve
  plot progression and cannot silently regress to generic fallback content.
- `gameplay-generation-recovery`: failed choice and summary generation must leave a
  recoverable, interactive state instead of a blocked page.
- `music-and-media-degradation`: media context must follow the committed current story
  while media failure remains non-blocking.
- `story-display-quality`: synthesized fallback prose must not be presented as a valid
  narrative outcome.

## Impact

Affected systems include `PlayerState` ledger restoration, round generation and choice
processing, SSE and synchronous gameplay routes, the life-summary API/client, and the
play-page media triggers. The change adds regression coverage for legacy saved state,
custom choice failure atomicity, repeated event rejection, summary timeout recovery,
and media-context selection.
