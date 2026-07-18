# Design

The tests use the real Zustand game store and `useChoiceHandler`. Network input is
represented by the repository's readable-stream SSE response fixture, so parsing,
callback sequencing, and hook state handling execute together without a server.
