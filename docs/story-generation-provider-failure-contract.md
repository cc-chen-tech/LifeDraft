# Story Generation Provider Failure Contract

When round-event generation cannot produce any valid story text, the backend
must surface a typed generation failure. It must not persist a templated
fallback story or mark the operation as successful.

If a generation attempt produced a valid story before a later option or
validation failure, that validated story may be retained with contextual
fallback options. This is the only non-provider fallback permitted by this
path.

When story rewrite fails, the API returns HTTP 503 and preserves the current
event text unchanged. A successful rewrite response always represents newly
generated persisted text.
