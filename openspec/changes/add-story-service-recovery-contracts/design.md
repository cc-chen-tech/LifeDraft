## Context

The maintained suite already validates StoryService fallback prose, but provider delegation and custom-choice failure handling remain primarily in legacy mock-based tests. The maintained backend gate requires deterministic, provider-free tests.

## Goals / Non-Goals

**Goals:**
- Exercise StoryService's public compression/world-update delegation contract.
- Exercise custom-choice input sanitization, retry, and fallback contracts with small concrete in-memory providers.
- Add the new tests to both synchronized maintained-backend workflow lists.

**Non-Goals:**
- Change StoryService behavior, prompts, validation rules, or provider configuration.
- Replace legacy tests or introduce live API, database, HTTP, randomness, or browser dependencies.

## Decisions

- Use minimal concrete recording providers instead of mocking libraries. This preserves a real call boundary while keeping retry sequencing explicit and deterministic.
- Assert observable inputs and returned contracts rather than private implementation details. This permits internal refactoring while guarding user-facing fallback and safety semantics.
- Keep the test module narrowly scoped to StoryService and append it to the paired workflow lists in identical order. This maintains the repository's established gate-parity invariant.

## Risks / Trade-offs

- [Prompt wording changes can make assertions brittle] → Assert sanitized content and stable behavioral fragments rather than complete prompt text.
- [Provider-like fakes can diverge from production interfaces] → Limit them to the exact public methods and keyword arguments invoked by StoryService.
- [Coverage can rise without end-to-end confidence] → This change complements, but does not replace, DB/API/E2E validation.
