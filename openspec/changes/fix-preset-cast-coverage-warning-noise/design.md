## Context

`QuickValidator._check_key_people_cast_drift` currently uses the number of
canonical preset people present in a story to calculate an 80% threshold. That
ratio is applied even when the round is a focused scene, and its warning is
counted by story generation as a soft warning that can cause another model
attempt. Production replay showed repeated 4/7 and 5/7 warnings with no hard
issues, so the aggregate ratio is not a reliable per-round failure signal.

## Goals / Non-Goals

**Goals:**

- Make ordinary focused rounds with partial preset-cast coverage pass without a
  coverage warning or retry.
- Keep explicit participant requirements and high-confidence cast replacement
  protection intact.
- Keep prompt and validator behavior aligned without adding semantic scene
  classification.
- Preserve compatibility with historical validation messages.

**Non-Goals:**

- No new LLM call or scene classifier.
- No configurable threshold in this first fix; the aggregate ratio is removed
  from the per-round gate rather than moved into configuration.
- No database, API, frontend, deployment, or feature-flag changes.

## Decisions

### Aggregate coverage is diagnostic, not a finding

The validator may continue to derive the present preset names for takeover
checks, but aggregate coverage must not create a `QuickValidationResult` warning
or issue. This removes the retry side effect without changing the public
validator signature or introducing a new result schema.

### Explicit scope remains authoritative

The existing `required_people` input remains the only exact per-round cast
requirement. When the caller supplies it, each missing required person remains a
hard issue. This uses already-available event scope instead of guessing scene
type from prose.

### Takeover checks remain hard and high-confidence

Role-transfer and main-plot-driving checks remain hard failures. Mere presence
of an unapproved token is not enough; tests cover object/place/organization
noise so those tokens cannot cause a takeover failure.

### Remove the global 80% prompt rule

The shared authority block will retain canonical identity and no-substitution
constraints but will no longer tell every prompt that a multi-person scene must
use 80% of the network. Explicit event participant constraints remain supplied
through existing prompt/validator paths.

## Risks / Trade-offs

- [A round may use fewer preset people than before] -> explicit required-cast
  checks and high-confidence role-takeover checks remain blocking safeguards.
- [Historical dashboards may see fewer new `CAST_COVERAGE_LOW` findings] ->
  retain legacy message parsing and monitor retry counts plus hard takeover
  findings separately.
- [Prompt quality may change for broad relationship scenes] -> keep canonical
  identity/no-substitution instructions and add regression coverage for those
  prompt contracts.

## Migration Plan

Deploy as a normal backend code change. Roll back by reverting the PR; no data
migration or flag transition is required.

## Open Questions

None for this change. A future product decision may add an explicit scene scope
or observational coverage metric, but neither is required for this fix.
