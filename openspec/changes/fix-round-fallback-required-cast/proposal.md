## Why

Round-event generation now rejects stories that drift away from preset key people
or modern realistic settings. However, when the model fails quick validation twice,
the fallback story preserves the era but does not mention any preset key person.
That still produces the user-visible symptom from the UX report: the intended
mentor/friend/peer network can disappear from the round.

## What Changes

- Add regression coverage for validation-failure fallback preserving preset cast.
- Include the first canonical preset key person in the round fallback story when
  character settings define required key people.
- Keep the existing safe fallback behavior for games without preset key people.

## Impact

- `src/ai/story_generator.py`
- `tests/test_generate_round_event_retry.py`
