## Why

Production QA found a realistic, no-supernatural character setup displayed as `赛博朋克`. The automatic matcher counts generic modern technology words as positive cyberpunk evidence but ignores explicit realism and exclusion language, causing the displayed setting and generation constraints to diverge.

## What Changes

- Treat explicit realism, real-world, and no-supernatural statements as authoritative style constraints.
- Prevent incidental AI, network, or enterprise terms from selecting cyberpunk when realism exclusions are present.
- Map explicitly realistic contemporary setups to the existing `nonfiction_novel` style.
- Preserve an explicit user-selected `narrative_style_id`, including cyberpunk.
- Add no-mock matcher, initializer, DB round-trip, and browser display coverage through `test.sh`.

## Capabilities

### New Capabilities
- `realistic-style-alignment`: Defines authoritative style selection and display for explicitly realistic character settings.

### Modified Capabilities

## Impact

- Narrative style matcher and game initializer style persistence.
- Narrative style API/display values.
- Python contracts, real DB integration, and Playwright style-selection coverage.
