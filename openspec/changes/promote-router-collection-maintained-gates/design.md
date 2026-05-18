## Context

`tests/test_images_router.py` and `tests/test_api_collection.py` were previously left out of the maintained backend gate because an earlier candidate promotion exposed router mock/session ordering fragility. The latest targeted run passes both files together:

```bash
python -m pytest tests/test_images_router.py tests/test_api_collection.py -q
```

Result: `40 passed`.

## Decision

Promote both files as a narrow legacy-to-maintained batch:

- Add both tests to `test.sh contract` because they verify API/router behavior rather than only database persistence.
- Add both tests to `test.sh coverage-maintained-backend` and the matching CI coverage workflow.
- Add both tests to `.github/workflows/backend-tests.yml` maintained backend gates.
- Update gate-fidelity checks so these files cannot silently drop from maintained CI.
- Update the legacy failure inventory from "follow-up not promoted" to "promoted after targeted stabilization".

## Risks

- These suites still use router/session mocks, so they are less strong than no-mock DB tests. They are still useful maintained contracts because they cover HTTP-level serialization, routing, permission checks, and collection payload behavior.
- If future ordering fragility returns, the failure should block maintained gates instead of living as undocumented full-suite debt.

## Out of Scope

- Raising the maintained backend coverage threshold above 30 in this change.
- Rewriting these suites into full no-mock integration tests.
- Changing image router or collection API production behavior.
