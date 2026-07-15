## Context

`RoundIllustrationService` turns narrative state into a small set of image references before provider calls. Entity selection determines whether recurring people, props, and settings remain visually consistent, and it can be tested without a provider or database.

## Goals / Non-Goals

**Goals:**
- Verify the public selection helpers with fixed narrative state.
- Preserve the priority order: characters, repeated items, then locations, with bounded output.
- Exercise malformed dynamic-fact tolerance and source de-duplication.

**Non-Goals:**
- Generate images, submit work to the executor, or alter selection algorithms.

## Decisions

- Instantiate the service without calling its constructor because these helpers do not require dependencies.
- Assert whole selected entity tuples where order is the contract, rather than implementation-local intermediate lists.
- Use repeated fact data to prove the three-occurrence rule instead of testing regular-expression item extraction.

## Risks / Trade-offs

- [Rules evolve with world-model schemas] → Tests use canonical `established_facts`, `dynamic_facts`, and `character_locations` shapes.
- [Selection does not prove an image provider renders every reference] → Provider rendering stays in integration/browser scope.
