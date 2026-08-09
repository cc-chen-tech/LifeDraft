## Context

`test_validation_pipeline_contract.py` runs 11 deterministic tests without mocks, providers, databases, or skip behavior. It constructs a real registry and definitions to exercise the public pipeline API.

## Goals / Non-Goals

**Goals:** promote the verified suite symmetrically and retain an evidence-based coverage floor.

**Non-Goals:** change validators, production pipeline behavior, or existing tests.

## Decisions

- Reuse the existing focused suite instead of duplicating it.
- Require two focused and two expanded maintained runs before a ratchet.

## Risks / Trade-offs

- [Gate time increase] -> The suite is in-process and completes in milliseconds.
