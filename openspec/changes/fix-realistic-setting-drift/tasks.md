## 1. Tests

- [x] Add no-mock prompt contract coverage for realistic modern settings forbidding unrequested cyberpunk/IP-world drift.
- [x] Verify the new prompt contract fails before production code changes.
- [x] Add runtime quick-validator coverage for modern stories drifting into "夜之城"/"荒坂"/"Viktor"/义体.
- [x] Add StoryGenerator round-event retry coverage for modern stories drifting into external cyberpunk/IP worlds.

## 2. Fix

- [x] Add reusable realistic-modern setting boundary constraints.
- [x] Inject those constraints into opening-story, story-only, and round-event prompts without blocking explicit cyberpunk settings.
- [x] Reject unrequested cyberpunk/IP terms during modern-era quick validation.
- [x] Preserve explicit original cyberpunk settings without allowing external IP proper nouns.

## 3. Verify

- [x] Run `openspec validate fix-realistic-setting-drift --strict`.
- [x] Run targeted prompt contract tests.
- [x] Run `./test.sh preflight`.
- [x] Run `./test.sh all`.
