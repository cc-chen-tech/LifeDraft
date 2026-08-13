# story101 Visual Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver PR1 of the approved story101 visual-system rollout: warm ink tokens, backward-compatible UI primitive variants, shared state components, and a deterministic browser fixture.

**Architecture:** Keep existing shadcn primitives and calm narrative-loading behavior, then add role-based tokens and focused components on top. The hidden E2E regression route owns deterministic visual states; production pages consume the new foundation only in later PRs.

**Tech Stack:** Next.js 16, React 19, Tailwind CSS v4, Radix/shadcn, class-variance-authority, Jest/Testing Library, Playwright.

## Global Constraints

- Base commit is `184b5d5266e0f0a2d72c2d38d9cf7207a1c5745d`, verified against live `origin/main` at execution start.
- Frontend only. Do not modify APIs, stores, SSE, database code, media generation, ShareCard export, or narrative-loading copy/state behavior.
- Core palette: canvas `#0D0C0B`, reading `#11100F`, primary text `#F0ECE6`, muted text `#8F8881`, rule `#34302C`, non-text interaction boundary `#71675D`.
- Context colors: success `#9AAF98`, danger `#C58F8A`, warning `#C2A26E`; color is never the only status signal.
- `story101` brand role uses `@fontsource-variable/spline-sans@5.3.0` (OFL-1.1) Latin subset. Chinese UI remains the system sans stack; narrative copy remains the system Song/Ming stack.
- Page surfaces use 0–4px radius, controls 6px, overlays 10px. Reading surfaces have no shadow; shadows are reserved for overlays.
- Ordinary text contrast is at least 4.5:1. Controls and body text are at least 14px, auxiliary text at least 12px, and touch controls are at least 44×44px.
- Only `PageTransition` introduces the new 200ms/4px page entrance; `prefers-reduced-motion` makes it static. Do not add pulse, glow, skeleton, or spinner behavior.
- Preserve the existing `.narrative-loading` selectors and exact six calm-loading colors; they may reference equivalent global tokens only if computed values and tests remain unchanged.
- Use real semantic elements, visible `focus-visible`, valid labels/descriptions, and no duplicate live regions.
- Use TDD for every production behavior: focused RED, minimal GREEN, refactor, then regression suite.

---

### Task 1: Ink tokens, brand font, and primitive variants

**Files:**
- Modify: `.gitignore`
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Modify: `frontend/src/app/globals.css`
- Modify: `frontend/src/components/ui/button.tsx`
- Modify: `frontend/src/components/ui/input.tsx`
- Modify: `frontend/src/components/ui/textarea.tsx`
- Modify: `frontend/src/components/ui/badge.tsx`
- Create: `frontend/src/__tests__/components/ui/visualFoundationPrimitives.test.tsx`

**Interfaces:**
- `Button` adds variants `chrome | quiet | narrative | floating` and sizes `touch | icon-touch`; every existing variant and size remains source-compatible.
- `Input` and `Textarea` add optional `surface?: "default" | "filled" | "underline"` and `controlSize?: "default" | "touch"`.
- `Badge` adds variants `success | warning | danger | info` while retaining existing variants.
- CSS exposes `--surface-canvas`, `--surface-reading`, `--surface-raised`, `--surface-overlay`, `--surface-subtle`, `--text-primary`, `--text-secondary`, `--text-subtle`, `--border-default`, `--border-strong`, `--border-interactive`, semantic foreground/subtle/border variables, role radii, role shadows, `--font-brand`, and safe-area insets.

- [ ] **Step 1: Write failing primitive behavior tests**
  - Render real Button/Input/Textarea/Badge components.
  - Assert `touch` and `icon-touch` expose their selected `data-size`, new variants expose `data-variant`, inputs expose `data-surface` and `data-control-size`, and semantic badges render readable text without replacing it with color-only content.
  - The production changes these tests catch are missing/incorrect variant routing and lost native form semantics.

- [ ] **Step 2: Run RED**
  - Run: `npm run test:unit -- --runInBand src/__tests__/components/ui/visualFoundationPrimitives.test.tsx`
  - Expected: FAIL because the new props and variants do not exist.

- [ ] **Step 3: Install and import the brand font**
  - Run: `npm install --save-exact @fontsource-variable/spline-sans@5.3.0`
  - Import only the Latin variable weight CSS in `globals.css`; map it to `--font-brand` and a Tailwind `font-brand` theme token.

- [ ] **Step 4: Implement role tokens and variants**
  - Replace the cold-blue global aliases with the approved ink palette while keeping existing token names as compatibility aliases.
  - Add the exact role tokens and semantic triples from Global Constraints.
  - Implement the public variant props without changing native input/textarea/button behavior or existing variants.
  - `#71675D` must not be assigned to text color.

- [ ] **Step 5: Run GREEN and regressions**
  - Run the focused test, then existing Button/Card/Input-adjacent suites and `src/__tests__/components/NarrativeLoadingState.test.tsx`.
  - Run `npm run test:types` and target ESLint.

- [ ] **Step 6: Commit**
  - Commit message: `feat(ui): establish story101 visual tokens`

### Task 2: Shared surfaces, fields, feedback, transitions, and global states

