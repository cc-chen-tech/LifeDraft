## Context

Style matching is additive keyword scoring across era, world, traits, and culture. Cyberpunk includes generic terms such as artificial intelligence, enterprise, and networks, so a contemporary product-manager story can cross the assignment threshold despite explicit requests for realism and no supernatural elements.

## Goals / Non-Goals

**Goals:**
- Make explicit world-boundary language authoritative over incidental keyword scores.
- Persist and display one consistent resolved style.
- Keep explicit user style choices authoritative.

**Non-Goals:**
- Creating a new style manifest.
- Rewriting existing stories or saves.
- Disabling cyberpunk matching for genuinely futuristic settings.

## Decisions

1. Detect explicit realistic constraints from all nested setting text before additive scoring. Positive markers must coexist with no fantasy/supernatural or explicit real-world language, while explicit cyberpunk declarations take precedence.
2. Resolve authoritative realism to `nonfiction_novel`, the existing contemporary style whose contract emphasizes facts and real events.
3. Return a confidence above the initializer threshold and include the override in `all_scores`, so persistence follows the existing path without a second style-selection mechanism.
4. Do not invoke auto-match when `narrative_style_id` is supplied; the initializer already enforces this and receives regression coverage.

## Risks / Trade-offs

- [Negated words are misread as positive genre intent] -> Check explicit cyberpunk intent before realism only when cyberpunk is not itself negated.
- [Realism override is too broad] -> Require explicit boundary phrases rather than treating every modern year as realism.
- [Existing saves retain old style] -> Apply only during new-game initialization; users can still change existing saves manually.
