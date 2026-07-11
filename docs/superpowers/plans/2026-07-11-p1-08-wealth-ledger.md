# P1-8 Authoritative Wealth Ledger Implementation Plan

## Goal

Keep the numeric `PlayerState.wealth` balance authoritative while making every
gameplay balance change source-linked, auditable, and idempotent. Story,
summary, assistant, and UI consumers must agree with that structured balance.

## Design

1. Add a versioned wealth ledger containing opening balance, ordered
   transactions, and diagnostic conflicts. Each transaction stores a stable ID,
   opening balance, applied delta, reason, source event, week/round, and closing
   balance.
2. Seed legacy and new saves from the numeric player balance without inventing
   historical transactions. Keep the ledger mirror synchronized, but never use
   narrative prose to overwrite `PlayerState.wealth`.
3. Route standard choices, custom choices, legacy decisions, and weekly wealth
   bonuses through idempotent ledger transactions instead of direct wealth
   mutation.
4. Inject the current balance and active transaction into event, continuation,
   and weekly-summary prompts. Validate exact balance/change claims locally;
   reject and retry mismatches, then deterministically remove or correct
   unsupported precision.
5. Add balance and recent transaction evidence to the read-only assistant so
   cited money answers resolve to the same structured authority.
6. Keep the existing frontend player-state balance as the display consumer; add
   contract coverage proving it receives the ledger closing balance.

## TDD sequence

1. Unit-test ledger seeding, arithmetic, insufficient-funds clamping,
   idempotency, conflict recording, serialization, and exact-claim validation.
2. Add choice/finalizer integration tests proving one transaction per stable
   source and `closing = opening + delta` across at least twelve rounds.
3. Add story/summary/assistant tests for supported balance claims, rejected
   invented changes, and deterministic non-precise fallback.
4. Implement the ledger and integrations minimally until the red tests pass.
5. Add all regressions to preflight, then run focused tests, static checks,
   preflight, full backend classification, and a deterministic production
   browser/API smoke.

## Non-goals

- Do not create a second spendable balance separate from `PlayerState.wealth`.
- Do not infer transactions from old story prose.
- Do not redesign currencies, shops, investments, or the frontend status bar.
