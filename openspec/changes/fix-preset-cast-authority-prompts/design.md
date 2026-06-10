## Root Cause

Character settings can include structured key people with role and relationship semantics, but the story prompts reduce that information to a plain name list. The world model also omits these preset cast entries, so continuity constraints only mention facts learned from prior stories. When the model needs a friend, mentor, or colleague, it can satisfy the loose narrative shape by inventing a new person and drifting that substitute's identity over time.

## Design

- Extract required preset cast entries from `character_settings.relationships.key_people`.
- Treat legacy `character_settings.relationships` list payloads as the same canonical key-people list instead of dropping or crashing on them.
- Preserve each entry's canonical `name`, `role`, `relationship`, and description fields.
- Build a concise prompt block marked as mandatory:
  - all preset key people are canonical relationship facts;
  - names must be used exactly;
  - at least one canonical preset key person must appear in each generated round;
  - roles/relationships must not be transferred to invented substitutes;
  - unspecified bystanders may only use generic labels.
- Add the block to:
  - story-only prompts;
  - round-event prompts;
  - WorldModel constraint text generated from player state.
- Keep generation validation separate; this change shifts the constraint left into prompt and world model assembly.

## Non-goals

- Rewriting the full story quality validator.
- Guaranteeing that every key person appears in every round; the required minimum is one canonical preset key person per generated round.
- Changing frontend character creation UI.
- Merging the broad older combined P0/music/wealth PR.
