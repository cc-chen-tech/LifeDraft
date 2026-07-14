## Context

`StoryService.generate_fallback_continuation` supplies the visible result when the AI continuation path fails. Its output depends only on the selected option, supplied effects, and configured language.

## Goals / Non-Goals

**Goals:** gate deterministic choice and effect rendering for both supported fallback languages.

**Non-Goals:** change production fallback behavior or invoke AI generation.

## Decisions

- Construct `StoryService` with a concrete unused object because the fallback method never calls the generator.
- Assert semantic fragments instead of treating the complete prose as a snapshot.

## Risks / Trade-offs

- [Workflow drift] -> validate ordered workflow parity and the full maintained gate.
