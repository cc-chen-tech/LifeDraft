## Why

Production QA found a week 1-4 life summary calling the period "less than half a year", endorsing an apparent non-compete workaround as compliant, merging contradictory events into certain facts, and displaying resource metrics that conflict with the story ledger. The summary model currently receives raw history plus mutable resource values and its output is returned without grounding checks.

## What Changes

- Build life-summary prompts with an exact week range and explicit evidence-only rules.
- Stop injecting energy, mood, knowledge, and wealth metrics into life summaries.
- Require contradictory source claims to remain unresolved instead of being reconciled by invention.
- Forbid describing evasive or disputed legal conduct as compliant or lawful.
- Reject ungrounded generated summaries and fall back to deterministic source excerpts.
- Add no-mock contract, real DB, and browser-panel coverage through `test.sh`.

## Capabilities

### New Capabilities
- `life-summary-grounding`: Defines evidence, timeline, legal-claim, and metric boundaries for life summaries.

### Modified Capabilities

## Impact

- Life-summary API prompt construction, output validation, and fallback behavior.
- Summary panel text shown by `ChatBar`.
- Static, import, contract, DB, and Playwright gates.
