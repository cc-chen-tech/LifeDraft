# Design: Reject no-op story rewrites

## Decision

Compare the final returned story with the original story after normalizing line endings,
trimming leading/trailing whitespace, and collapsing blank-line-only differences. If the
normalized texts are equal, raise `StoryRewriteFailure` before a router can persist the result.

## Rationale

The service owns the semantic contract that a successful rewrite must change the story. Keeping
the check below the provider call makes both synchronous and SSE routes use the same behavior.
Whitespace-only changes are not player-visible rewrites; substantive prose edits remain valid.

## Failure behavior

Existing router and SSE exception handling already keep the original story unchanged and present
an error. No synthetic replacement text is introduced.
