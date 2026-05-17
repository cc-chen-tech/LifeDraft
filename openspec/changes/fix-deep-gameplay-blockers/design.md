# Design

## Exploration Findings

### Generation State

The visible failure is not merely "generation takes a while." A slow generation is acceptable only if the game remains recoverable. The defect pattern is: frontend enters a generating/analyzing phase, refresh restores that transient phase, and there is no persisted story/options or retry/continue path.

The fix must treat generation as a recoverable operation:
- persisted completed event wins over local generating state;
- stale in-flight generation must expire into a retryable state;
- UI must offer a clear long-running message and recovery action before a hard failure.

### Protagonist Identity

Story prompts previously accepted `player_name` as an optional explicit argument. Normal calls provided `player_state.player_name` but did not pass the explicit argument, so generated prompts could omit the canonical name. Ancient detective settings can therefore drift into famous/template figures. The prompt layer must derive protagonist identity from `player_state` by default.

### Collection Recognition

Collection design should be asymmetric:
- Characters: every concrete named person appearing in accepted story text should be collectable, excluding the protagonist duplicate and generic titles.
- Items/landmarks: only important or repeated entities should be collected, to avoid noise.

### Browser Click Stability

If DOM click works but normal browser click does not, the likely causes are overlay layering, oversized fixed elements, unstable animation hit targets, or clickable content not mapped to the actual button element. The fix should be verified by real Playwright/agent-browser behavior, not only unit tests.

## Worktree Ownership

- `codex/p0-generation-recovery-timeout`: generation/recovery tests and code only.
- `codex/p2-collection-entity-recognition`: entity recognition/collection tests and code only.
- `codex/p2-browser-click-stability`: browser interaction tests and frontend hit-target fixes only.
- `codex/gameplay-blockers-integration`: OpenSpec artifacts, merge resolution, final gates.
- Root checkout currently owns protagonist prompt lock changes already started before this split; integration will merge that as a separate slice.

Full browser/dev-server runs and `./test.sh all` are reserved for the integration worktree.
