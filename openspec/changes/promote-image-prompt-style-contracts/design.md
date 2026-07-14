## Context

Appearance anchors, prompt enhancement, and style management are local control layers between game state and image-provider calls. Their existing tests exercise serialization, temporary local persistence, matching, palette construction, and temporal style adjustments without contacting a provider.

## Goals / Non-Goals

**Goals:**
- Include deterministic image-control regressions in both maintained workflows.
- Catch prompt and appearance drift before provider calls or browser review.

**Non-Goals:**
- Change image generation behavior, existing tests, or provider integration.
- Run browser or network tests in the maintained gate.

## Decisions

- Promote the three suites as one image-control boundary: appearance definitions feed prompt enhancement and style selection.
- Keep provider-facing scene generation excluded; its behavior remains covered by focused existing contract tests.
- Verify isolated execution, parity, strict specification validation, and the entire maintained coverage command.

## Risks / Trade-offs

- [Temporary-file persistence] → The existing suite uses its established temporary storage isolation and is run inside the complete gate.
- [Global style-manager state] → Tests validate both per-game and global state; full-order execution detects leakage.
- [Workflow drift] → Compare the extracted ordered workflow lists before commit.
