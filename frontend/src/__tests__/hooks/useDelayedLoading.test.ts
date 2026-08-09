import { act, renderHook } from "@testing-library/react";
import { getNarrativeLoadingDelay } from "@/components/narrative-loading/NarrativeLoadingState";
import { useDelayedLoading } from "@/hooks/useDelayedLoading";

describe("getNarrativeLoadingDelay", () => {
  it.each([
    ["hydrate", undefined, 250],
    ["character-step", undefined, 15_000],
    ["ending", undefined, 15_000],
    ["character-auto", undefined, 30_000],
    ["gameplay", "fast", 45_000],
    ["gameplay", "expert", 90_000],
    ["opening", "master", 180_000],
  ] as const)("returns %dms for %s", (context, quality, delay) => {
    expect(getNarrativeLoadingDelay(context, quality)).toBe(delay);
  });
});

describe("useDelayedLoading", () => {
  beforeEach(() => jest.useFakeTimers());
  afterEach(() => jest.useRealTimers());

  it("waits 250ms for hydration before becoming visible", () => {
    const { result } = renderHook(() =>
      useDelayedLoading({ isLoading: true, delay: 250, loadingIdentity: "route:/story/opening" })
    );
    expect(result.current).toBe(false);
    act(() => jest.advanceTimersByTime(249));
    expect(result.current).toBe(false);
    act(() => jest.advanceTimersByTime(1));
    expect(result.current).toBe(true);
  });

  it("uses a single timeout for the configured character and quality thresholds", () => {
    const timeout = jest.spyOn(global, "setTimeout");
    const { result, rerender } = renderHook(
      ({ delay }) => useDelayedLoading({ isLoading: true, delay, loadingIdentity: "generation:42" }),
      { initialProps: { delay: 15_000 } }
    );
    expect(result.current).toBe(false);
    expect(timeout).toHaveBeenCalledTimes(1);
    act(() => jest.advanceTimersByTime(15_000));
    expect(result.current).toBe(true);

    rerender({ delay: 45_000 });
    expect(timeout).toHaveBeenCalledTimes(1);
  });

  it("resets the one-shot timeout only when the loading identity changes", () => {
    const { result, rerender } = renderHook(
      ({ identity, phase }) => useDelayedLoading({ isLoading: true, delay: 30_000, loadingIdentity: identity }),
      { initialProps: { identity: "auto:one", phase: "preparing" } }
    );
    act(() => jest.advanceTimersByTime(29_000));
    rerender({ identity: "auto:one", phase: "generating" });
    act(() => jest.advanceTimersByTime(1_000));
    expect(result.current).toBe(true);

    rerender({ identity: "auto:two", phase: "preparing" });
    expect(result.current).toBe(false);
    act(() => jest.advanceTimersByTime(29_999));
    expect(result.current).toBe(false);
    act(() => jest.advanceTimersByTime(1));
    expect(result.current).toBe(true);
  });
});
