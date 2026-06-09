## Context

`ChatBar` exposes quick actions in both collapsed and expanded states. The expanded state labels the full story regeneration action as "重新生成", while the collapsed state currently labels the same callback as "重写". The collapsed state also has a separate "改写" button that opens the rewrite sheet, so the regenerate button label creates avoidable ambiguity.

## Goals / Non-Goals

**Goals:**
- Make the collapsed regenerate action use the same visible wording as the expanded regenerate action.
- Keep "改写" reserved for the rewrite sheet entry point.
- Preserve existing callbacks and backend routes.

**Non-Goals:**
- Redesign ChatBar layout.
- Change rewrite or regenerate generation semantics.
- Rename backend APIs.

## Decisions

- Update only the collapsed regenerate button label from "重写" to "重新生成".
- Keep the `RotateCcw` icon and existing title because they already communicate regeneration.
- Cover the behavior in the existing ChatBar component test file, which is already part of `test.sh` preflight.

## Risks / Trade-offs

- Longer button text can be slightly wider in the collapsed quick-action row. Mitigation: this row already wraps and uses compact text styling; the expanded state already uses the same label.
