## 1. Tests First

- [x] 1.1 Add a StatusBar test proving modern wealth without explicit currency metadata renders in yuan, not `货币`.
- [x] 1.2 Add StatusBar to the `test.sh` preflight Jest list.
- [x] 1.3 Add API regressions proving generated `starting_wealth` initializes new games and late character settings before play.

## 2. Implementation

- [x] 2.1 Update wealth formatting so explicit `currency` still renders as a prefix.
- [x] 2.2 Update wealth formatting so explicit `currency_name` renders as a suffix.
- [x] 2.3 Use `元` as the modern/default fallback instead of `货币`.
- [x] 2.4 Normalize generated wealth numeric fields (`wealth`, `starting_wealth`, `initial_wealth_amount`) before creating or patching a game.

## 3. Verification

- [x] 3.1 Verify the new StatusBar test fails before implementation.
- [x] 3.2 Run the focused StatusBar Jest test.
- [x] 3.3 Run `./test.sh preflight`.
- [x] 3.4 Run the full required gate before PR.
