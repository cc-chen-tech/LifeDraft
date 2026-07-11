## Context

Recognition currently applies a strict metadata allowlist after the AI response and again during deterministic supplementation. A newly introduced person can therefore be omitted until another subsystem records relationship metadata. Fallback descriptions use a fixed character window, which can begin and end inside a sentence. The frontend add action awaits both the durable POST and a potentially expensive details GET while sharing the initial-load flag.

The change crosses backend extraction, persistence contracts, and frontend interaction state. New tests must use real implementations and databases, contain no skip or mock constructs, be written before production code, and be registered in `test.sh`.

## Goals / Non-Goals

**Goals:**

- Preserve metadata gating for ambiguous phrases while admitting prose names supported by clear person syntax.
- Produce bounded, sentence-complete context containing the entity name.
- Make successful add feedback depend on the durable write, not on collection-detail hydration.
- Preserve eventual refresh, existing visible data, and real DB save-read behavior.

**Non-Goals:**

- Replace the AI recognition provider or add a new NLP dependency.
- Generate images/descriptions during entity add.
- Change collection endpoint paths or remove existing response fields.

## Decisions

1. Use deterministic person syntax as a second source of eligibility. AI-only characters remain metadata-gated; a name detected by the existing conservative person parser can pass even before relationship metadata is updated. This avoids accepting arbitrary AI names while fixing the prose-only omission.
2. Select context using Chinese/English sentence delimiters around the first mention, normalize whitespace, and only apply a bounded fallback when a single sentence is unusually long. The bound expands around the entity and adds ellipses only at deliberate boundaries.
3. Treat the add POST response as the completion boundary. The store clears the add loading state and recognition dialog after that response, then starts a background details refresh. A refresh failure remains reportable without changing the already successful add result.
4. Verify the write using the real collection route and database, and verify the user interaction in Playwright against the deterministic E2E backend. No request interception is used by the new tests.

## Risks / Trade-offs

- [Deterministic name patterns can still misclassify prose] -> Keep existing false-positive checks, require clear person syntax, and retain normalization/existing-entity filters.
- [Background refresh can finish after the dialog closes] -> Keep `isRefreshing` distinct from add loading and preserve visible collection data until refreshed data arrives.
- [Long sentences can exceed summary limits] -> Use a name-centered bounded excerpt with explicit ellipses instead of an unexplained mid-sentence fragment.
