import { act, renderHook } from '@testing-library/react';
import { useEventGenerator } from '@/hooks/game/useEventGenerator';
import { useGameStore } from '@/stores/useGameStore';
import type { StreamCallbacks } from '@/lib/sse';
import type { Phase } from '@/hooks/game/usePhaseManager';

const mockStreamGameEvent = jest.fn<Promise<void>, [number, StreamCallbacks, { signal?: AbortSignal; lastEventId?: number }?]>();

jest.mock('@/lib/sse', () => ({
  streamGameEvent: (...args: [number, StreamCallbacks, { signal?: AbortSignal; lastEventId?: number }?]) =>
    mockStreamGameEvent(...args),
}));

function pendingStream(): Promise<void> {
  return new Promise(() => {});
}

function flushMicrotasks() {
  return act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe('useEventGenerator run isolation', () => {
  const phaseRef: React.MutableRefObject<Phase> = { current: 'loading' };
  const runTokenRef: React.MutableRefObject<number> = { current: 0 };
  const abortRef: React.MutableRefObject<AbortController | null> = { current: null };
  const generatingRef: React.MutableRefObject<boolean> = { current: false };
  const pollingRef: React.MutableRefObject<boolean> = { current: false };
  const prefetchAbortRef: React.MutableRefObject<AbortController | null> = { current: null };
  const prefetchResultRef: React.MutableRefObject<never> = { current: null };
  const prefetchingRef: React.MutableRefObject<boolean> = { current: false };
  const isRetryingRef: React.MutableRefObject<boolean> = { current: false };

  const setters = {
    setPhase: jest.fn(),
    setConnectionStatus: jest.fn(),
    setReconnectAttempt: jest.fn(),
    setTransport: jest.fn(),
    setLoadingIdentity: jest.fn(),
    setProcessing: jest.fn(),
    setOptions: jest.fn(),
    setStoryText: jest.fn(),
    appendStoryText: jest.fn(),
    setCurrentEvent: jest.fn(),
    setGameOver: jest.fn(),
    setRoundSummary: jest.fn(),
    setIsPrefetching: jest.fn(),
  };

  const params = {
    gameId: 1,
    phaseRef,
    runTokenRef,
    abortRef,
    generatingRef,
    pollingRef,
    prefetchAbortRef,
    prefetchResultRef,
    prefetchingRef,
    isRetryingRef,
    ...setters,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    (global.fetch as jest.Mock).mockReset().mockResolvedValue({
      ok: true,
      json: async () => ({ current_event: null, round_info: { game_over: false } }),
    });
    window.sessionStorage.clear();
    phaseRef.current = 'loading';
    runTokenRef.current = 0;
    abortRef.current = null;
    generatingRef.current = false;
    pollingRef.current = false;
    prefetchAbortRef.current = null;
    prefetchingRef.current = false;
    isRetryingRef.current = false;
    mockStreamGameEvent.mockImplementation(pendingStream);
    useGameStore.setState({
      storyText: '',
      currentEvent: null,
      syncState: jest.fn().mockResolvedValue(undefined),
      syncPlayerState: jest.fn().mockResolvedValue(undefined),
      generateRoundSceneImage: jest.fn().mockResolvedValue(undefined),
    } as never);
  });

  it('does not poll or fail when the captured stream reports AbortError', async () => {
    const syncState = jest.fn().mockImplementation(async () => {
      useGameStore.setState({
        storyText: '不应读取的旧故事',
        currentEvent: { story: '不应读取的旧故事', options: [{ text: '旧选项' }] },
      } as never);
    });
    useGameStore.setState({ syncState } as never);
    const { result } = renderHook(() => useEventGenerator(params));

    act(() => { void result.current.generateEvent(); });
    await flushMicrotasks();
    const callbacks = mockStreamGameEvent.mock.calls[0][1];

    await act(async () => {
      await callbacks.onError?.(new DOMException('superseded', 'AbortError'));
    });

    expect(syncState).not.toHaveBeenCalled();
    expect(setters.setTransport).not.toHaveBeenCalledWith('polling');
    expect(setters.setTransport).not.toHaveBeenCalledWith('failed');
    expect(setters.setPhase).not.toHaveBeenCalledWith('error');
  });

  it('does not poll or fail when the stream promise rejects with AbortError', async () => {
    mockStreamGameEvent.mockRejectedValue(new DOMException('superseded', 'AbortError'));
    const { result } = renderHook(() => useEventGenerator(params));

    await act(async () => {
      await result.current.generateEvent();
    });

    expect(global.fetch).not.toHaveBeenCalled();
    expect(setters.setTransport).not.toHaveBeenCalledWith('polling');
    expect(setters.setTransport).not.toHaveBeenCalledWith('failed');
    expect(setters.setPhase).not.toHaveBeenCalledWith('error');
  });

  it('silences every callback from a superseded run while current callbacks still commit', async () => {
    const syncState = jest.fn().mockImplementation(async () => {
      useGameStore.setState({
        storyText: 'A 轮询写入',
        currentEvent: { story: 'A 轮询写入', options: [{ text: 'A 轮询选项' }] },
      } as never);
    });
    useGameStore.setState({ syncState } as never);
    const { result } = renderHook(() => useEventGenerator(params));

    act(() => { void result.current.generateEvent(); });
    await flushMicrotasks();
    const callbacksA = mockStreamGameEvent.mock.calls[0][1];

    act(() => { void result.current.recoverEventGeneration(); });
    await flushMicrotasks();
    expect(mockStreamGameEvent).toHaveBeenCalledTimes(2);
    const callbacksB = mockStreamGameEvent.mock.calls[1][1];
    const baseline = Object.fromEntries(
      Object.entries(setters).map(([name, setter]) => [name, setter.mock.calls.length]),
    );
    window.sessionStorage.setItem('story101:event-cursor:1', '22');
    window.sessionStorage.setItem('story101:event-story:1', 'B 的正文');

    await act(async () => {
      callbacksA.onStory?.('A 的旧正文');
      callbacksA.onStatus?.({ phase: 'generating_story' });
      callbacksA.onConnectionStatus?.('reconnecting');
      callbacksA.onReconnecting?.(1, 3);
      callbacksA.onEventId?.(9);
      callbacksA.onComplete?.({ event_description: 'A 的完整旧正文', options: [{ text: 'A 选项' }] });
      await callbacksA.onError?.(new Error('network error'));
      await Promise.resolve();
    });

    for (const [name, count] of Object.entries(baseline)) {
      expect(setters[name as keyof typeof setters]).toHaveBeenCalledTimes(count);
    }
    expect(syncState).not.toHaveBeenCalled();
    expect(window.sessionStorage.getItem('story101:event-cursor:1')).toBe('22');
    expect(window.sessionStorage.getItem('story101:event-story:1')).toBe('B 的正文');

    await act(async () => {
      callbacksB.onStory?.('B 的当前正文');
      callbacksB.onStatus?.({ phase: 'generating_story' });
      callbacksB.onEventId?.(23);
      callbacksB.onComplete?.({ event_description: 'B 的当前正文', options: [{ text: 'B 选项' }] });
      await Promise.resolve();
    });

    expect(setters.appendStoryText).toHaveBeenCalledWith('B 的当前正文');
    expect(setters.setProcessing).toHaveBeenCalledWith(true, 'generating_story');
    expect(setters.setOptions).toHaveBeenCalledWith([{ text: 'B 选项' }]);
  });

  it.each([
    ['heartbeat status', (callbacks: StreamCallbacks) => callbacks.onStatus?.({ phase: 'generating_story', heartbeat: true })],
    ['ordinary status', (callbacks: StreamCallbacks) => callbacks.onStatus?.({ phase: 'validating' })],
    ['story', (callbacks: StreamCallbacks) => callbacks.onStory?.('仍在继续的正文')],
  ] as const)('resets the continuous inactivity deadline after %s activity', async (_name, sendActivity) => {
    jest.useFakeTimers();
    const { result, unmount } = renderHook(() => useEventGenerator(params));

    act(() => { void result.current.generateEvent(); });
    await flushMicrotasks();
    const callbacks = mockStreamGameEvent.mock.calls[0][1];

    await act(async () => { await jest.advanceTimersByTimeAsync(44_999); });
    expect(mockStreamGameEvent).toHaveBeenCalledTimes(1);
    act(() => { sendActivity(callbacks); });
    await act(async () => { await jest.advanceTimersByTimeAsync(44_999); });
    expect(mockStreamGameEvent).toHaveBeenCalledTimes(1);
    await act(async () => { await jest.advanceTimersByTimeAsync(1); });

    expect(mockStreamGameEvent).toHaveBeenCalledTimes(2);
    expect(setters.setTransport).toHaveBeenCalledWith('reconnecting');

    unmount();
    jest.clearAllTimers();
    jest.useRealTimers();
  });

  it('performs a real resume before read-only polling and returns active after persisted completion', async () => {
    const syncState = jest.fn().mockImplementation(async () => {
      useGameStore.setState({
        storyText: 'legacy poll',
        currentEvent: { story: 'legacy poll', options: [{ text: 'legacy' }] },
      } as never);
    });
    useGameStore.setState({ syncState } as never);
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        current_event: {
          event_description: '服务端已完成正文',
          options: [{ text: '继续' }],
        },
      }),
    });
    const { result } = renderHook(() => useEventGenerator(params));

    act(() => { void result.current.generateEvent(); });
    await flushMicrotasks();
    const callbacksA = mockStreamGameEvent.mock.calls[0][1];
    await act(async () => { await callbacksA.onError?.(new Error('network error')); });

    expect(mockStreamGameEvent).toHaveBeenCalledTimes(2);
    expect(mockStreamGameEvent.mock.calls[1][2]?.lastEventId).toBe(-1);
    const callbacksB = mockStreamGameEvent.mock.calls[1][1];
    await act(async () => { await callbacksB.onError?.(new Error('network error')); });
    await flushMicrotasks();

    expect(syncState).not.toHaveBeenCalled();
    expect(setters.setTransport.mock.calls.map(([transport]) => transport)).toEqual(
      expect.arrayContaining(['active', 'reconnecting', 'polling', 'active']),
    );
    expect(setters.setOptions).toHaveBeenCalledWith([{ text: '继续' }]);
    expect(setters.setPhase).toHaveBeenCalledWith('options');
  });

  it('does not accept persisted options as complete until a story body is available', async () => {
    jest.useFakeTimers();
    (global.fetch as jest.Mock)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ current_event: { event_description: '', options: [{ text: 'too early' }] } }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          current_event: { event_description: 'persisted complete story', options: [{ text: 'continue' }] },
        }),
      });
    const { result, unmount } = renderHook(() => useEventGenerator(params));

    act(() => { void result.current.generateEvent(); });
    await flushMicrotasks();
    act(() => { mockStreamGameEvent.mock.calls[0][1].onError?.(new Error('network error')); });
    await flushMicrotasks();
    act(() => { mockStreamGameEvent.mock.calls[1][1].onError?.(new Error('network error')); });
    await flushMicrotasks();

    expect(setters.setOptions).not.toHaveBeenCalledWith([{ text: 'too early' }]);
    await act(async () => {
      await jest.advanceTimersByTimeAsync(5_000);
    });
    expect(setters.setOptions).toHaveBeenCalledWith([{ text: 'continue' }]);
    expect(setters.setStoryText).toHaveBeenCalledWith('persisted complete story');

    unmount();
    jest.clearAllTimers();
    jest.useRealTimers();
  });

  it('does not commit an in-flight persisted snapshot after a newer resume run starts', async () => {
    jest.useFakeTimers();
    let resolveSnapshot!: (response: Response) => void;
    const pendingSnapshot = new Promise<Response>((resolve) => {
      resolveSnapshot = resolve;
    });
    (global.fetch as jest.Mock).mockReturnValue(pendingSnapshot);
    const { result, unmount } = renderHook(() => useEventGenerator(params));

    act(() => { void result.current.generateEvent(); });
    await flushMicrotasks();
    const callbacksA = mockStreamGameEvent.mock.calls[0][1];
    act(() => { callbacksA.onError?.(new Error('network error')); });
    await flushMicrotasks();
    const callbacksAResume = mockStreamGameEvent.mock.calls[1][1];
    act(() => { callbacksAResume.onError?.(new Error('network error')); });
    await flushMicrotasks();
    expect(global.fetch).toHaveBeenCalledTimes(1);

    act(() => { void result.current.recoverEventGeneration(); });
    await flushMicrotasks();
    expect(mockStreamGameEvent).toHaveBeenCalledTimes(3);
    const currentSignal = mockStreamGameEvent.mock.calls[2][2]?.signal;
    const baseline = Object.fromEntries(
      Object.entries(setters).map(([name, setter]) => [name, setter.mock.calls.length]),
    );

    await act(async () => {
      resolveSnapshot({
        ok: true,
        json: async () => ({
          current_event: {
            event_description: 'OLD persisted story',
            options: [{ text: 'OLD persisted option' }],
          },
        }),
      } as Response);
      await pendingSnapshot;
      await Promise.resolve();
    });

    for (const [name, count] of Object.entries(baseline)) {
      expect(setters[name as keyof typeof setters]).toHaveBeenCalledTimes(count);
    }
    expect(currentSignal?.aborted).toBe(false);
    await act(async () => {
      await jest.advanceTimersByTimeAsync(5_000);
    });
    expect(global.fetch).toHaveBeenCalledTimes(1);

    unmount();
    jest.clearAllTimers();
    jest.useRealTimers();
  });

  it('does not let a stale 404 restore or its delayed retry create a third subscriber', async () => {
    jest.useFakeTimers();
    let resolveRestore!: (response: Response) => void;
    const pendingRestore = new Promise<Response>((resolve) => {
      resolveRestore = resolve;
    });
    (global.fetch as jest.Mock).mockReturnValue(pendingRestore);
    const { result, unmount } = renderHook(() => useEventGenerator(params));

    act(() => { void result.current.generateEvent(); });
    await flushMicrotasks();
    const callbacksA = mockStreamGameEvent.mock.calls[0][1];
    act(() => { callbacksA.onError?.({ message: '404 Not Found' }); });
    await flushMicrotasks();
    expect(global.fetch).toHaveBeenCalledTimes(1);

    act(() => { void result.current.recoverEventGeneration(); });
    await flushMicrotasks();
    expect(mockStreamGameEvent).toHaveBeenCalledTimes(2);
    const currentSignal = mockStreamGameEvent.mock.calls[1][2]?.signal;
    const baseline = Object.fromEntries(
      Object.entries(setters).map(([name, setter]) => [name, setter.mock.calls.length]),
    );

    await act(async () => {
      resolveRestore({
        ok: true,
        json: async () => ({ current_event: null, round_info: { game_over: false } }),
      } as Response);
      await pendingRestore;
      await Promise.resolve();
      await jest.advanceTimersByTimeAsync(100);
    });

    expect(mockStreamGameEvent).toHaveBeenCalledTimes(2);
    for (const [name, count] of Object.entries(baseline)) {
      expect(setters[name as keyof typeof setters]).toHaveBeenCalledTimes(count);
    }
    expect(currentSignal?.aborted).toBe(false);

    unmount();
    jest.clearAllTimers();
    jest.useRealTimers();
  });

  it('uses a read-only 404 restore and ignores buffered frames while it is pending', async () => {
    let resolveRestore!: (response: Response) => void;
    const pendingRestore = new Promise<Response>((resolve) => {
      resolveRestore = resolve;
    });
    (global.fetch as jest.Mock).mockReturnValue(pendingRestore);
    const syncPlayerState = jest.fn().mockResolvedValue(undefined);
    useGameStore.setState({ syncPlayerState } as never);
    const { result } = renderHook(() => useEventGenerator(params));

    act(() => { void result.current.generateEvent(); });
    await flushMicrotasks();
    const callbacks = mockStreamGameEvent.mock.calls[0][1];
    act(() => { callbacks.onError?.({ message: '404 Not Found' }); });
    await flushMicrotasks();
    Object.values(setters).forEach((setter) => setter.mockClear());

    act(() => {
      callbacks.onStory?.('buffered OLD story');
      callbacks.onStatus?.({ phase: 'buffered OLD status' });
      callbacks.onEventId?.(99);
      callbacks.onComplete?.({ event_description: 'buffered OLD complete', options: [{ text: 'OLD' }] });
    });

    expect(syncPlayerState).not.toHaveBeenCalled();
    expect(setters.appendStoryText).not.toHaveBeenCalled();
    expect(setters.setProcessing).not.toHaveBeenCalled();
    expect(setters.setOptions).not.toHaveBeenCalled();
    expect(window.sessionStorage.getItem('story101:event-cursor:1')).toBeNull();

    resolveRestore({
      ok: true,
      json: async () => ({ current_event: null, round_info: { game_over: false } }),
    } as Response);
  });

  it('keeps a superseded prefetch response from mutating the next game stores', async () => {
    let resolveLegacySync!: () => void;
    const legacySyncGate = new Promise<void>((resolve) => {
      resolveLegacySync = resolve;
    });
    let resolveSnapshot!: (response: Response) => void;
    const snapshotResponse = new Promise<Response>((resolve) => {
      resolveSnapshot = resolve;
    });
    (global.fetch as jest.Mock).mockReturnValue(snapshotResponse);
    const syncPlayerState = jest.fn(async () => {
      await legacySyncGate;
      useGameStore.setState({
        playerState: { player_name: 'STALE A player' },
        progress: { week: 1 },
        roundInfo: { week: 1, current_round: 0 },
        storyText: 'STALE A story',
      } as never);
    });
    useGameStore.setState({ syncPlayerState } as never);
    const { result, rerender } = renderHook(
      ({ gameId }) => useEventGenerator({ ...params, gameId }),
      { initialProps: { gameId: 1 } },
    );

    act(() => { void result.current.prefetchNextEvent(); });
    await flushMicrotasks();

    act(() => {
      rerender({ gameId: 2 });
      useGameStore.setState({
        gameId: 2,
        playerState: { player_name: 'B player' },
        progress: { week: 8 },
        roundInfo: { week: 8, current_round: 2 },
        storyText: 'B story',
      } as never);
    });
    resolveLegacySync();
    resolveSnapshot({
      ok: true,
      json: async () => ({
        player_state: { player_name: 'STALE A player' },
        progress: { week: 1 },
        round_info: { week: 1, current_round: 0 },
        current_event: null,
      }),
    } as Response);
    await flushMicrotasks();

    expect(syncPlayerState).not.toHaveBeenCalled();
    expect(mockStreamGameEvent).not.toHaveBeenCalled();
    expect(useGameStore.getState()).toEqual(expect.objectContaining({
      gameId: 2,
      playerState: { player_name: 'B player' },
      progress: { week: 8 },
      roundInfo: { week: 8, current_round: 2 },
      storyText: 'B story',
    }));
  });

  it('completes durable game-over state discovered by polling', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
        current_event: null,
        player_state: { resume_view: { phase: 'ending' } },
        progress: { week: 52, total_weeks: 52 },
      }),
    });
    const { result, unmount } = renderHook(() => useEventGenerator(params));

    act(() => { void result.current.generateEvent(); });
    await flushMicrotasks();
    act(() => { mockStreamGameEvent.mock.calls[0][1].onError?.(new Error('network error')); });
    await flushMicrotasks();
    act(() => { mockStreamGameEvent.mock.calls[1][1].onError?.(new Error('network error')); });
    await flushMicrotasks();

    expect(setters.setGameOver).toHaveBeenCalledWith(true);
    expect(setters.setPhase).toHaveBeenCalledWith('ending');
    expect(setters.setTransport).toHaveBeenCalledWith('active');
    unmount();
  });

  it('enforces the polling deadline even when one persisted GET hangs', async () => {
    jest.useFakeTimers();
    let pollSignal: AbortSignal | undefined;
    (global.fetch as jest.Mock).mockImplementation((_url: string, init: RequestInit) => {
      pollSignal = init.signal as AbortSignal;
      return new Promise((_resolve, reject) => {
        pollSignal?.addEventListener('abort', () => {
          reject(new DOMException('request deadline', 'AbortError'));
        }, { once: true });
      });
    });
    const { result, unmount } = renderHook(() => useEventGenerator(params));

    act(() => { void result.current.generateEvent(); });
    await flushMicrotasks();
    act(() => { mockStreamGameEvent.mock.calls[0][1].onError?.(new Error('network error')); });
    await flushMicrotasks();
    act(() => { mockStreamGameEvent.mock.calls[1][1].onError?.(new Error('network error')); });
    await flushMicrotasks();

    await act(async () => { await jest.advanceTimersByTimeAsync(180_000); });

    expect(pollSignal?.aborted).toBe(true);
    expect(setters.setTransport).toHaveBeenCalledWith('failed');
    unmount();
    jest.clearAllTimers();
    jest.useRealTimers();
  });

  it('clears durable resume state and omits the cursor for an explicit fresh retry', async () => {
    window.sessionStorage.setItem('story101:event-cursor:1', '18');
    window.sessionStorage.setItem('story101:event-story:1', 'failed partial story');
    phaseRef.current = 'error';
    const { result } = renderHook(() => useEventGenerator(params));
    await flushMicrotasks();

    act(() => { void result.current.generateEvent(); });
    await flushMicrotasks();

    expect(mockStreamGameEvent.mock.calls[0][2]?.lastEventId).toBeUndefined();
    expect(window.sessionStorage.getItem('story101:event-cursor:1')).toBeNull();
    expect(window.sessionStorage.getItem('story101:event-story:1')).toBeNull();
  });

  it('invalidates the durable cursor and story as soon as the backend restarts a retry epoch', async () => {
    const first = renderHook(() => useEventGenerator(params));
    act(() => { void first.result.current.generateEvent(); });
    await flushMicrotasks();
    const firstCallbacks = mockStreamGameEvent.mock.calls[0][1];

    act(() => {
      useGameStore.setState({ storyText: 'rejected old epoch story' } as never);
      firstCallbacks.onEventId?.(7);
    });
    expect(window.sessionStorage.getItem('story101:event-cursor:1')).toBe('7');
    expect(window.sessionStorage.getItem('story101:event-story:1')).toBe('rejected old epoch story');

    act(() => {
      firstCallbacks.onStatus?.({ phase: 'retry' });
    });

    expect(window.sessionStorage.getItem('story101:event-cursor:1')).toBeNull();
    expect(window.sessionStorage.getItem('story101:event-story:1')).toBeNull();
    first.unmount();

    useGameStore.setState({ storyText: '' } as never);
    phaseRef.current = 'generating';
    generatingRef.current = true;
    const refreshed = renderHook(() => useEventGenerator(params));
    await flushMicrotasks();
    act(() => { void refreshed.result.current.recoverEventGeneration(); });
    await flushMicrotasks();

    expect(setters.setStoryText).not.toHaveBeenCalledWith('rejected old epoch story');
    expect(mockStreamGameEvent.mock.calls.at(-1)?.[2]).toEqual(expect.objectContaining({
      lastEventId: -1,
    }));
    refreshed.unmount();
  });

  it('invalidates before abort on unmount so late callbacks remain silent', async () => {
    const { result, unmount } = renderHook(() => useEventGenerator(params));
    act(() => { void result.current.generateEvent(); });
    await flushMicrotasks();
    const callbacks = mockStreamGameEvent.mock.calls[0][1];
    window.sessionStorage.setItem('story101:event-cursor:1', '31');
    window.sessionStorage.setItem('story101:event-story:1', 'current story');

    unmount();
    Object.values(setters).forEach((setter) => setter.mockClear());
    await act(async () => {
      callbacks.onStory?.('OLD story');
      callbacks.onStatus?.({ phase: 'OLD status' });
      callbacks.onEventId?.(32);
      callbacks.onComplete?.({ event_description: 'OLD complete', options: [{ text: 'OLD' }] });
      callbacks.onError?.(new Error('network error'));
      await Promise.resolve();
    });

    Object.values(setters).forEach((setter) => expect(setter).not.toHaveBeenCalled());
    expect(window.sessionStorage.getItem('story101:event-cursor:1')).toBe('31');
    expect(window.sessionStorage.getItem('story101:event-story:1')).toBe('current story');
  });
});
