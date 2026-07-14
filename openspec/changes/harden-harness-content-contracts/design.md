## Context

The pure `validators.py` contract suite is stable but not maintained. `item_continuity_validator.py` and deterministic functions in `narrative_validators.py` have low coverage; the latter's existing suite uses a mock only for provider-like import degradation.

## Goals / Non-Goals

**Goals:**
- Cover public content validation APIs with concrete local dictionaries and text.
- Promote only the already verified no-double existing suite.
- Preserve workflow parity and evidence-based threshold changes.

**Non-Goals:**
- Modify existing tests, production validators, or cover mock-dependent pacing-import behavior.

## Decisions

- Add a focused no-double file for item and deterministic narrative functions instead of changing the existing narrative test file.
- Promote `test_harness_validators_contract.py` only after repeated local runs.
- Retain the current floor unless two expanded runs support the next integer threshold.

## Risks / Trade-offs

- [Text rules are heuristic] -> Use unambiguous texts and assert structured validator results.
- [Larger gate] -> All selected tests are pure in-process functions.
