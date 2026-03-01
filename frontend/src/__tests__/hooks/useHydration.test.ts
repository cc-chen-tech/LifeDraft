/**
 * hooks/useHydration.ts Tests
 * Tests for Zustand persist hydration hook
 * 
 * Note: In Jest's test environment, useEffect runs synchronously,
 * so the initial render already has hydrated=true.
 */
import { renderHook, act } from '@testing-library/react';
import { useHydration } from '@/hooks/useHydration';

describe('useHydration', () => {
  it('returns a boolean value', () => {
    const { result } = renderHook(() => useHydration());
    expect(typeof result.current).toBe('boolean');
  });

  it('returns true after hydration (useEffect runs)', () => {
    const { result } = renderHook(() => useHydration());
    // In Jest, useEffect runs synchronously, so hydrated is already true
    expect(result.current).toBe(true);
  });

  it('maintains true value on subsequent renders', () => {
    const { result, rerender } = renderHook(() => useHydration());

    expect(result.current).toBe(true);

    // Should stay true
    rerender();
    expect(result.current).toBe(true);

    rerender();
    expect(result.current).toBe(true);
  });

  it('works with multiple hook instances', () => {
    const { result: result1 } = renderHook(() => useHydration());
    const { result: result2 } = renderHook(() => useHydration());

    // Both should be true after hydration
    expect(result1.current).toBe(true);
    expect(result2.current).toBe(true);
  });

  it('cleans up effect on unmount', () => {
    const { unmount, result } = renderHook(() => useHydration());

    // Let the effect run
    act(() => {});
    expect(result.current).toBe(true);

    // Should not throw on unmount
    expect(() => unmount()).not.toThrow();
  });
});
