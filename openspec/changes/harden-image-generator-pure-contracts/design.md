## Context

`src/ai/image_generator.py` contains deterministic protocol logic around MiniMax request construction and safe response handling. Existing integration contracts exercise the provider boundary but use environment mutation or HTTP servers, so they are excluded from the maintained no-mock selection.

## Goals / Non-Goals

**Goals:**
- Cover deterministic image-generator behavior with direct in-process assertions.
- Capture payload limits, caller overrides, safe decoding, and typed error semantics.
- Add the new suite to both maintained workflow lists with exact parity.

**Non-Goals:**
- Make a real provider request, mutate environment or configuration, or patch a dependency.
- Duplicate integration tests for HTTP headers, retries, or image downloads.
- Modify production behavior.

## Decisions

- Construct `ImageGenerator` with explicit inert credentials and only invoke helper methods that cannot call its session. This avoids the provider entirely while exercising production code.
- Assert observable payload and exception attributes rather than implementation internals such as local variables or logs.
- Cover both valid and malformed inputs because safety regressions arise from normalization boundaries.
- Add one focused test file rather than altering existing provider tests, preserving their broader integration role.

## Risks / Trade-offs

- [Helper contracts drift from integration behavior] -> The suite invokes the production methods directly and leaves end-to-end provider tests in their existing layer.
- [Constructor starts a retry session] -> No helper invokes it; tests use only local values and do not issue HTTP.
- [Coverage gain is limited relative to the whole module] -> Follow this batch with DB/service contracts for image persistence and scene generation.
