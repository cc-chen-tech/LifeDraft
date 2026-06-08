# Collection Panel Ambiguous Character Locator - 2026-06-08

## Problem

`frontend/e2e/collection-panel-cache.spec.ts` intermittently failed in Playwright strict mode while asserting that the protagonist was visible in the collection panel.

## Evidence

The failing locator was `page.locator('text=缓存测试角色')`. It matched both:

- the story paragraph in the main reading surface
- the protagonist card inside the collection dialog

Playwright strict mode rejected the assertion because the locator resolved to two elements.

## Root Cause

The E2E test used an unscoped page-level text locator for a value that can legitimately appear in story content and in the collection UI at the same time.

## Fix

The test now scopes protagonist assertions to the `收集` dialog and targets the protagonist card by accessible button name: `/缓存测试角色.*主角/`.

## Regression Coverage

Added `tests/test_gate_preflight_no_mock.py::test_collection_panel_cache_spec_uses_scoped_character_locator` to prevent this spec from regressing back to the ambiguous page-level text locator.

## Verification

Targeted verification:

```bash
python -m pytest tests/test_gate_preflight_no_mock.py::test_collection_panel_cache_spec_uses_scoped_character_locator -q
```

Browser verification:

```bash
npx playwright test e2e/collection-panel-cache.spec.ts --project=core --reporter=list --workers=1 --no-deps
```

Full gate verification:

```bash
./test.sh preflight
./test.sh e2e
```
