## 1. Tests

- [x] Add no-mock prompt contract coverage for realistic modern settings forbidding unrequested cyberpunk/IP-world drift.
- [x] Verify the new prompt contract fails before production code changes.

## 2. Fix

- [x] Add reusable realistic-modern setting boundary constraints.
- [x] Inject those constraints into opening-story, story-only, and round-event prompts without blocking explicit cyberpunk settings.

## 3. Verify

- [x] Run `openspec validate fix-realistic-setting-drift --strict`.
- [x] Run targeted prompt contract tests.
- [x] Run `./test.sh preflight`.
- [x] Run `./test.sh all`.
