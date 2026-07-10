## Context

Quality profiles exist but only the harness retry loop consumes part of them. Prompt length, provider token budget, quick-validation regeneration, and world-model AI consistency use fixed behavior, so fast mode has nearly the same critical path as higher modes.

## Goals / Non-Goals

**Goals:**
- Make fast mode materially shorter by construction, not by UI label alone.
- Guarantee at most one story-generation provider call before option generation in fast mode.
- Keep local critical checks while skipping secondary AI validation.
- Show users that fast generation is in its bounded generation stage.

**Non-Goals:**
- Guaranteeing network latency from an external provider.
- Removing option generation.
- Weakening expert or master behavior.

## Decisions

1. Add a frozen execution-budget mapping keyed by `QualityLevel` with target length, max output tokens, quick-regeneration permission, AI-consistency permission, and expected duration.
2. Fast targets 350-600 Chinese characters (or 250-450 English words), uses at most 2,048 output tokens, and permits no secondary story model call.
3. Expert keeps balanced 800-1,200 character output and existing validation; master retains 1,500-2,000 characters and strict validation.
4. The round prompt receives the actual selected level and renders one unambiguous length instruction.
5. Quick validation remains local in fast mode; failures become diagnostics rather than a second provider call. AI consistency is skipped according to the profile.
6. Progress UI derives the active expectation from the same execution budget to avoid label/behavior drift.

## Risks / Trade-offs

- [Fast output has a critical local warning] -> Return the single generated result with diagnostics instead of hiding another long model call; hard fallback still applies when output is unusable.
- [Provider ignores length] -> Token cap and prompt limit work together; contract tests verify both.
- [Expectation is mistaken for a guarantee] -> Use “通常” and continue showing actual elapsed time.
