## Context

`StoryGenerator._build_round_story_fallback` is used after story-provider
recovery fails. The maintained suite checks a player-name authority case but
does not cover contextual grounding or the English branch.

## Goals / Non-Goals

**Goals:**
- Test Chinese fallback grounding from era, trait, and established relationship data.
- Test English fallback grounding and the invalid-round fallback label.
- Keep execution entirely provider-free and deterministic.

**Non-Goals:**
- Change production fallback text, prompt generation, or provider retry behavior.
- Modify existing tests or test external AI APIs.

## Decisions

- Invoke the static fallback builder directly with fixed state dictionaries.
  This tests the recovery output without a provider or mock boundary.
- Assert stable grounding fragments, not full prose, so editorial wording can
  evolve while required information remains protected.
- Register the test in both maintained workflow lists at the story-generator
  contract location.

## Risks / Trade-offs

- [Exact prose assertions can make tests brittle] → Assert locale, contextual
  names, roles, and fallback round labels only.
- [Relationship extraction has its own compatibility behavior] → Use normal
  `relationships.key_people` fixtures that mirror persisted settings.
