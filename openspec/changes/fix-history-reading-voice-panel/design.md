## Context

The gameplay page renders story text, story voice controls, scene images, chat/regeneration controls, and the history drawer in one vertical flow. Selecting a historical round swaps the displayed text, but the surrounding current-round components still compete for space and the drawer lifecycle can drop the user back into the latest story before the historical text has been read comfortably.

The current story voice component was built to exercise the future reading pipeline. In production it exposes internal fields such as source, job id, audio URL, playback mode, and debug-like controls even when provider-backed TTS is unavailable, so the UI looks broken rather than intentionally disabled.

## Goals / Non-Goals

**Goals:**
- Make selected historical text readable in a stable surface that is not covered by side drawers, image panels, or current-round action controls.
- Keep history mode read-only and pinned until explicit return.
- Replace the normal story voice UI with a compact, polished preview/unavailable panel while keeping test controls available only when explicitly requested.
- Add regression tests before production changes.

**Non-Goals:**
- Add or integrate a new TTS provider.
- Change backend voice-reading contracts or stored story history shape.
- Redesign the whole gameplay layout or collection/music systems.

## Decisions

- Use a dedicated history reading card on the gameplay page instead of trying to make every current-round component history-aware. This narrows the fix to the presentation layer and avoids mutating game state while reading old rounds.
- Keep historical scene image actions behind the history card, below the story text. Images remain available, but they cannot cover the text or become the primary reading surface.
- Make `StoryVoiceControls` default to a preview panel with one disabled-looking primary action and clear availability copy. Existing state details stay accessible only through `showTestControls` so tests can still exercise the store without leaking internals into production.
- Keep browser speech fallback behavior in the store for now. The UX change is presentation-focused because the user-facing problem is that an unavailable feature is being advertised as working.

## Risks / Trade-offs

- Existing tests may assert debug fields are visible by default. Mitigation: update tests to assert the production UI and keep debug field coverage under `showTestControls`.
- Historical images are pushed below text, so users may scroll more to inspect old images. Mitigation: text readability is the priority for history review; image controls remain available.
- Browser speech remains callable through store tests or explicit controls later. Mitigation: this change does not remove the underlying API path, only prevents misleading production presentation.
