# Unify Sound Controls UI

## Why

Music playback and story narration are both sound features, but production UI had them presented as stacked controls with separate visual hierarchy. Users could read this as two unrelated areas and the narration row exposed too many standalone buttons.

## What Changes

- Present the global sound UI through one "声音" entry point.
- Make the expanded content a single "音乐和朗读" group instead of another nested sound region.
- Remove redundant "声音控制" / "声音面板" naming so the mini bar remains the single sound entry point.
- Make music and narration peer channel rows inside that surface, separated by lightweight dividers instead of nested cards.
- Use concise embedded channel labels: "音乐" and "朗读".
- Render embedded story narration controls as a compact channel inside the expanded sound panel instead of a standalone bordered card or toolbar.
- Keep the collapsed sound bar simple: one primary sound control and one expand/collapse control. Manual narration controls live in the expanded panel.
- Keep existing music playback, auto-read, voice selection, and provider-backed TTS behavior unchanged.

## Impact

- Frontend UI only: `GlobalMusicPlayer`, `StoryVoiceControls`, and component tests.
- No backend API or generated OpenAPI type change.
