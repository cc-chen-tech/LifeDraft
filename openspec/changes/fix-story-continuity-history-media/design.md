## Context

The gameplay loop is split across a Next.js frontend and a FastAPI backend. The frontend stores current story text, options, history view state, collection state, and scene-image state in several hooks and Zustand stores. The backend generates story text and options in separate AI calls, validates consistency, streams story chunks via SSE, persists round history, and serves scene images keyed by game, week, round, and stage.

The reported issues mostly come from state-source ambiguity and weak validation boundaries:

- Current story text is appended during SSE, but retries can stream a replacement story without a single frontend-owned buffer reset boundary.
- Historical image state exists both inside `useHistoryViewer` and in `useSceneImageStore`, causing selected historical rounds to lose the fetched image.
- Option consistency warnings are logged but not treated as generation failures.
- Scene image APIs support week/round/stage keys, but frontend state selection is inconsistent between current and historical rounds.
- Collection refreshes preserve some character images but not all entity types and can update selection with stale or empty detail objects.
- Narrative quality constraints exist in prompts and world model helpers, but they are not enforced uniformly across story, option, and continuation generation.

## Goals / Non-Goals

**Goals:**

- Make story streaming idempotent per generation attempt and prevent duplicate display after retry or reconnection.
- Ensure generated options directly answer the current story's decision point and are regenerated or replaced when generic/unrelated.
- Make history review a read-only view pinned to one selected round until the user returns to current.
- Make historical and current scene image state derive from the same keyed scene cache.
- Keep collection refreshes visually stable and preserve selected details when data reloads.
- Tighten generation prompts/validators around punctuation, repeated openings, character location, and career/position progression.
- Capture member voice reading as a spec-level contract without blocking gameplay bug fixes.
- Enforce the requested test gates before implementation: strict mypy, import validation, contract tests, real DB integration, and browser E2E coverage must be runnable from `test.sh`.

**Non-Goals:**

- Replacing the AI provider or adding a new generation framework.
- Reworking the entire persistence model for games, images, or collections.
- Fully implementing paid membership, SMS infrastructure, or custom voice cloning in this bug-fix pass.
- Changing the game rules or removing existing save/load/session recovery behavior.

## Decisions

1. Use a generation-attempt boundary on the frontend.

   Story text changes from a retry MUST replace the current attempt buffer. Existing successful story text remains only when recovering the same event without a retry marker. This keeps SSE recovery useful while preventing duplicate paragraphs.

2. Treat option relevance as a hard generation quality gate.

   Existing option consistency checks will be promoted from warning-only behavior to retry/fallback behavior. If generated options are generic, too detached from the story ending, or use invalid relationship targets, the backend will retry option generation and only use fallback options that are explicitly tied to the story text.

3. Use the scene image store as the single source of truth.

   `useHistoryViewer` should track selected history index and text, while image data should come from keyed scene-image store state. Fetching a history image must update the same keyed cache used by current round images.

4. Key scene images by `week`, `round_number`, and `stage`.

   The frontend must not infer a historical image by current round alone. Current display can prefer `event` or `result` based on phase; historical display uses the selected round and requested/default stage.

5. Preserve collection data during refresh by entity key/name.

   Refreshes should merge character, item, and landmark data to preserve image URLs and selected detail state when the backend temporarily returns partial data during image/description generation.

6. Stage member voice reading separately.

   Phone login and voice synthesis require external services and security/privacy decisions. The spec defines behavior and acceptance boundaries, while implementation can be a later change unless local stubs already exist.

7. Tests are written first and then treated as locked.

   For each task, add the relevant no-mock/no-skip tests and `test.sh` command coverage before changing production code. After those tests are added, production implementation must adapt to them; tests should not be weakened to make code pass.

## Risks / Trade-offs

- **Retry replacement could erase valid streamed text if backend emits an incorrect retry status** → Scope replacement only to explicit retry/retrying status and add tests around normal reconnect behavior.
- **Stricter option validation may increase AI latency** → Limit retries and provide story-specific fallback options rather than looping indefinitely.
- **Historical scene image cache may contain multiple stages per round** → Use explicit key matching and deterministic stage preference.
- **Collection merge may keep stale images after deletion** → Merge only by entities returned by the backend; do not keep entities absent from the new response.
- **Prompt-only quality constraints can still be violated** → Add lightweight deterministic validation where practical and keep AI validation as a second layer.
- **Existing legacy test suites contain mocks/skips** → New gate tests for this change will be no-mock/no-skip, and `test.sh` will call those gate suites explicitly. Broad legacy cleanup is outside this change unless required by the gate commands.
