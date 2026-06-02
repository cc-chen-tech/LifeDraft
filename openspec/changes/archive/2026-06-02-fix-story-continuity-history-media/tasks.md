## 1. Test Gates First

- [x] 1.1 Add no-mock/no-skip static gate coverage for strict mypy and changed backend modules.
- [x] 1.2 Add no-mock/no-skip import validation coverage for gameplay, scene image, and collection lazy imports.
- [x] 1.3 Add no-mock/no-skip contract tests for gameplay, history scene image, and collection response fields.
- [x] 1.4 Add no-mock/no-skip real DB integration tests for round history and scene image save-read chains.
- [x] 1.5 Add no-mock/no-skip browser E2E coverage for history review and collection panel interactions.
- [x] 1.6 Update `test.sh` so all new gate tests run in the requested layers.

## 2. Gameplay Continuity Fixes

- [x] 2.1 Implement retry-aware story stream replacement for event and choice generation.
- [x] 2.2 Promote option consistency validation from warnings to retry/story-specific fallback behavior.
- [x] 2.3 Add Chinese punctuation normalization/validation for generated story and continuation text.
- [x] 2.4 Tighten generation constraints for repeated openings, character location, and career progression.

## 3. History And Scene Images

- [x] 3.1 Make historical scene image state derive from the keyed scene-image store.
- [x] 3.2 Ensure history review remains pinned to the selected round while current story state changes.
- [x] 3.3 Ensure scene images are selected by `game_id`, `week`, `round_number`, and `stage`.

## 4. Collection Stability

- [x] 4.1 Preserve character, item, and landmark image/detail data during refresh.
- [x] 4.2 Keep selected entity detail open after refresh when the entity still exists.
- [x] 4.3 Keep initial loading and background refresh states distinct.

## 5. Member Voice Reading Scope

- [x] 5.1 Add contract-level placeholders for phone login and voice-reading API fields without enabling unfinished member-only behavior.

## 6. Verification

- [x] 6.1 Run targeted new tests and confirm they pass.
- [x] 6.2 Run `./test.sh all` and confirm all required layers pass.

## 7. Live Regression Tests First

- [x] 7.1 Add frontend no-skip regression coverage for `/story/opening` displaying `event: story` chunks and preserving accumulated text on empty complete payloads.
- [x] 7.2 Add frontend store regression coverage that recovered events with options also restore visible story text.
- [x] 7.3 Add frontend interaction regression coverage that expanded ChatBar can be closed and does not block custom choice submission.
- [x] 7.4 Add frontend regeneration regression coverage that options are never shown with empty story after regenerate/recovery.
- [x] 7.5 Add backend real-DB scene image regression coverage for missing image auto-generation from `game_states.state_json` without `Game.player_state`.
- [x] 7.6 Add music service degradation regression coverage for upstream 503 returning a fast, user-visible empty/fallback recommendation instead of noisy failure.
- [x] 7.7 Add backend narrative quality regression coverage for perspective consistency, paragraph normalization, and internal-state leak rejection.

## 8. Live Regression Fixes

- [x] 8.1 Fix opening-story SSE parsing and page accumulation behavior.
- [x] 8.2 Fix active game/state recovery so story text and options are restored together.
- [x] 8.3 Fix ChatBar/custom-choice layout and accessible close behavior.
- [x] 8.4 Fix regenerate/recovery state transitions that can leave options without story text.
- [x] 8.5 Fix scene image endpoint to read latest persisted state snapshot and return 202 for background generation.
- [x] 8.6 Fix music 503 handling to degrade quickly and quietly with clear UI state.
- [x] 8.7 Fix deterministic narrative cleanup gates for internal text leaks, mixed perspective, and over-fragmented paragraphs.
- [x] 8.8 Run targeted regression tests and `./test.sh all`.
