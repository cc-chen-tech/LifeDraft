# Design

The tests use the real Zustand store, mocked browser speech APIs, and the existing
fetch boundary used by `api.voice_reading`. They deliberately avoid mocking store
actions so that attempt ordering, shared settings loading, and completion state are
observed at the public store boundary.

The concurrency scenario holds the settings response until two distinct attempts
are pending. It then verifies that only the latest attempt starts speech. The chunk
scenario captures utterances and completes them in sequence, proving that a long
text reaches the terminal idle state only after every chunk.
