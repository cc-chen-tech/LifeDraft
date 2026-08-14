## Why

Character creation currently treats the exact story date, AI-selected era year,
starting age, and derived birth year as separate authorities. They can disagree
in the UI and are only silently reconciled when the game is initialized, leaving
the saved timeline and descriptive setting text out of sync.

## What Changes

- **BREAKING** Replace the separate era and age creation steps plus the optional
  date input with one atomic `story_origin` generation step.
- Generate and validate the exact Gregorian start date, starting age, era
  description, life-stage description, and world context as one candidate.
- Allow origin changes only through whole-card feedback regeneration; never
  expose birth year as a generated or player-facing authority.
- Rebase unplayed draft games with compare-and-swap origin revisions, invalidate
  all time-dependent downstream settings and media, and lock the origin when day
  one begins.
- Project legacy `start_date`, `era`, and `age` fields for compatibility while
  making `story_origin` canonical for new creation, prompts, presets, and media
  generation.

## Capabilities

### New Capabilities
- `story-origin`: Atomic story-origin generation, validation, draft replacement,
  revision fencing, and legacy preset normalization.

### Modified Capabilities
- `character-setting-continuity`: Character creation and downstream generation
  consume one coherent date-and-age origin and invalidate dependent settings
  after an origin replacement.
- `gameplay-continuity`: Daily gameplay starts from the canonical origin date and
  prevents origin mutation after the first playable event exists.

## Impact

This affects character-generation prompts and APIs, game initialization and
draft persistence, preset compatibility, character-image job fencing, frontend
creation state and displays, generated OpenAPI types, and character-creation
unit, database, and browser tests. Existing played games and their histories are
not rewritten.
