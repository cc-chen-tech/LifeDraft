/**
 * Type-safe store method spy utility.
 * Replaces selected store methods with jest.fn() spies and returns typed references.
 *
 * Usage:
 *   const { spies, restore } = spyOnStoreMethods(useGameStore, ['saveGame', 'syncState']);
 *   // spies.saveGame is typed as jest.Mock
 *   // spies.saveGame.mockResolvedValue(...)
 *   // ...
 *   restore(); // in afterEach
 */
export function spyOnStoreMethods<
  T extends Record<string, any>,
  K extends keyof T & string
>(
  store: { getState: () => T; setState: (partial: Partial<T>) => void },
  methodNames: readonly K[]
): {
  spies: { [P in K]: jest.Mock };
  restore: () => void;
} {
  const state = store.getState() as Record<string, any>;
  const originals: Record<string, Function> = {};
  const spies: Record<string, jest.Mock> = {};

  for (const key of methodNames) {
    const original = state[key];
    if (typeof original === 'function') {
      originals[key] = original as Function;
      const spy = jest.fn().mockResolvedValue(undefined);
      state[key] = spy;
      spies[key] = spy;
    } else {
      // Non-function properties become a no-op spy to keep types consistent
      const spy = jest.fn().mockResolvedValue(undefined);
      state[key] = spy;
      spies[key] = spy;
    }
  }

  function restore() {
    const currentState = store.getState() as Record<string, any>;
    for (const [key, fn] of Object.entries(originals)) {
      currentState[key] = fn;
    }
  }

  return { spies: spies as any, restore };
}

/**
 * Convenience: spy on useGameStore methods.
 * Re-exports spyOnStoreMethods for backwards compatibility with the existing pattern.
 */
export { spyOnStoreMethods as spyOnStore };
