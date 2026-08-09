## Why

Image generation commonly falls back before any provider request is made. Era sanitization and deterministic scene/appearance fallbacks must retain story identity while stripping visual cues that cause character drift or unsafe futuristic imagery.

## What Changes

- Add no-provider contracts for era sanitization, default composition, story truncation, and fallback appearance-anchor variants.
- Register the contract module in both maintained backend workflows.

## Capabilities

### New Capabilities
- `image-prompt-fallback-contracts`: Deterministic image prompt and appearance fallback contracts.

### Modified Capabilities

- None.

## Impact

- Adds one maintained test module for `src/ai/image_prompt_builder.py`.
