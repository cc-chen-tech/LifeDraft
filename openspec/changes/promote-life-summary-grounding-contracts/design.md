## Context

The life-summary grounding module is currently low coverage in the maintained gate. Its deterministic contracts verify range-aware prompt construction, unsafe-summary fallback, real DB history reads, and production import reachability without external providers.

## Goals / Non-Goals

**Goals:** Gate summary evidence and persistence regressions early.

**Non-Goals:** Change summary behavior or call a live generation provider.

## Decisions

- Promote the pure, DB, and import suites together because all protect one summary boundary.
- Preserve the current floor unless the full maintained suite reaches the next integer.

## Risks / Trade-offs

- [DB fixture state leaks] -> The test creates and removes its own game and user rows and passed repeatedly.
