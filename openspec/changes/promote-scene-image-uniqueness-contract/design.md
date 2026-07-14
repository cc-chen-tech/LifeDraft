## Context

`SceneImage` is keyed by a game and gameplay position. The existing contract uses SQLAlchemy table metadata only, has no provider or database-server dependency, and verifies the composite index that prevents duplicate image records during retries. Both maintained workflows must remain an ordered-parity selection.

## Goals / Non-Goals

**Goals:**

- Add the deterministic existing contract to each maintained backend workflow.
- Preserve workflow selection order and run the complete maintained suite before changing a coverage threshold.

**Non-Goals:**

- Change the SceneImage schema, persistence implementation, or application behavior.
- Replace a real database concurrency test with metadata inspection.
- Raise the coverage threshold unless a strict candidate run proves the precise total reaches it.

## Decisions

- Promote the existing test instead of duplicating it because it already checks the intended schema invariant without mocks or environment mutation.
- Append it at the end of each ordered selection, keeping the two lists identical and minimizing diff churn.
- Treat the reported coverage percentage as insufficient evidence for a threshold increase; rerun with the candidate `--cov-fail-under` value.

## Risks / Trade-offs

- [Metadata cannot prove write-time race behavior] -> Keep DB concurrency coverage as a separate future change.
- [Rounded coverage output can overstate the exact total] -> Require a strict candidate gate run before editing the threshold.
- [Workflow lists can drift] -> Compare extracted selections before committing.
