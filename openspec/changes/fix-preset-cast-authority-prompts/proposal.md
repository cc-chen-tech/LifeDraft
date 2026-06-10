## Why

The 2026-06-08 UX report shows a P0 narrative quality failure: preset key people such as 陆昊然、陈晓雨、林一凡 were absent from generated gameplay, while an invented substitute character replaced the intended relationship network. Current prompts expose available names, and validators can reject some bad generations after the fact, but generation prompts and the world model do not inject the preset cast as authoritative relationship facts.

## What Changes

- Add a relationship authority helper that extracts canonical preset key people from character settings, including both `relationships.key_people` and legacy `relationships: [...]` payloads.
- Inject canonical names, roles, relationship labels, and a no-rename/no-substitute rule into main event, story-only, and round-event prompts.
- Require each generated round to use at least one canonical preset key person, preventing the "0 出场" failure mode even when no invented substitute is detected.
- Carry the same preset cast authority into WorldModel constraints so later rounds preserve the relationship network.
- Extend the same authority and realistic-world boundary to post-choice story continuation prompts.
- Run post-choice continuations through fast local drift validation before they are saved or returned.
- Prevent story-character synchronization from promoting a newly invented named person
  when that name is introduced as a substitute for an existing preset relationship
  role, such as a new "mentor" replacing the canonical mentor.
- Add no-mock import and contract coverage wired into `test.sh` before implementation.

## Impact

- Backend prompt construction for main event, story-only, and round-event generation.
- Backend prompt construction and validation for choice-result continuations.
- WorldModel constraints built from `PlayerState.character_settings`.
- Legacy character creation payloads where `relationships` is already a list of key people.
- Import validation and contract tests.
- No database migration or frontend UI change is required.
