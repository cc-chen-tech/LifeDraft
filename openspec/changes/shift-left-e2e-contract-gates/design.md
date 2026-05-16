## Design

The fastest reliable source of API truth is FastAPI's in-process route table. The route-table contract test compares method/path templates directly, avoiding network startup, browser launch, cookies, and external services.

The browser API-contract suite can continue to smoke-test real server availability, but missing endpoints and accidental deprecated endpoint resurrection should fail in the contract layer first.

## Test Placement

- `preflight`: validates this OpenSpec change and checks that route-drift coverage is wired before E2E.
- `contract`: runs the route-table contract test alongside existing producer/consumer contract tests.

## Non-Goals

- Do not remove Playwright coverage in this change.
- Do not change production routes.
- Do not replace user-flow E2E tests that verify real UI behavior.
