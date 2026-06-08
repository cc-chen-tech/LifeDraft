# Image metadata endpoints required image API key

Date: 2026-06-07

## Problem

The E2E API contract check failed for:

- `GET /api/images/999999`
- `DELETE /api/images/999999`

Both endpoints returned `500` when the image provider API key was not configured. They should return a normal resource-level status such as `404` for a missing image.

## Root Cause

The metadata endpoints only need to look up or soft-delete a database row, but they constructed `ImageService(db)` at request start. `ImageService` eagerly constructed `ImageClient`, which eagerly constructed `ImageGenerator`. `ImageGenerator.__init__` raised when `IMAGE_API_KEY` or `OPENAI_API_KEY` was missing, so read-only metadata endpoints became dependent on image generation provider credentials.

## Test Added

Added `TestImageMetadataEndpointsWithoutProviderConfig` in `tests/test_images_router.py`.

The tests monkeypatch `Settings.IMAGE_API_KEY` and `Settings.OPENAI_API_KEY` to `None`, call the real image router without mocking `ImageService`, and assert missing images return `404` for both GET and DELETE.

## Fix

`ImageGenerator` now permits construction without provider credentials and validates provider configuration only when `_call_api` or `_call_edit_api` is invoked for an actual generation request.

This preserves failure behavior for real image generation while keeping metadata reads and deletes independent from provider configuration.

## Verification

```bash
python -m pytest tests/test_images_router.py::TestImageMetadataEndpointsWithoutProviderConfig -q
```

Result: 2 passed.
