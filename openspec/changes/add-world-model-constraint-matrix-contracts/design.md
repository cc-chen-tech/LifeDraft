## Context

WorldModel assembles locations, careers, commitments, causal chains, physical state, dynamic facts, character profiles, and required relationships into story-generation constraints.

## Goals / Non-Goals

**Goals:** gate category preservation and Chinese/English rendering using concrete persisted state structures.

**Non-Goals:** change constraint prose, invoke AI, or construct a database session.

## Decisions

- Populate a concrete WorldModel directly with production dataclasses.
- Assert category-specific fragments and resolved-chain exclusion instead of a brittle full-text snapshot.

## Risks / Trade-offs

- [Workflow drift] -> validate ordered workflow parity and the full maintained gate.
