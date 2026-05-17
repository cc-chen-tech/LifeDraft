## 1. Failure Inventory

- [x] 1.1 Re-run the last-failed backend suite and confirm current failure groups
- [x] 1.2 Pick a coherent first repair group with low implementation risk

## 2. Chinese Text Normalization

- [x] 2.1 Restore the StoryGenerator punctuation normalization compatibility entry point
- [x] 2.2 Ensure the current text-quality helper satisfies the legacy Chinese punctuation contract
- [x] 2.3 Run the targeted Chinese text normalization contract

## 3. Remaining Groups

- [x] 3.1 Re-run last-failed after the first repair group
- [x] 3.2 Update triage with remaining failure counts
- [x] 3.3 Select the next coherent group for a follow-up repair

## 4. Era Validation and Music Era Search

- [x] 4.1 Restore the StoryGenerator validation-context compatibility entry point
- [x] 4.2 Ensure ancient era settings produce prioritized music search keywords
- [x] 4.3 Run targeted era and music-era contract tests

## 5. Legacy Backend Restoration

- [x] 5.1 Restore low-risk StoryGenerator compatibility entry points used by prompt-security, narrative, retry, and best-story fallback contracts
- [x] 5.2 Restore music router serialization and Netease client URL-cache/health/default-URL contracts without regressing 503 fast degradation
- [x] 5.3 Restore scene image SSE event cache/publish/endpoint behavior
- [x] 5.4 Restore frontend SSE streaming retry and disconnect-error contracts
- [x] 5.5 Reconcile stale feature-flag and security-test expectations with current product behavior

## 6. Verification

- [x] 6.1 Validate the OpenSpec change strictly
- [x] 6.2 Run maintained preflight if repaired tests are promoted into maintained gates
- [x] 6.3 Run full backend suite and confirm legacy backend failures are cleared
