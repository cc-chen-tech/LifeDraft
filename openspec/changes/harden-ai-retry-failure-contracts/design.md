# Design

The tests use a small scripted provider fake with the same public `call` surface
as `AIClient`. It records request arguments and returns configured strings or
raises configured exceptions. This exercises real `AIRetryHandler` control flow
without network calls, SDK mocks, sleeps, or timing dependence.
