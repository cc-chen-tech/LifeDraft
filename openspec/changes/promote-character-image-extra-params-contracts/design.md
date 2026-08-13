## Context

Image generation is an external provider boundary. The candidate suite avoids
network calls by assigning minimal handwritten provider functions to an
uninitialized ImageGenerator and verifies public character-generation behavior.
Comparison against the maintained coverage JSON shows 14 newly exercised lines
in the extra-parameter forwarding path.

## Goals / Non-Goals

**Goals:**
- Promote the deterministic provider-boundary contract suite.
- Preserve ordered workflow parity and prove the 51% coverage gate before
  raising it.

**Non-Goals:**
- Change production generation logic or pre-existing tests.
- Emulate the full remote image provider or introduce a mock framework.

## Decisions

- Accept the handwritten fake only at the actual image-provider method
  boundary; it captures invocation arguments and returns simple protocol data.
- Add the file adjacent to other image tests in both maintained selections.
- Use a coverage-JSON non-overlap check before promotion and an exact full 51%
  run before updating the workflow threshold.

## Risks / Trade-offs

- [The fake diverges from the provider protocol] → It returns the existing
  method's documented tuple shape and tests the public forwarding contract.
- [Global result falls below 51%] → Keep the previous threshold.
- [Workflow drift] → Compare parsed ordered selections before commit.
