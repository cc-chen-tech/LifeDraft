# Fix Generated Music Generic Title

## Why

Production QA showed generated AI music surfaced as `AI MiniMax 叙事`. Current main can also produce `AI MiniMax 日常过渡` after generic scene profile fallback. These titles expose internal music-scene labels instead of useful story context, making generated music look like a broken NetEase recommendation or placeholder result.

## What Changes

- Add one shared generated-music title helper.
- Keep specific scene titles such as `雨夜追逐` or `现代职场危机`.
- When the scene title is generic (`叙事`, `日常过渡`, `通用`, etc.), derive the title from environment plus mood, such as `AI MiniMax 现代医院 紧张`.
- Apply the same title rule to newly generated tracks and reused local AI music library tracks.

## Impact

- Backend display metadata only.
- No change to MiniMax generation, playlist insertion, NetEase recommendation filtering, or audio asset storage.
