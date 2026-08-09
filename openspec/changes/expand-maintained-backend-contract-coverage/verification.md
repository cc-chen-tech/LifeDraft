## Candidate Stability

The four new suites ran twice in the maintained environment before promotion:

- `tests/test_event_fallback_context_contracts.py`
- `tests/test_gameplay_event_protocol_contracts.py`
- `tests/test_extraction_parser_contracts.py`
- `tests/test_local_music_library_helper_contracts.py`

Each focused run passed all 20 tests without skips, xfails, provider calls,
network calls, or background timing dependencies.

## Expanded Maintained Measurement

After promotion, the maintained selection contains 23 test files and passed
twice with 278 tests and 3 existing SQLAlchemy warnings:

- 8,146 / 23,293 covered statements (34.97%)
- 8,146 / 23,293 covered statements (34.97%)

The new `--cov-fail-under=34` workflow floor also passed twice at 34.97%.

| Module | Before batch | Current |
| --- | ---: | ---: |
| `src/game/round/event_generator.py` | 11.20% | 23.16% |
| `src/api/routers/gameplay/events.py` | 26.40% | 48.80% |
| `src/services/item_extraction_service.py` | 17.86% | 51.79% |
| `src/services/landmark_extraction_service.py` | 16.67% | 55.00% |
| `src/services/local_ai_music_library.py` | 23.36% | 48.13% |

35% requires 8,153 covered statements, so the current selection remains seven
statements short of a stable 35% floor. 70% requires 16,306 covered
statements; the remaining gap is 8,160 statements. The next batch should
target large, high-risk local paths such as `sse_helpers` durable operations,
`scene_service`, and gameplay state transitions.
