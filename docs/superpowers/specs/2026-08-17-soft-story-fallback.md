# Soft Story Fallback Design

## Goal

Prevent generation from ending on a blank screen when the retry budget contains a renderable draft with only non-blocking quality warnings, without ever displaying a draft rejected by a hard safety or continuity check.

## Delivery boundary

- A candidate with no blocking findings is delivered normally.
- A candidate with only soft quality warnings may enter the fallback pool.
- A candidate with any hard finding, empty output, broken structure, or unsafe content never enters the fallback pool.
- The generator keeps trying within the configured quality budget (fast 1, expert 3, master 10) after a soft-warning candidate.
- If no clean candidate is produced, the best soft-warning candidate is selected deterministically.
- If no deliverable candidate exists, generation raises the existing structured `StoryGenerationFailure`; replacement keeps the previously committed story visible.

## Ranking

Rank soft-warning candidates by:

1. fewer soft warnings;
2. higher Harness validation score;
3. longer complete story text;
4. earlier provider request as a stable tie-breaker.

## Player-facing contract

- A normal event has no delivery notice.
- A soft fallback event persists a sanitized `delivery_notice` with a short reason, retry affordance, and attempts used.
- The reading page shows that notice as subdued small text below the story and offers regeneration.
- Raw validator diagnostics, prompts, and rejected hard-error drafts are never exposed.

## Transaction boundary

Only the selected event is returned and persisted. Rejected candidates never update committed event, options, relationship state, or world state. Regeneration continues to preserve the old committed event until a replacement succeeds atomically.
