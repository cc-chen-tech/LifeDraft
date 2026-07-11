## Context

The summary endpoint concatenates round history, injects current resource metrics, asks for a literary summary, and returns provider text directly. The prompt does not define temporal scale, source authority, contradiction handling, or legal-claim boundaries.

## Goals / Non-Goals

**Goals:**
- Keep summaries within the exact selected week range.
- Prevent unsupported certainty, legal endorsement, and resource metrics.
- Guarantee a readable evidence-based result when provider output is unsafe.

**Non-Goals:**
- Determining which side of a contradictory story claim is objectively true.
- Providing legal advice.
- Reconstructing or correcting old story rounds.

## Decisions

1. Move prompt construction and output checks into a strictly typed production module.
2. Derive a literal `第N-M周` label from the selected history; do not use vague month/year metaphors for short ranges.
3. Do not include energy, mood, knowledge, or wealth in the provider prompt or deterministic fallback.
4. Tell the provider to report source conflicts as unresolved and never call circumvention of legal or contractual duties compliant.
5. Validate provider output for mismatched long-duration language, resource metrics, unsupported numeric claims, and legal endorsement. Unsafe output is replaced by a deterministic summary assembled from bounded source excerpts.
6. Preserve the API response field names and frontend panel contract.

## Risks / Trade-offs

- [A safe literary summary is rejected] -> Prefer a grounded excerpt summary over confident misinformation.
- [A nonnumeric invented claim passes] -> Prompt constraints reduce this risk; deterministic checks cover the observed high-impact failure classes.
- [Fallback prose is less polished] -> Keep it concise, chronological, and explicit about unresolved conflicts.
