## Why

Main story generation, round generation, scheduled events, and normal choice continuations already inject preset-cast authority constraints and run quick consistency validation. The custom-choice JSON result path did not. It only serialized `character_settings` into the prompt and returned the first parsed JSON result.

That left a route for the P0 persona drift bug to re-enter gameplay: after a user typed a custom action, the model could put a new named person into the mentor/friend/peer role and the backend would accept the `story_continuation` without validating it against preset key people.

## What Changes

- Add preset key-person and realistic world-boundary constraints to the custom-choice result system prompt.
- Validate `story_continuation` from `generate_custom_choice_result()` with the same quick validator used by other story paths.
- Retry once when the generated JSON story violates required cast or world-boundary constraints.

## Impact

- Affected prompt: `get_custom_choice_result_prompt`.
- Affected service: `StoryService.generate_custom_choice_result`.
- No change to normal choice continuations, option generation, or resource-effect normalization.
