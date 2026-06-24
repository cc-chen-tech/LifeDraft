## Why

The deep UX report found that preset key people such as mentors, close friends, and peers could disappear from later stories. One concrete cause is schema drift: older frontend and persistence payloads may store a key person's role under `relation`, while the story authority layer only read `role` and `relationship`.

When `relation` is ignored, prompts still list names but lose the role function that tells the model which canonical person must be used for mentor/friend/peer scenes. That weakens the guardrail against invented replacements such as new mentors or friends.

## What Changes

- Treat `relation` as an alias for preset key-person role and relationship authority.
- Show relation-only key people with their role label in available-people prompt text.
- Keep prompt facts deduplicated when `relation` is copied into both role and relationship channels.
- Add regression tests for relation-only payloads.

## Impact

- Backend prompt helpers and relationship authority only.
- No API schema or database migration.
- Strengthens existing story drift validation without changing frontend behavior.
