## Why

Production QA found a realistic world regeneration presenting invented certifications, filing requirements, fixed approval timelines, GDP figures, and venture-capital statistics as real facts. Those claims are persisted and then reused as hard constraints by later story generation.

## What Changes

- Add explicit factual-safety instructions to realistic world-setting prompts.
- Treat unsupported named regulations, certifications, precise statistics, and fixed process timelines as fictional scenario assumptions.
- Deterministically qualify high-precision generated world claims before persistence and downstream prompt reuse.
- Preserve ordinary qualitative world descriptions without adding unnecessary warnings.
- Add no-mock prompt, contract, real DB, and browser-display coverage through `test.sh`.

## Capabilities

### New Capabilities
- `world-fact-safety`: Defines how generated world settings distinguish story assumptions from real-world facts.

### Modified Capabilities

## Impact

- Character world-setting prompt construction and generation result validation.
- Persisted character settings consumed by later story prompts.
- World-setting display in character creation and gameplay settings.
