## Implementation

- [x] Reproduce browser fallback voice choices not affecting `SpeechSynthesisUtterance.voice`.
- [x] Reproduce backend voice 5xx delaying or preventing audible fallback.
- [x] Add regression tests for browser speech voice selection and immediate fallback.
- [x] Add regression coverage for production `tts_provider=browser` settings skipping backend audio requests.
- [x] Add regression coverage for mid-playback browser voice switching restarting with the newly selected voice.
- [x] Add regression coverage for completed choice-result auto-read while the sound panel is collapsed.
- [x] Implement browser voice matching and voice-reading no-retry fallback policy.
- [x] Implement runtime voice provider settings and strict male voice matching that does not match `female`.
- [x] Run focused frontend tests and OpenSpec validation.
- [x] Run preflight validation.
