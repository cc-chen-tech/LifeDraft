# Unify Sound Controls UI

## Why

Music playback and story narration are both sound features, but production UI had them presented as stacked controls with separate visual hierarchy. Users could read this as two unrelated areas and the narration row exposed too many standalone buttons.

## What Changes

- Present the expanded global sound panel as one unified surface.
- Make music and narration peer channels inside that surface, separated by lightweight dividers instead of nested cards.
- Render embedded story narration controls as a compact row inside the expanded sound panel instead of a standalone bordered card.
- Keep the collapsed sound bar simple: one primary sound control and one expand/collapse control. Manual narration controls live in the expanded panel.
- Keep existing music playback, auto-read, voice selection, and provider-backed TTS behavior unchanged.

## Impact

- Frontend UI only: `GlobalMusicPlayer`, `StoryVoiceControls`, and component tests.
- No backend API or generated OpenAPI type change.
