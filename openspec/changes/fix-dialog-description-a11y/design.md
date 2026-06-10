## Context

The application uses shared Radix-based `DialogContent` and `SheetContent` wrappers. Existing modal call sites mostly render explicit descriptions, but gameplay side panels such as the collection panel are implemented with `SheetContent` and can omit `SheetDescription`, which still triggers Radix's `DialogContent` missing-description warning because Sheet uses Dialog primitives internally.

## Goals / Non-Goals

**Goals:**
- Eliminate `Missing Description for DialogContent` warnings for dialogs opened without an explicit `DialogDescription`.
- Eliminate the same warning for sheets opened without an explicit `SheetDescription`.
- Preserve existing dialog titles, descriptions, layout, and close controls.
- Keep the fix centralized in the shared primitives.

**Non-Goals:**
- Redesign dialog layouts.
- Add visible instructional text.
- Replace Radix dialog primitives.

## Decisions

- Add a screen-reader-only fallback `DialogPrimitive.Description` inside `DialogContent`.
- Add a screen-reader-only fallback `SheetPrimitive.Description` inside `SheetContent`.
- Use a generated id and `aria-describedby` default so Radix can associate content with a description before warning.
- Allow callers to override `aria-describedby` when they need a more specific relationship.

## Risks / Trade-offs

- A generic fallback is less specific than each dialog's visible description. Mitigation: existing explicit `DialogDescription` nodes stay in place, and the fallback is only a primitive-level warning guard.
