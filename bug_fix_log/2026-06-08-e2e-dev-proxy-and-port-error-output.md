# E2E dev proxy and port error output

Date: 2026-06-08

## Problem

Code review found two E2E runtime risks after the dynamic-port fixes:

- `E2E_FRONTEND_MODE=dev` still let Playwright start the frontend without exporting the dynamic backend proxy target, so browser `/api/*` requests could fall back to `http://localhost:8000`.
- `find_free_port` printed allocation errors to stdout while callers captured stdout into `E2E_BACKEND_PORT` / `E2E_FRONTEND_PORT`, so an error string could become the port value.

## Reproduction

Added preflight regressions in `tests/test_gate_preflight_no_mock.py`:

- `test_e2e_dev_frontend_proxy_targets_dynamic_backend_port`
- `test_find_free_port_errors_do_not_pollute_captured_port_value`

Both tests failed before the fix.

## Fix

- `test.sh` now defines one `backend_url` for both prod and dev E2E frontend modes.
- Dev mode exports `BACKEND_URL` and `NEXT_PUBLIC_API_URL=/api` before Playwright starts its web server.
- `find_free_port` sends allocation errors to stderr so command substitution only captures valid port numbers.

## Verification

Targeted regression:

```bash
python -m pytest tests/test_gate_preflight_no_mock.py -k 'dev_frontend_proxy_targets_dynamic_backend_port or find_free_port_errors_do_not_pollute_captured_port_value' -q
```

Result: passed.

Broader gates:

```bash
python -m pytest tests/test_gate_preflight_no_mock.py -q
./test.sh preflight
./test.sh e2e
```

Result: passed.
