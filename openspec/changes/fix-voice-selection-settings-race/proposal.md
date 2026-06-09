## Why

Story voice settings load asynchronously when the sound panel mounts. If the user
changes the selected voice before that request finishes, the late settings response
can overwrite the local selection with a stale server value. The next reading
request then uses the wrong voice, making voice switching appear delayed or
unreliable.

## What Changes

- Track whether the user has changed the voice locally during the component
  lifetime.
- Do not apply a late `selected_voice_color` settings response after a local
  voice change.
- Preserve the existing behavior that a mid-playback voice change immediately
  restarts/regenerates the active reading.
- Add regression coverage for the settings-load race.

## Impact

- Frontend story voice controls only.
- No backend API, schema, or persistence migration is required.
