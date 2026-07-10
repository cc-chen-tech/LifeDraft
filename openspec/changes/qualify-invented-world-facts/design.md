## Context

World generation currently asks for detailed technology, social-system, and economic descriptions but gives the model no epistemic boundary. A request for concrete compliance constraints therefore encourages plausible-looking invented names and numbers, and the unvalidated JSON is stored verbatim.

## Goals / Non-Goals

**Goals:**
- Prevent unsupported generated claims from looking like verified real-world facts.
- Keep the safety treatment visible after persistence and in downstream story context.
- Leave low-precision qualitative descriptions readable.

**Non-Goals:**
- Fact-checking every jurisdiction against an external legal database.
- Removing fictional regulations from explicitly fictional worlds.
- Rewriting existing saves.

## Decisions

1. The world prompt explicitly forbids presenting model-invented legal names, certifications, official procedures, statistics, or exact timelines as verified facts.
2. Illustrative details remain allowed only when clearly described as story assumptions rather than real guidance.
3. A deterministic production boundary scans generated world text for high-precision regulatory, certification, percentage, and fixed-duration signals. Matching fields receive a localized story-assumption qualifier before they can be saved.
4. The qualifier is idempotent so regeneration, API retries, and save-read cycles cannot duplicate it.
5. Browser coverage uses the real API and database to prove the qualifier remains visible in the world settings panel.

## Risks / Trade-offs

- [A legitimate user-provided statistic is qualified] -> Prefer a visible caution over presenting an unverified generated claim as authoritative; future sourced-data support can carry provenance explicitly.
- [Pattern detection misses a novel claim form] -> Pair deterministic detection with prompt prevention and cover the concrete production failure shapes.
- [Warnings overwhelm ordinary prose] -> Only qualify fields containing precision or authority markers; leave qualitative fields unchanged.
