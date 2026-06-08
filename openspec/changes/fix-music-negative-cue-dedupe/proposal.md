## Why

The 2026-06-08 UX report shows that music recommendations can expose a correct `music_brief.negative_cues` while still returning incompatible NetEase tracks: multiple "小幸运" variants, "断了的弦" covers, and meme/vocal-pop tracks. The current implementation filters exact cue substrings and duplicate ids, but it does not translate generic negative cues such as "情歌", "人声", or "流行人声" into post-search rejection of known vocal-pop/meme titles, and it does not normalize cover/version suffixes for duplicate titles.

## What Changes

- Add hard post-search filtering for reported vocal-pop and meme-title failures when the brief asks for instrumental/no-vocal background music.
- Normalize song titles before de-duplication so cover/version/speed variants count as the same recommendation.
- Apply the same filtering/deduplication when selecting from the verified recommendation pool.
- Add no-mock contract tests wired through the existing `test.sh contract` layer.

## Impact

- Backend music recommendation ranking and pool selection.
- No API schema, database schema, or frontend changes.
