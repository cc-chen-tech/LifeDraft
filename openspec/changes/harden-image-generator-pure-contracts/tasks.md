## 1. Provider-Free Contract Coverage

- [x] 1.1 Add deterministic tests for MiniMax URL, response format, prompt, size, and payload normalization.
- [x] 1.2 Add deterministic tests for image-source parsing, base64 decoding, and typed provider error classification.
- [x] 1.3 Verify the new test file has no mock, skip, xfail, network, or environment-mutation mechanism.

## 2. Maintain Gate Selection

- [x] 2.1 Add the new image-generator contract suite to the maintained coverage workflow.
- [x] 2.2 Add the same suite in the same position to the maintained backend test workflow.

## 3. Verify and Record

- [x] 3.1 Run the focused new test suite with direct image-generator coverage.
- [x] 3.2 Verify workflow path-list parity and strict OpenSpec validity.
- [x] 3.3 Run the expanded maintained coverage suite and raise the floor only when measurement supports it.
