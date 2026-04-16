# Integration Tests

This directory contains integration tests that verify the interaction between multiple units of the application.

## Directory Structure

```
__tests__/integration/
├── api/           # API integration tests
├── stores/        # Store interaction tests
└── components/    # Component combination tests
```

## Test Categories

### API Integration Tests (`/api/`)

Tests that verify the integration between frontend services and API endpoints.

- **Responsibility**: Test API client functions, request/response handling, error scenarios
- **Mocking**: Use MSW (Mock Service Worker) to mock backend API responses
- **When to add**: When adding new API endpoints, modifying request/response schemas, or testing error handling

Example scenarios:
- API client correctly serializes request payloads
- API client handles authentication headers
- API client correctly parses response data
- API error responses are handled gracefully

### Store Integration Tests (`/stores/`)

Tests that verify Zustand store interactions and state management across multiple actions.

- **Responsibility**: Test state transitions, action sequences, and store-to-store interactions
- **Mocking**: Mock API layer, but test real store logic
- **When to add**: When adding complex state transitions, cross-store dependencies, or async action flows

Example scenarios:
- A sequence of user actions results in correct state
- Multiple stores interact correctly (e.g., auth store affects game store)
- Async actions update loading and error states properly
- State persistence and hydration work correctly

### Component Integration Tests (`/components/`)

Tests that verify multiple components working together.

- **Responsibility**: Test component composition, prop drilling alternatives, and shared state
- **Mocking**: Mock stores and API, but render real components
- **When to add**: When components have complex interactions or shared context

Example scenarios:
- Parent-child component communication
- Components sharing a store update together
- Form components with validation feedback
- Modal/dialog flows with multiple steps

## Test Pyramid

```
       /\
      /  \
     / E2E \      <- Few tests, full system (expensive, slow)
    /--------\
   /          \
  / Integration \  <- Medium tests, multiple units (balanced)
 /--------------\
/                \
/      Unit        \ <- Many tests, isolated (fast, cheap)
/--------------------\
```

### Test Type Responsibilities

| Test Type | Scope | Speed | Cost | When to Use |
|-----------|-------|-------|------|-------------|
| **Unit** | Single function/component | Fast | Low | Business logic, pure functions, component rendering |
| **Integration** | Multiple units together | Medium | Medium | API contracts, state flows, component interactions |
| **E2E** | Full application | Slow | High | Critical user journeys, cross-browser issues |

### When to Add Which Test

1. **Start with Unit Tests** for:
   - Pure utility functions
   - Individual component rendering
   - Reducer logic
   - Simple store actions

2. **Add Integration Tests** when:
   - Testing API request/response cycles
   - Verifying state changes across multiple actions
   - Components interact through shared state
   - Integration points between modules

3. **Add E2E Tests** for:
   - Critical user paths (login, checkout, etc.)
   - Cross-browser compatibility
   - Production-like environment validation
   - Smoke tests after deployment

## E2E Test Selection Criteria

Before adding an E2E test, consider:

1. **Is this a critical user journey?** - E2E tests are expensive; reserve them for high-value paths
2. **Can this be tested at a lower level?** - Prefer unit/integration tests when possible
3. **Does this involve browser-specific behavior?** - E2E is appropriate for testing actual browser APIs
4. **Is this a cross-system integration?** - E2E validates the full stack works together

### E2E Test Checklist

- [ ] Tests a complete user workflow from start to finish
- [ ] Cannot be adequately tested with unit/integration tests
- [ ] Has clear success/failure criteria visible in the UI
- [ ] Runs in a reasonable time (under 30 seconds per test)
- [ ] Is stable and not flaky

## Running Tests

```bash
# Run all unit tests (excludes integration)
npm run test:unit

# Run integration tests only
npm run test:integration

# Run all tests (unit + integration)
npm test

# Run E2E tests
npm run test:e2e

# Run E2E tests with UI
npm run test:e2e:ui
```

## MSW (Mock Service Worker)

Integration tests use MSW to mock API responses. This allows testing the frontend in isolation while maintaining realistic request/response cycles.

### Setup

MSW handlers are defined in `src/mocks/handlers.ts` and configured in `jest.setup.js`.

### Example Handler

```typescript
// src/mocks/handlers.ts
import { http, HttpResponse } from 'msw';

export const handlers = [
  http.get('/api/health', () => {
    return HttpResponse.json({ status: 'ok' });
  }),
];
```

## Best Practices

1. **Test behavior, not implementation** - Focus on what the code does, not how it does it
2. **One concept per test** - Each test should verify one specific behavior
3. **Descriptive test names** - Test names should explain the expected behavior
4. **Arrange-Act-Assert** - Structure tests clearly with setup, action, and verification phases
5. **Clean up after tests** - Reset mocks and store state between tests
