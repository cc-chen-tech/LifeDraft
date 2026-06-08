## 1. Tests

- [x] Add contract tests for post-search negative cue filtering of reported vocal-pop/meme failures.
- [x] Add contract tests for title-normalized de-duplication of cover/version variants.
- [x] Run the new tests before implementation and confirm they fail for the missing behavior.

## 2. Implementation

- [x] Implement canonical title normalization and generic no-vocal rejection cues.
- [x] Add filtered/deduped ranking output for music recommendations.
- [x] Use filtered/deduped ranking when selecting songs from the verified pool.

## 3. Verification

- [x] Run targeted music recommendation contract tests.
- [x] Run `openspec validate fix-music-negative-cue-dedupe --strict`.
- [x] Run `./test.sh all`.
