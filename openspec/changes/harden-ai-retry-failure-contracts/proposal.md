# Harden AI Retry Failure Contracts

## Why

Provider failures and malformed AI responses should fail within the retry layer,
before gameplay or browser tests wait for external AI behaviour.

## What Changes

- Add deterministic provider-fake contracts for timeout retry, JSON recovery, and
  retry exhaustion.
- Verify retry feedback, temperature decay, and stream callback behavior.
- Add the contracts to the maintained backend manifest.

## Scope

This change adds tests, test selection, and OpenSpec artifacts only.
