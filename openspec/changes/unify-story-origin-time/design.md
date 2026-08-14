## Context

Daily timeline v2 already makes `start_date + day_index` authoritative during
play, but character creation still produces `start_date`, `era.year`,
`age.age`, and `age.birth_year` through independent controls and AI calls. The
initializer silently reconciles the numeric values only after the UI has shown
them, and a late settings patch can diverge from an already-created day-zero
timeline. Character images and automatic background settings can also finish
after an upstream edit and restore stale content.

## Goals / Non-Goals

**Goals:**

- Make one validated `story_origin` the only creation-time authority for date,
  starting age, and their narrative context.
- Replace or rebase the origin atomically while the game is still an unplayed
  draft, with revision fencing for concurrent generation and media work.
- Preserve old games and presets through deterministic compatibility projection.
- Keep the existing 365-completed-day age rule and 672-day campaign.

**Non-Goals:**

- Adding birthdays, editing origins after play begins, rewriting played history,
  or removing all legacy `era` and `age` readers in this release.
- Changing the deterministic daily timeline, choice settlement, or ending rules.

## Decisions

### Canonical origin and compatibility projection

New creation stores `story_origin = {revision, start_date, starting_age,
era_description, life_stage_description, world_context}`. A focused domain
module validates the exact Gregorian date, bounded integer age, non-empty text,
and explicit date/year/age anchors in the life vision or feedback. It projects
top-level `start_date`, `era`, and `age` fields for legacy consumers. Projected
`birth_year` is never shown or treated as narrative authority.

This keeps the rollout additive while preventing callers from calculating the
same values independently. Replacing only `era` or `age` was rejected because it
would retain the current multi-authority model.

### Candidate-first AI generation

`POST /api/character/story-origin` generates the whole structure in one call.
The candidate is normalized and validated before being returned; explicit
feedback anchors are hard requirements. Generation failure returns an error and
does not mutate an existing origin. The old generic setting endpoint remains for
legacy clients but the new frontend never requests `era` or `age` separately.

### Draft compare-and-swap rebase

`PATCH /api/games/{game_id}/story-origin` accepts `expected_revision` and a full
candidate. It is allowed only when the owned daily game has no current event,
day history, or advanced day. In one durable save it increments the revision,
reprojects compatibility fields, resets day zero and age milestones, preserves
identity and gender, and removes world, portrait-dependent metadata, family,
relationships, traits, and matched narrative style. A stale revision returns a
conflict; a played game returns `story_origin_locked`.

Frontend asynchronous work captures the origin revision and discards stale
setting results. Character image jobs persist the revision in their request
metadata and verify it before publishing an image, so invalidated work cannot
reappear after a rebase.

### Creation flow and preset compatibility

The manual flow becomes story origin, gender, world, portrait. Origin feedback
always regenerates the full card. Accepting a replacement invalidates dependent
settings and returns the user to world generation; gender remains valid.

Old presets synthesize an origin from a valid top-level date or the era year's
January 1 and `age.age`. If explicit years in preserved narrative text disagree
with the chosen date, the preset is marked `story_origin_needs_review` and cannot
start until a new origin is generated. Played games remain untouched and can
continue using compatibility fields.

## Risks / Trade-offs

- [A single origin call contains more fields] → Validate field-by-field and keep
  the previous candidate on any failure.
- [Rebasing invalidates costly generated content] → Limit it to unplayed drafts,
  make the consequence explicit, and fence stale jobs by revision.
- [Legacy consumers still read projected fields] → Centralize projection in one
  helper and add contract tests preventing independent recomputation.
- [Old preset prose may contain ambiguous dates] → Only block confirmed numeric
  conflicts; otherwise preserve the text and require no AI migration.

## Migration Plan

1. Deploy additive origin validation, generation, projection, preset synthesis,
   and draft rebase APIs while retaining legacy fields.
2. Switch the frontend creator and generated API types to the four-step flow.
3. Fence background settings and character images with the origin revision.
4. Monitor origin-generation validation errors, stale revision conflicts, and
   legacy preset review rates before retiring legacy creation calls.
5. Rollback restores the old frontend entry; additive origin fields and projected
   compatibility data remain readable without rewriting played saves.

## Open Questions

None. Product choices are fixed by the approved implementation plan.
