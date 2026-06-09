## Context

The application uses a shared Radix-based `DialogContent` wrapper. Existing call sites mostly render `DialogDescription`, but a shared primitive-level fallback prevents runtime warnings if a future or conditional dialog path omits the description node.

## Goals / Non-Goals

**Goals:**
- Eliminate `Missing Description for DialogContent` warnings for dialogs opened without an explicit `DialogDescription`.
- Preserve existing dialog titles, descriptions, layout, and close controls.
- Keep the fix centralized in the shared primitive.

**Non-Goals:**
- Redesign dialog layouts.
- Add visible instructional text.
- Replace Radix dialog primitives.

## Decisions

- Add a screen-reader-only fallback `DialogPrimitive.Description` inside `DialogContent`.
- Use a generated id and `aria-describedby` default so Radix can associate content with a description before warning.
- Allow callers to override `aria-describedby` when they need a more specific relationship.

## Risks / Trade-offs

- A generic fallback is less specific than each dialog's visible description. Mitigation: existing explicit `DialogDescription` nodes stay in place, and the fallback is only a primitive-level warning guard.
