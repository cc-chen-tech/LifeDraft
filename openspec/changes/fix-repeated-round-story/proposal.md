# Reject repeated round stories

## Why

A provider response can satisfy local formatting and cast checks while repeating an earlier
round almost verbatim. Prompt-only anti-repetition guidance cannot prevent the nine-round
template replay observed in production.

## What Changes

- Compare candidate round prose with committed recent round prose deterministically.
- Request one focused retry when output is materially duplicated.
- Refuse to persist a repeated candidate if the retry remains duplicated.

## Impact

- Affected code: `src/ai/story_generator.py` and focused generation tests.
- No schema change; committed history remains unchanged on rejection.
