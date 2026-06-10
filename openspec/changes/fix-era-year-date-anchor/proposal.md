## Why

Production QA found modern 2026 gameplay summaries and history labels rendering
as `2024年1月...`. The story followed the requested 2026 AI startup setting, but
the gameplay date helper only read `character_settings.era.year` and fell back to
2024 when older or generated settings stored the year only inside
`era_name`, `era_description`, or `world_context`.

## What Changes

- Recover the gameplay start year from text-only era fields when `era.year` is
  missing or serialized as a string.
- Keep the existing 2024 fallback only when no explicit year is present anywhere
  in the era setting.
- Add a regression proving a 2026 era text does not summarize as 2024.

## Impact

- Backend gameplay time/date labels derived from `PlayerState.get_game_date_info`.
- Existing saves with text-only era settings now display the intended year when
  the year appears in saved era text.
