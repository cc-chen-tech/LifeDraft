## 1. Tests First

- [x] 1.1 Add contract tests for MiniMax text-to-image request URL, auth, payload, and response parsing.
- [x] 1.2 Add contract tests for MiniMax image-to-image `subject_reference`, payload fields, and response parsing.
- [x] 1.3 Add error contract tests for non-zero `base_resp` and content safety code `1026`.
- [x] 1.4 Run the new targeted tests before implementation and confirm they fail against the DashScope adapter.

## 2. Provider Switch

- [x] 2.1 Update image provider defaults to MiniMax endpoint and `image-01` model lists.
- [x] 2.2 Replace DashScope T2I request building with MiniMax `/v1/image_generation` request building.
- [x] 2.3 Replace DashScope I2I request building with MiniMax `subject_reference` request building.
- [x] 2.4 Update response parsing to support `data.image_urls` and `data.image_base64`.
- [x] 2.5 Preserve existing `ImageClient` public method signatures and caller behavior.

## 3. Verification

- [x] 3.1 Run targeted image contract tests.
- [x] 3.2 Run image import tests.
- [x] 3.3 Run mypy/static gate for touched backend code.
- [x] 3.4 Run relevant `./test.sh` layers before marking complete.
