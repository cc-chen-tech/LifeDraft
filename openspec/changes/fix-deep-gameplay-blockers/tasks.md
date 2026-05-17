# Tasks

## 1. Generation Recovery / Timeout

- [x] 1.1 Reproduce week-2-style stale generating state locally with active game state containing no visible story/options.
- [x] 1.2 Add failing backend and/or frontend tests that refresh/recovery never restores a no-body generating state when a completed event or retry path exists.
- [x] 1.3 Implement stale generation expiry, recovery precedence, and retry/continue UX.
- [x] 1.4 Run targeted tests for gameplay recovery and SSE timeout behavior.

## 2. Protagonist Identity Lock

- [x] 2.1 Add prompt contract tests for opening, week, and round prompts with `林见微` / `女`.
- [x] 2.2 Ensure prompts derive canonical protagonist name from `player_state` or request payload without requiring optional explicit args.
- [x] 2.3 Run targeted prompt tests.

## 3. Collection Recognition

- [x] 3.1 Reproduce story text containing named people plus many items/locations where collection misses characters.
- [x] 3.2 Add failing tests: all concrete story people are recognized; incidental items are filtered unless important/repeated.
- [x] 3.3 Implement recognition fallback/normalization and collection merge behavior.
- [x] 3.4 Run targeted collection/entity tests.

## 4. Browser Click Stability

- [x] 4.1 Reproduce normal-click failures with agent-browser or Playwright on week progression, ChatBar, and choice buttons.
- [x] 4.2 Add failing browser/component tests that detect overlay or hit-target blocking.
- [x] 4.3 Fix z-index/pointer-events/button ownership without changing unrelated UI.
- [x] 4.4 Run targeted browser/component tests.

## 5. Integration

- [x] 5.1 Merge worker branches into `codex/gameplay-blockers-integration`.
- [x] 5.2 Resolve conflicts only in integration.
- [x] 5.3 Run `openspec validate fix-deep-gameplay-blockers --strict`.
- [x] 5.4 Run targeted suites for all fixed areas.
- [x] 5.5 Run `./test.sh all` from integration worktree.
