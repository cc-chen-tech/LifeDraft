## Context

Option generation is the second half of a playable event. Its failure must not invalidate an already complete story. The current generator validates the response as one all-or-nothing group, and the UI assumes that options are either all present or the whole page failed.

## Goals / Non-Goals

**Goals:** exactly three options for new events; item-level validation and repair; deterministic completion when the provider fails; compatibility with stored two-to-four option events; stable accessible two-line controls; story-preserving pending state.

**Non-goals:** changing saved legacy rows, introducing new request input limits, redesigning summary/memory, or enabling rollout flags in production.

## Decisions

### One localized display budget

Add a resolver beside narrative budgets. Chinese length uses the existing Unicode-character measurement policy; English uses word measurement. Target length is prompt guidance, while the higher repair threshold determines whether an otherwise usable item requires repair.

### Validate and merge by item

Normalize each candidate, retain the first valid unique options in source order, and identify only missing/invalid slots. A single repair call requests replacements for those slots while including retained texts as exclusions. Merge valid repairs; fill remaining slots with contextual deterministic options that are unique from retained and recent choices.

### Compatibility at the persistence boundary

Newly completed events must contain exactly three options. Existing persisted events with two, three, or four options remain valid for restore and display. No database migration or silent rewrite is performed.

### Story and options have separate presentation states

If story text exists, it remains rendered while options are pending. The loading copy is inline and calm. A page-level retry belongs only to a state with no usable story.

### Accessible truncation

The visual control is limited to two lines with CSS line clamping, but the button accessible name and title preserve the complete option text. Selection immediately disables all controls and marks the chosen option as entering/loading.

## Risks / Trade-offs

- Deterministic fallback text may be less literary, but it preserves playability and only fills missing slots.
- Legacy four-option saves remain visually denser; compatibility is preferred over mutating history.
- CSS clamping hides visual overflow, so full accessible naming and title text are mandatory.

## Rollout

Land behind the existing unified narrative rollout stack, exercise deterministic E2E with a single malformed option, and keep production enablement outside this PR.