**Files:**
- Create: `frontend/src/components/story101/Surface.tsx`
- Create: `frontend/src/components/story101/FormField.tsx`
- Create: `frontend/src/components/story101/FeedbackNotice.tsx`
- Create: `frontend/src/components/story101/PageTransition.tsx`
- Create: `frontend/src/components/story101/GlobalStatePage.tsx`
- Create: `frontend/src/components/story101/RouteLoadingState.tsx`
- Create: `frontend/src/components/story101/index.ts`
- Modify: `frontend/src/app/loading.tsx`
- Modify: `frontend/src/app/error.tsx`
- Modify: `frontend/src/app/global-error.tsx`
- Modify: `frontend/src/app/not-found.tsx`
- Create: `frontend/src/__tests__/components/story101/Story101Foundation.test.tsx`
- Create: `frontend/src/__tests__/app/GlobalStates.test.tsx`

**Interfaces:**
- `Surface({ variant?: "reading" | "raised" | "subtle" | "overlay", asChild?: boolean })` preserves element props and sets `data-variant`.
- `FormField({ id, label, description?, error?, required?, children })` uses a render child `({ describedBy, invalid }) => ReactNode`; it owns visible label and stable description/error IDs.
- `FeedbackNotice({ tone, title?, children, action? })`, where `tone` is `success | warning | danger | info`; danger uses `role="alert"`, other tones use one `role="status"` with `aria-live="polite"`.
- `PageTransition` is a semantic wrapper with `data-slot="page-transition"`; CSS owns its one-shot animation.
- `GlobalStatePage({ title, description, action })` presents one heading, one explanation, and a real button/link action.
- `RouteLoadingState` keeps an ink shell mounted, stays visually empty for 250ms, then renders exactly one hydrate `NarrativeLoadingState`.

- [ ] **Step 1: Write failing shared-component tests**
  - Assert the render-prop field wires label, `aria-describedby`, `aria-invalid`, description, and error without creating a fake tab stop.
  - Assert each feedback tone has exactly one correct live region and an optional real action.
  - Assert Surface and PageTransition preserve semantic element props and variants.

- [ ] **Step 2: Write failing global-state tests**
  - With fake timers, assert route loading is silent at 249ms and exposes one hydrate status at 250ms.
  - Assert route error and global error call the provided reset exactly once from a named button.
  - Assert not-found exposes a named link to `/`.

- [ ] **Step 3: Run RED**
  - Run the two new suites and observe failures caused by missing components/legacy spinner states.

- [ ] **Step 4: Implement shared components and migrate global states**
  - Use the exact interfaces above and existing `useDelayedLoading`/`NarrativeLoadingState` rather than adding timers or loading copy.
  - Keep Sentry capture behavior unchanged in both error boundaries.
  - `global-error.tsx` must remain a valid `<html><body>` root fallback.

- [ ] **Step 5: Run GREEN and regressions**
  - Run both new suites, narrative-loading tests, useDelayedLoading tests, types, and target ESLint.

- [ ] **Step 6: Commit**
  - Commit message: `feat(ui): unify foundational page states`

### Task 3: Deterministic visual-foundation fixture and browser acceptance

**Files:**
- Modify: `frontend/src/app/e2e-regression/page.tsx`
- Modify: `frontend/src/app/e2e-regression/E2ERegressionClient.tsx`
- Create: `frontend/e2e/story101-visual-foundation.spec.ts`
- Modify: `frontend/src/__tests__/components/NarrativeLoadingState.test.tsx` only if a regression assertion is needed; do not change its production contract.

**Interfaces:**
- Query `visualSystem=foundation` is a server allowlist entry rendering only `VisualFoundationFixture`; absent, arrays, or unknown values continue to SSR `E2ERegressionPageContent`.
- `VisualFoundationFixture` performs no `/api/*` request and renders real controls in normal, hover/focus-testable, disabled, invalid, success, warning, and danger states.
- The fixture is regression infrastructure, not the product-design source of truth.

- [ ] **Step 1: Write the failing Playwright contract**
  - Assert no-JavaScript response HTML contains only the allowlisted foundation fixture.
  - Assert computed core token values, Spline Sans brand family, 44px touch controls, minimum text sizes, semantic live regions, visible invalid text, and no horizontal overflow.
  - Assert no `/api/*` request and no navigation/reload from local fixture actions.
  - Capture desktop 1440×900 and mobile 390×844 evidence; run additional overflow assertions at 320px and 375px.

- [ ] **Step 2: Run RED**
  - Run the spec in `core` with `--workers=1 --retries=0`.
  - Expected: FAIL because the allowlisted fixture does not exist.

- [ ] **Step 3: Implement the server gate and fixture**
  - Preserve the existing narrative-loading SSR allowlist exactly.
  - Add the foundation fixture without mounting legacy hooks or product APIs.
  - Use only real story101 primitives and meaningful Chinese state copy.

- [ ] **Step 4: Run GREEN on desktop and mobile**
  - Run the exact spec for `core` and `Mobile Safari`, then types and target ESLint.
  - Inspect screenshots for clipping, nested-card appearance, glow, unreadable utility text, and color-only status.

- [ ] **Step 5: Run PR1 verification**
  - Run all PR1 focused Jest suites, `npm run test:types`, `npm run lint`, and `git diff --check`.
  - Run `./scripts/test-run-isolated.sh --namespace story101_visual_foundation all` before publishing PR1.

- [ ] **Step 6: Commit**
  - Commit message: `test(e2e): cover story101 visual foundation`
