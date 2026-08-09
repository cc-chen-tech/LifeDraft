## Context

The facade used by API routes reads image records and saved game fields before it delegates generation. Existing maintained tests cover several helpers but not the persisted lookup order that protects cross-game image references or restores image-relevant character fields.

## Goals / Non-Goals

**Goals:** Verify actual SQLite records and local image files across active-image selection, primary fallback, reference encoding, and saved-state fallback.

**Non-Goals:** Invoke an image provider, generate an image, or exercise background thread behavior.

## Decisions

- Construct `ImageService` without its normal constructor and inject only a real SQLAlchemy session plus `ImageStorageService`; this isolates read-side persistence behavior from provider setup.
- Use a small Pillow-generated image in temporary local storage so the reference compression path and data URL are real.
- Seed both `GameState` and `Game.initial_state` records to assert their documented preference order.

## Risks / Trade-offs

- [Image compression varies by library version] -> Assert the data URL type and decoded payload behavior rather than an exact JPEG byte sequence.
- [Does not exercise provider-facing delegate methods] -> Keep provider behavior in separate transport contracts; this change fixes the data ownership boundary.
