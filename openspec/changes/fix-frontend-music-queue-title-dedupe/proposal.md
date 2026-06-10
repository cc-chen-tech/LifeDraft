## Why

Backend music recommendation and persistent playlist merge now dedupe reported
title families such as `绅士` and `红尘客栈`, but the frontend music store still
performs its local queue merge by provider id only. When playlist persistence is
slow or unavailable, the optimistic queue can still expose repeated title-family
variants before the server response corrects it.

## What Changes

- Mirror the backend title-family normalization in `useMusicStore`.
- Dedupe the local future queue by both provider id and normalized title family.
- Preserve the current song and generated AI tracks while filtering duplicate
  NetEase variants.

## Impact

- `frontend/src/stores/useMusicStore.ts`
- Frontend music queue policy tests
