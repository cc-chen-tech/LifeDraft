## Context

The character creator combines provider-backed generation with deterministic
normalization. The maintained gate must cover the latter without invoking an
AI provider or copying mock-heavy legacy tests.

## Goals / Non-Goals

**Goals:**
- Cover pure modern/classical era alignment, placeholder family names, and
  rule-based initial attribute bounds with fixed inputs.
- Use `CharacterCreator.__new__` only for the helper that has no initialized
  dependency requirements.

**Non-Goals:**
- Invoke generation APIs, test retries, random orientation selection, or alter
  character-creation behavior.

## Decisions

- Assert normalized public dictionaries, not prompt text or private logs.
- Cover both modern and explicitly classical life visions, since their conflict
  rules intentionally point in opposite directions.
- Measure twice before any coverage-floor adjustment.

## Risks / Trade-offs

- [Rules change as product design evolves] -> Keep assertions on declared
  normalization outputs and review them with rule changes.
- [Constructor gains required side effects] -> Continue using only the unbound
  rule helper; no provider is created.
