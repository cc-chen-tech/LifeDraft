## Why

Scene image generation must reuse a valid persisted scene rather than issuing a duplicate provider request, and character appearance anchors must survive persistence. These image lifecycle boundaries are underrepresented in the maintained gate.

## What Changes

- Add real SQLite and local-file contracts for valid scene reuse and persisted appearance-anchor recovery.
- Register the test module in both maintained backend workflow lists.

## Capabilities

### New Capabilities
- `scene-image-persistence-contracts`: Provider-free scene reuse and appearance-anchor persistence contracts.

### Modified Capabilities

- None.

## Impact

- Adds one test module covering `src/services/image/scene_service.py` with disposable storage.
