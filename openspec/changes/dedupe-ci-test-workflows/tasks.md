## 1. Governance Contracts

- [x] 1.1 Add shell behavior tests for quick-gate order and failure propagation
- [x] 1.2 Add workflow ownership, deployment allowlist, E2E ordering, and concurrency tests
- [x] 1.3 Run the new tests and record their expected pre-implementation failures

## 2. Quick Gate

- [x] 2.1 Extract reusable strict TypeScript and preflight Jest helpers
- [x] 2.2 Add `./test.sh quick` with all four required sub-gates and non-zero failure propagation
- [x] 2.3 Run quick locally

## 3. Workflow Governance

- [x] 3.1 Gate PR E2E with quick before Playwright and skip the extra gate on main
- [x] 3.2 Make Frontend Tests the unique complete-suite/coverage owner with Cobertura and HTML artifacts
- [x] 3.3 Delete Frontend Integration Tests and the duplicate frontend coverage job
- [x] 3.4 Synchronize the production deployment required-workflow list
- [x] 3.5 Add PR-only cancellation to every non-deployment workflow

## 4. Verification

- [x] 4.1 Run CI governance tests, shell syntax, and OpenSpec strict validation
- [x] 4.2 Run `./test.sh quick` and frontend coverage locally
- [x] 4.3 Run the complete local `./test.sh all` gate
