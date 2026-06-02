## Why

Gameplay currently has several visible continuity and state issues: choices can feel detached from the story, streamed retries can duplicate story text, history review can fall back to the latest story, scene images do not reliably correspond to the selected round, and collection refreshes can be slow or visually unstable. These issues break immersion, especially in longer play sessions where history, relationships, character location, and career continuity matter.

## What Changes

- Stabilize event and choice streaming so a retry/regeneration replaces the attempted story segment instead of duplicating old and new text.
- Make generated options directly answer the final decision point of the current story and reject obviously generic or unrelated options.
- Keep history review read-only and pinned to the selected round, including text, selected index, and matching scene image.
- Ensure scene image lookup and display are keyed by `game_id + week + round + stage`, including historical scene images.
- Improve collection loading behavior so refreshes keep existing data visible and do not clear details or thumbnails unnecessarily.
- Add generation-quality requirements for Chinese punctuation, story opening variation, character location constraints, and career/position progression consistency.
- Define member voice reading behavior as a separate capability surface: phone login, selectable voice colors, optional uploaded voice synthesis, and auto-read mode. Implementation may be staged after core gameplay fixes.

## Capabilities

### New Capabilities

- `gameplay-continuity`: Story generation, choice relevance, streaming retry behavior, and narrative consistency rules.
- `history-review`: Read-only historical round browsing and historical scene-image selection.
- `collection-stability`: Collection panel loading, refresh, detail preservation, and image refresh behavior.
- `member-voice-reading`: Member login and voice-reading requirements for later implementation.
- `test-gates`: Required no-mock/no-skip test layers and `test.sh` integration for all bug fixes and new features.

### Modified Capabilities

- None.

## Impact

- Frontend gameplay hooks and stores: `usePlayGame`, `useEventGenerator`, `useChoiceHandler`, `useHistoryViewer`, `useGameStore`, `useSceneImageStore`, `useCollectionStore`.
- Frontend game components: play page, history drawer/image display, collection panel, streaming text, option cards.
- Backend gameplay generation: event generation, choice processing, prompt construction, option validation, consistency validation, world-model constraints.
- Backend image APIs: round-scene image lookup and generation behavior for current and historical rounds.
- Tests: unit tests for hooks/stores, API/router tests for scene images and gameplay, and focused e2e coverage for history and no-duplicate-stream regressions.
