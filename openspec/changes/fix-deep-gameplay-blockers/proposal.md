# Fix Deep Gameplay Blockers

## Why

Live gameplay can block before week 4: week 2 weekend generation may remain in a generating/analyzing state with no story, no options, and no usable recovery after refresh. Additional issues reduce trust in longer sessions: protagonist identity can drift away from the saved character, collection recognition misses story characters, and normal browser clicks can fail where DOM clicks work.

## What Changes

- Add robust generation recovery and timeout fallback for long-running story/choice generation.
- Lock protagonist name and gender into opening, week, and round story prompts.
- Improve collection recognition so named people appearing in story text are captured, while items and landmarks remain filtered to important entities.
- Stabilize real browser interaction hit targets for week progression, ChatBar, and choice buttons.

## Impact

- Backend gameplay/SSE recovery logic and persisted current event handling.
- Frontend play-state recovery, loading/timeout UX, and click target layering.
- Entity recognition and collection service behavior.
- Prompt contract tests and browser regression coverage.
