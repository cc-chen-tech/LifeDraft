# Harden Session Recovery DB Contracts

## Why

Save/resume failures often arise when snapshot selection, legacy field recovery,
ownership checks, and in-memory session restoration are verified independently.

## What Changes

- Add real database contracts for choosing the newest saved state and filling
  compatible identity fields from the original game state.
- Add SessionService recovery coverage for owner isolation and session cleanup.
- Include the new test in the maintained backend manifest.

## Scope

This change only adds tests, test selection, and OpenSpec artifacts.
