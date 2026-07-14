## Context

Entity recognition must use relationship metadata without promoting text fragments to characters, while an empty whitelist must still retain clear named story people. Opening prompts must preserve the selected life vision and key people. The existing test file drives the real domain services and uses only a handwritten response object for the explicit AI boundary.

## Goals / Non-Goals

**Goals:**

- Promote the deterministic regression contracts in both maintained workflows.
- Preserve the ordered parity of the maintained workflow selections.
- Run the complete maintained suite and consider a new threshold only when its exact coverage result supports it.

**Non-Goals:**

- Change recognition, prompt, music, or collection production behavior.
- Call an external AI or music provider.
- Introduce framework mocks, skip directives, or environment mutation.

## Decisions

- Promote the existing file as one coherent live-regression unit because each assertion derives from the same recovered gameplay and collection context.
- Accept the small handwritten AI-client and HTTP response fakes because they isolate unavoidable external boundaries while exercising real domain code.
- Append the file to both workflow lists to keep all existing ordering stable.

## Risks / Trade-offs

- [A future AI client interface change can break the fake] -> The fake is minimal and exposes only the documented `call` surface used by the service.
- [The file covers several modules] -> Treat it as a domain regression suite, while retaining focused unit contracts for each module.
