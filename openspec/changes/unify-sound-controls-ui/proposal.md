# Unify Sound Controls UI

## Why

Music playback and story narration are both sound features, but production UI had them presented as stacked controls with separate visual hierarchy. Users could read this as two unrelated areas and the narration row exposed too many standalone buttons.

## What Changes

- Present the global sound UI through one "声音" entry point.
- Make the expanded content a single "音乐和朗读" group instead of another nested sound region.
- Remove redundant "声音控制" / "声音面板" naming so the mini bar remains the single sound entry point.
- Make music and narration compact peer control rows inside one "声音控制台" so they read as one sound console, not two separate modules.
- Use explicit channel labels: "背景音乐" and "故事朗读".
- Do not expose "背景音乐" and "故事朗读" as separate section groups; they are row labels inside the shared console.
- Replace the collapsed mini bar with an expanded panel header while the panel is open, with "收起声音" as the single collapse action.
- Render embedded music and story narration controls as compact channels inside the expanded sound panel instead of standalone bordered cards, recommendation panels, or toolbars.
- Keep the collapsed sound bar as a single sound-panel entry point. Music play/pause, manual narration, voice selection, and auto-read controls live in the expanded panel.
- Keep existing music playback, auto-read, voice selection, and provider-backed TTS behavior unchanged.

## Impact

- Frontend UI only: `GlobalMusicPlayer`, `StoryVoiceControls`, and component tests.
- No backend API or generated OpenAPI type change.
