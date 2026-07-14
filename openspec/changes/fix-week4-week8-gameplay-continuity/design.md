## Context

The game persists `round_history`, `decision_history`, and numeric state, then
reconstructs a `PlayerState` after a browser or server-session recovery. The newer
continuity and wealth ledgers are durable authorities for new games, but legacy saves
with an empty ledger only regain initial identity data. A later prompt can therefore
see a generic compressed summary instead of the player's committed action. Separately,
the normal choice path updates state before a provider-backed continuation is known to
be valid, and both custom-choice helpers fabricate plausible text/effects on failure.
Life-summary generation uses a five-minute provider timeout with no client deadline.

## Goals / Non-Goals

**Goals:**

- Preserve committed player actions and reliable source text across restored legacy
  saves, without inventing historical facts.
- Make a failed continuation or custom-choice evaluation atomic: no state, ledger, or
  history write is committed before a valid narrative outcome exists.
- Stop generated fallback prose/options from becoming repeated playable content.
- Return a bounded life-summary outcome and retain a responsive playable page.
- Keep music and illustration consumers tied to valid current story context only.

**Non-Goals:**

- Rewriting existing player histories or retroactively correcting text already shown.
- Guaranteeing semantic truth extraction from arbitrary prose.
- Replacing external AI providers, changing media providers, or changing the normal
  three-round weekly cadence.

## Decisions

### Reconstruct ledger timeline from durable rounds

When a ledger has no timeline, reconstruct a bounded, idempotent sequence from
`round_history` in `(week, round)` order. Each entry records the existing summary,
choice, date, and existing full story hash, and the constraints render both summary and
choice. This uses persisted source records rather than attempting NLP fact extraction.
The prompt can therefore distinguish a completed bookcase purchase or public event
from an opening-plan statement. Existing non-empty ledgers are never rewritten.

Alternative: parse all old prose into completed facts. Rejected because it would turn
uncertain model prose into authority and could create more continuity errors.

### Stage choice mutations before commit

Build a deep working copy of `PlayerState`, apply the requested resource transaction
and effects there, and use that staged state for continuation generation and validation.
Only after a valid continuation returns are the same deterministic mutations applied to
the live state and allowed into histories/ledgers. A typed generation failure leaves
the original event and all live state intact, enabling the existing choice retry flow.

Alternative: mutate then manually reverse effects and ledger entries. Rejected because
partial rollback can drift relationships, caps, and transaction ordering.

### Surface invalid generation instead of fabricating an outcome

Use one typed `StoryContinuationFailure` for unavailable providers, invalid custom
effects, empty continuations, and invalid retried continuations. SSE and synchronous
routes map it to a retryable failure while retaining the event. Contextual option
fallbacks remain only for a valid generated story and must be rejected when their
normalized texts duplicate the recent committed decision set.

Alternative: generate neutral prose/effects. Rejected because it falsely claims the
player action happened and poisons all downstream consumers.

### Bound life-summary latency twice

The summary endpoint runs the blocking provider operation behind a server deadline and
returns deterministic evidence-only fallback text on deadline or provider failure. The
browser uses a shorter abortable request deadline, clears loading in `finally`, and
shows a retryable error. The server fallback protects clients that do not use the web
UI; the client deadline protects an unhealthy proxy or older deployment.

Alternative: only add a client timeout. Rejected because a timed-out request can still
consume server capacity and leaves non-browser clients waiting.

## Risks / Trade-offs

- [Legacy source text may be noisy] -> Store it as evidence and show exact committed
  choice; do not promote it into immutable facts.
- [Provider operation continues after server timeout] -> Return immediately, cancel
  work that has not started, and keep it outside gameplay mutation; provider client
  timeout remains the final resource bound.
- [Strict failure surfaces may be more visible than generic fallback] -> Retain the
  current event and explicit retry instead of silently advancing a corrupt save.
- [Option retry can make recovery slower] -> Only run duplicate rejection when a
  fallback would match recent choices, and return an actionable error rather than loop.

## Migration Plan

1. Deploy the read-time ledger reconstruction. It writes only to the in-memory state
   and is persisted through the normal next save.
2. Deploy atomic choice handling and typed failure mapping together so no request
   advances partially.
3. Deploy bounded life summary at both API and client layers.
4. Roll back by reverting the change; existing ledger and history fields remain
   backward compatible because no schema migration is required.
