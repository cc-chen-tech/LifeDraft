## 1. Explore Existing Coverage

- [x] 1.1 Inventory browser-agent findings already covered by no-mock Playwright and frontend preflight tests
- [x] 1.2 Identify stable gaps suitable for deterministic Jest or backend gate tests

## 2. Codify Browser Findings

- [x] 2.1 Add frontend preflight regressions for restored story text, current-event fallback, and history image identity
- [x] 2.2 Add frontend preflight regressions for rewrite/session recovery and custom-choice input behavior
- [x] 2.3 Add frontend preflight regressions for collection refresh failures preserving visible data
- [x] 2.4 Add frontend preflight regressions for music recommendation degradation and playlist continuity
- [x] 2.5 Add no-mock Playwright assertions for deep browser fixture discoverability where needed

## 3. Gate Wiring

- [x] 3.1 Wire the new OpenSpec change into `./test.sh preflight`
- [x] 3.2 Wire maintained frontend regression files into preflight
- [x] 3.3 Extend gate fidelity tests so omitted browser regression files fail fast
- [x] 3.4 Ensure e2e command keeps the deep Story101 exploration sweep discoverable

## 4. Verification and PR

- [x] 4.1 Run strict OpenSpec validation for the new change
- [x] 4.2 Run targeted RED/GREEN frontend tests while implementing
- [x] 4.3 Run `./test.sh preflight`
- [x] 4.4 Run targeted e2e/no-mock regression checks or document any local blocker
- [x] 4.5 Commit, push, and open a draft pull request
