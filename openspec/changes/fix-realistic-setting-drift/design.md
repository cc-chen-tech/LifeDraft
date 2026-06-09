## Design

Modern setting drift currently has weak protection. `_build_era_anachronism_constraints` treats "future", "科幻", and "赛博" as modern-compatible cues, then emits only a light warning that the story should not use overly advanced technology. That is not enough for ordinary contemporary settings.

The fix adds a reusable prompt constraint for realistic modern settings:

- Detect modern/contemporary settings from `character_settings`.
- Detect explicit speculative requests separately from ordinary modern/realistic requests.
- For ordinary modern settings, emit a hard "现实主义世界边界" block.
- The block forbids unrequested cyberpunk, future city, game/IP crossover, and concrete known external-world names from the report.

This remains prompt-level rather than output post-processing because these story generators are already prompt-contract driven and the issue is model drift before generation. Existing tests already gate prompt text and no-mock validators.

## Risks

- Overblocking explicit sci-fi/cyberpunk stories would be a regression. The detector must allow explicit cyberpunk/future settings to keep using those genres.
- The new block must be injected into opening-story, story-only, and round-event prompts, because the report observed drift in new-game opening and continued rounds.
