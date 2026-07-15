# Reject no-op story rewrites

## Why

The rewrite provider can return the original story unchanged. The current path treats that
response as successful, persists it, and tells the player that the story was rewritten even
though the visible diff is empty.

## What Changes

- Treat output that is equal to the input after whitespace normalization as a failed rewrite.
- Preserve the original story and send an error through the existing API/SSE failure path.
- Cover both service-level rejection and the resulting streaming error contract.

## Impact

- Affected code: `src/ai/story_rewriter.py`, rewrite SSE behavior, focused rewrite tests.
- No database schema or persisted-state format changes.
