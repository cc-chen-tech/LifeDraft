## Context

The play page sets narration and music targets once story text reaches `options`, `result`, or `summary`. When regeneration starts, phase and displayed text change, but the previous targets remain in global stores and an existing reading attempt is not stopped. Voice settings are persisted by the backend and guarded against late hydration, but that behavior needs direct regression coverage.

## Goals / Non-Goals

**Goals:**
- Make stale playback impossible once current-story regeneration begins.
- Prevent TTS and generated music from receiving incomplete replacement text.
- Preserve the user's selected voice across hydration and navigation.

**Non-Goals:**
- Changing MiniMax voice IDs or adding new voices.
- Stopping deliberate history narration when only the current story is idle.
- Reworking music recommendation ranking.

## Decisions

1. Introduce one production completed-media gate that owns both voice and music story targets.
2. A current-story busy phase clears both targets and calls the voice store's normal stop path, which also restores ducked music.
3. Completed text is published only when the phase is media-ready and the user is not viewing history.
4. History narration keeps its explicit context and never becomes a generated-music target.
5. Existing backend settings remain the persistence source; tests prove a user selection is not overwritten by delayed hydration and survives a real repository round trip.

## Risks / Trade-offs

- [Rapid phase changes stop a deliberate read] -> Only current-story busy phases trigger cancellation; history context is excluded.
- [Same completed text is republished] -> Existing TTS/music dedupe keys remain authoritative.
- [Backend settings are unavailable] -> Keep the local user selection and existing browser fallback behavior.
