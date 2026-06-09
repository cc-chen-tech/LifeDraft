## Why

The 2026-06-08 UX report shows a P0 narrative quality failure: preset key people such as 陆昊然、陈晓雨、林一凡 were absent from generated gameplay, while an invented substitute character replaced the intended relationship network. Current prompts expose available names, and validators can reject some bad generations after the fact, but generation prompts and the world model do not inject the preset cast as authoritative relationship facts.

## What Changes

- Add a relationship authority helper that extracts canonical preset key people from character settings.
- Inject canonical names, roles, relationship labels, and a no-rename/no-substitute rule into story prompts.
- Carry the same preset cast authority into WorldModel constraints so later rounds preserve the relationship network.
- Extend the same authority and realistic-world boundary to post-choice story continuation prompts.
- Run post-choice continuations through fast local drift validation before they are saved or returned.
- Add no-mock import and contract coverage wired into `test.sh` before implementation.

## Impact

- Backend prompt construction for story-only and round-event generation.
- Backend prompt construction and validation for choice-result continuations.
- WorldModel constraints built from `PlayerState.character_settings`.
- Import validation and contract tests.
- No database migration or frontend UI change is required.
