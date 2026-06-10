## Why

The music recommendation service already filters repeated vocal-pop title families and Anime/ACG opening metadata, but the `/api/music/recommend` router trusted whatever the service object returned. If a stale cache, mocked service path, or future service change passed dirty songs through, the API could still return titles such as `绅士`, `红尘客栈`, or Anime OP results to the frontend after URL lookup.

That keeps the reported production failure possible at the final response boundary and wastes URL lookup time on songs that contradict the `music_brief`.

## What Changes

- Add an API-level safety net for `/api/music/recommend` that applies `MusicResultRanker.filter_and_dedupe()` to the recommendation songs before playback URL lookup.
- Use the returned `music_brief` when present, including dict-shaped briefs for compatibility.
- Keep the existing empty fallback behavior and response schema unchanged.

## Impact

- Affected API: `POST /api/music/recommend`.
- Affected tests: router-level music recommendation contracts.
- No change to MiniMax generated music, playlist insertion, or the core NetEase search algorithm.
