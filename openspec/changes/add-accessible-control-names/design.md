## Context

Several icon-only controls currently rely on an SVG or generic English dialog close text, while history entries expose only fragmented visible text. The production interaction snapshot therefore cannot identify credential copy, public-ID copy, save deletion, character-detail navigation, or history-reading actions consistently.

## Goals / Non-Goals

**Goals:**
- Expose concise Chinese accessible names for every reported control.
- Include the affected entity or round in repeated-control names.
- Keep names stable enough for role/name browser tests.
- Reflect copy success without removing the control's purpose.

**Non-Goals:**
- Redesigning the affected pages or dialogs.
- Changing action behavior, authorization, or persistence.
- Adding a new accessibility dependency.

## Decisions

1. Use native `aria-label` on icon-only buttons. This keeps visible layout unchanged and is understood by React Testing Library, Playwright, and assistive technology.
2. Add a `closeButtonLabel` option to the shared dialog content primitive. The default remains `Close` for compatibility, while character detail supplies a contextual Chinese label.
3. Name repeated controls with user-visible identity. Save deletion includes the player name and history entries include one-based week plus the round label.
4. Add focused Jest tests plus a no-mock Playwright contract that renders the real application pages/components through existing test setup. Register the browser spec in `test.sh` so it cannot drift outside the project gate.

## Risks / Trade-offs

- [Names can become stale when visible labels change] -> Derive names from the same runtime values displayed in the control.
- [Shared dialog API can affect unrelated dialogs] -> Keep the existing default and opt in only from character detail.
- [Duplicate player names can still produce duplicate delete names] -> Include the save game ID as an additional stable suffix available to assistive users.
