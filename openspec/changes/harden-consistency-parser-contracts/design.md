## Context

Parser behavior is pure local JSON transformation when invoked directly.

## Goals / Non-Goals

**Goals:** cover retry semantics, severity normalization, and fix guidance with no doubles.

**Non-Goals:** call AI, alter production logic, or modify existing tests.

## Decisions

- Instantiate with `None` and invoke the parser only.

## Risks / Trade-offs

- [Private method] -> exercise its stable observable `ValidationResult` contract.
