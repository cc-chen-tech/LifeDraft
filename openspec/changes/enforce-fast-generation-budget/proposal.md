## Why

Production QA measured both fast and master generation at roughly 80-120 seconds. Fast mode still produced more than 2,000 Chinese characters and displayed long logic-validation waits. The fast profile declares zero AI validation and retry, but round generation omits `quality_level` from its prompt call, always requests 8,192 tokens, performs a quick-validation regeneration, and invokes AI consistency whenever a world model exists.

## What Changes

- Define one typed execution budget for fast, expert, and master generation.
- Pass the selected quality level into round prompts and use distinct length requirements.
- Cap fast-mode output tokens and prohibit secondary model calls for quick or AI consistency validation.
- Preserve deterministic local validation diagnostics without delaying fast delivery.
- Expose the active fast stage and bounded expectation in the existing progress surface.
- Add no-mock static, prompt, contract, DB, and browser progress coverage through `test.sh`.

## Capabilities

### New Capabilities
- `fast-generation-budget`: Defines observable latency and validation differences among generation quality levels.

### Modified Capabilities

## Impact

- Story generator execution policy and round-event prompt.
- Loading progress text for quality-aware generation.
- Quality settings persistence and E2E progress verification.
