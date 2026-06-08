/**
 * useEventGenerator Tests
 * Tests for the event generation hook
 */
import { renderHook, act, waitFor } from '@testing-library/react';
import { useEventGenerator } from '@/hooks/game/useEventGenerator';
import { useGameStore } from '@/stores/useGameStore';
import type { Phase, ConnectionStatus } from '@/hooks/game/usePhaseManager';
import { createSSEMockResponse } from '@/__tests__/helpers/sse-mock';

function createHangingSSEMockResponse(chunks: string[]): Response {
  let index = 0;
  const reader: ReadableStreamDefaultReader<Uint8Array> = {
    read(): Promise<ReadableStreamReadResult<Uint8Array>> {
      if (index < chunks.length) {
        const value = new TextEncoder().encode(chunks[index]);
        index += 1;
        return Promise.resolve({ done: false, value });
      }
      return new Promise(() => {});
    },
    cancel(): Promise<void> {
      return Promise.resolve();
    },
    releaseLock(): void {},
    get closed(): Promise<undefined> {
      return Promise.resolve(undefined);
    },
  };
  return {
    ok: true,
    status: 200,
    headers: new Headers({ 'content-type': 'text/event-stream' }),
    body: {
      locked: false,
      cancel: () => Promise.resolve(),
      getReader: () => reader,
    } as unknown as ReadableStream<Uint8Array>,
  } as Response;
}

function createBrokenSSEMockResponse(chunks: string[] = []): Response {
  let index = 0;
  const reader: ReadableStreamDefaultReader<Uint8Array> = {
    read(): Promise<ReadableStreamReadResult<Uint8Array>> {
      if (index < chunks.length) {
        const value = new TextEncoder().encode(chunks[index]);
        index += 1;
        return Promise.resolve({ done: false, value });
      }
      return Promise.reject(new TypeError('network error'));
    },
    cancel(): Promise<void> {
      return Promise.resolve();
    },
    releaseLock(): void {},
    get closed(): Promise<undefined> {
      return Promise.resolve(undefined);
    },
  };
  return {
    ok: true,
    status: 200,
    headers: new Headers({ 'content-type': 'text/event-stream' }),
    body: {
      locked: false,
      cancel: () => Promise.resolve(),
      getReader: () => reader,
    } as unknown as ReadableStream<Uint8Array>,
  } as Response;
}

function setupDefaultState() {
  useGameStore.setState({
    storyText: '',
    currentEvent: null,
    roundInfo: { current_round: 1 },
    enableSceneImage: true,
    generateRoundSceneImage: jest.fn().mockResolvedValue(undefined),
  } as never);
}

describe('useEventGenerator', () => {
  const mockPhaseRef: React.MutableRefObject<Phase> = { current: 'loading' as Phase };
  const mockAbortRef: React.MutableRefObject<AbortController | null> = { current: null };
  const mockGeneratingRef: React.MutableRefObject<boolean> = { current: false };
  const mockPollingRef: React.MutableRefObject<boolean> = { current: false };
  const mockPrefetchAbortRef: React.MutableRefObject<AbortController | null> = { current: null };
  const mockPrefetchResultRef: React.MutableRefObject<{ story: string; options: { text: string }[]; event: { story: string; options: { text: string }[] } | null } | null> = { current: null };
  const mockPrefetchingRef: React.MutableRefObject<boolean> = { current: false };
  const mockIsRetryingRef: React.MutableRefObject<boolean> = { current: false };

  const mockSetters = {
    setPhase: jest.fn(),
    setConnectionStatus: jest.fn(),
    setReconnectAttempt: jest.fn(),
    setProcessing: jest.fn(),
    setOptions: jest.fn(),
    setStoryText: jest.fn(),
    appendStoryText: jest.fn(),
    setCurrentEvent: jest.fn(),
    setGameOver: jest.fn(),
    setRoundSummary: jest.fn(),
    setIsPrefetching: jest.fn(),
  };

  const defaultParams = {
    gameId: 1,
    phaseRef: mockPhaseRef,
    setPhase: mockSetters.setPhase,
    setConnectionStatus: mockSetters.setConnectionStatus,
    setReconnectAttempt: mockSetters.setReconnectAttempt,
    setProcessing: mockSetters.setProcessing,
    setOptions: mockSetters.setOptions,
    setStoryText: mockSetters.setStoryText,
    appendStoryText: mockSetters.appendStoryText,
    setCurrentEvent: mockSetters.setCurrentEvent,
    setGameOver: mockSetters.setGameOver,
    setRoundSummary: mockSetters.setRoundSummary,
    isGameOver: false,
    setIsPrefetching: mockSetters.setIsPrefetching,
    abortRef: mockAbortRef,
    generatingRef: mockGeneratingRef,
    pollingRef: mockPollingRef,
    prefetchAbortRef: mockPrefetchAbortRef,
    prefetchResultRef: mockPrefetchResultRef,
    prefetchingRef: mockPrefetchingRef,
    isRetryingRef: mockIsRetryingRef,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockPhaseRef.current = 'loading' as Phase;
    mockGeneratingRef.current = false;
    mockPollingRef.current = false;
    mockPrefetchingRef.current = false;
    mockIsRetryingRef.current = false;
    mockAbortRef.current = null;
    mockPrefetchAbortRef.current = null;
    mockPrefetchResultRef.current = null;
    setupDefaultState();
  });

  describe('generateEvent', () => {
    it('does nothing when gameId is null', async () => {
      const { result } = renderHook(() =>
        useEventGenerator({ ...defaultParams, gameId: null })
      );
      await act(async () => { await result.current.generateEvent(); });
      expect(global.fetch).not.toHaveBeenCalledWith(
        expect.stringContaining('/event'),
        expect.anything()
      );
    });

    it('does nothing when already generating', async () => {
      mockGeneratingRef.current = true;
      const { result } = renderHook(() => useEventGenerator(defaultParams));
      const fetchCallsBefore = (global.fetch as jest.Mock).mock.calls.length;
      await act(async () => { await result.current.generateEvent(); });
      expect((global.fetch as jest.Mock).mock.calls.length).toBe(fetchCallsBefore);
    });

    it('recovers from a stuck generation by aborting stale work and forcing a new stream', async () => {
      const abort = jest.fn();
      mockAbortRef.current = { abort } as unknown as AbortController;
      mockGeneratingRef.current = true;
      mockPollingRef.current = true;
      mockIsRetryingRef.current = true;
      mockPhaseRef.current = 'generating' as Phase;

      (global.fetch as jest.Mock).mockResolvedValue(
        createSSEMockResponse([
          'data: {"type":"story","content":"恢复后的故事"}\n\n',
          'event: complete\ndata: {"event_description":"恢复后的故事","options":[{"text":"继续","effects":{}}]}\n\n',
        ])
      );

      const { result } = renderHook(() => useEventGenerator(defaultParams));

      await act(async () => { await result.current.recoverEventGeneration(); });

      expect(abort).toHaveBeenCalled();
      expect(mockPollingRef.current).toBe(false);
      expect(mockIsRetryingRef.current).toBe(false);
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/games/1/event'),
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
    });

    it('enters retryable error when event stream completes without options', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(
        createSSEMockResponse([
          'event: complete\ndata: {"event_description":"故事已生成但没有选项","options":[]}\n\n',
        ])
      );

      const { result } = renderHook(() => useEventGenerator(defaultParams));

      await act(async () => { await result.current.generateEvent(); });

      expect(mockSetters.setConnectionStatus).toHaveBeenCalledWith('error');
      expect(mockSetters.setPhase).toHaveBeenCalledWith('error');
      expect(mockGeneratingRef.current).toBe(false);
    });

    it('enters retryable error when event stream completes without story body', async () => {
      setupDefaultState({ storyText: '', currentEvent: null });
      (global.fetch as jest.Mock).mockResolvedValue(
        createSSEMockResponse([
          'event: complete\ndata: {"event_description":"","options":[{"text":"继续"}]}\n\n',
        ])
      );

      const { result } = renderHook(() => useEventGenerator(defaultParams));

      await act(async () => { await result.current.generateEvent(); });

      expect(mockSetters.setOptions).not.toHaveBeenCalledWith([{ text: '继续' }]);
      expect(mockSetters.setConnectionStatus).toHaveBeenCalledWith('error');
      expect(mockSetters.setPhase).toHaveBeenCalledWith('error');
      expect(mockGeneratingRef.current).toBe(false);
    });

    it('surfaces recovered partial story instead of staying in generation recovery forever', async () => {
      jest.useFakeTimers();
      const partialStory = '第十回 残月孤影探险途\n\n沈清越已经取到证据，但选项仍在生成。';
      const syncState = jest.fn().mockImplementation(async () => {
        useGameStore.setState({
          storyText: partialStory,
          currentEvent: {
            story: partialStory,
            options: [],
          },
        } as never);
      });
      useGameStore.setState({ syncState } as never);

      (global.fetch as jest.Mock).mockResolvedValue(
        createSSEMockResponse([
          'event: error\ndata: {"message":"Timeout waiting for event generation"}\n\n',
        ])
      );

      const { result } = renderHook(() => useEventGenerator(defaultParams));

      await act(async () => {
        void result.current.generateEvent();
      });

      await act(async () => {
        await jest.advanceTimersByTimeAsync(181000);
      });

      expect(syncState).toHaveBeenCalled();
      expect(mockSetters.setStoryText).toHaveBeenCalledWith(partialStory);
      expect(mockSetters.setCurrentEvent).toHaveBeenCalledWith({
        story: partialStory,
        options: [],
      });
      expect(mockSetters.setConnectionStatus).toHaveBeenCalledWith('error');
      expect(mockSetters.setPhase).toHaveBeenCalledWith('error');
      expect(mockGeneratingRef.current).toBe(false);

      jest.useRealTimers();
    });

    it('does not bubble stream rejection after event polling recovery starts', async () => {
      const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
      const recoveredStory = '轮次事件已经由后端保存。';
      const recoveredOptions = [{ text: '继续调查' }];
      const syncState = jest.fn().mockImplementation(async () => {
        useGameStore.setState({
          storyText: recoveredStory,
          currentEvent: {
            story: recoveredStory,
            options: recoveredOptions,
          },
        } as never);
      });
      useGameStore.setState({ syncState } as never);
      (global.fetch as jest.Mock).mockResolvedValue(createBrokenSSEMockResponse());

      const { result } = renderHook(() => useEventGenerator(defaultParams));

      await expect(act(async () => {
        await result.current.generateEvent();
      })).resolves.toBeUndefined();

      await waitFor(() => {
        expect(syncState).toHaveBeenCalled();
        expect(mockSetters.setOptions).toHaveBeenCalledWith(recoveredOptions);
        expect(mockSetters.setPhase).toHaveBeenCalledWith('options');
      });
      expect(mockSetters.setConnectionStatus).not.toHaveBeenCalledWith('error');
      expect(
        warnSpy.mock.calls.some((args) =>
          args.some((arg) => String(arg).includes('TypeError') || String(arg).includes('network error'))
        )
      ).toBe(false);
      warnSpy.mockRestore();
    });

    it('clears recovered partial story before retrying so new output is not appended to it', async () => {
      const partialStory = '半截故事：沈清越刚推开门，正文还没有选项。';
      setupDefaultState();
      useGameStore.setState({
        storyText: partialStory,
        currentEvent: {
          story: partialStory,
          options: [],
        },
      } as never);
      mockPhaseRef.current = 'error' as Phase;

      (global.fetch as jest.Mock).mockResolvedValue(
        createSSEMockResponse([
          'data: {"content":"重新生成的完整故事"}\n\n',
          'event: complete\ndata: {"event_description":"重新生成的完整故事","options":[{"text":"继续","effects":{}}]}\n\n',
        ])
      );

      const { result } = renderHook(() => useEventGenerator(defaultParams));

      await act(async () => { await result.current.generateEvent(); });

      expect(mockSetters.setStoryText).toHaveBeenCalledWith('');
      expect(mockSetters.appendStoryText).toHaveBeenCalledWith('重新生成的完整故事');
    });

    it('clears retrying guard when retry status stream never completes', async () => {
      jest.useFakeTimers();
      (global.fetch as jest.Mock).mockResolvedValue(
        createHangingSSEMockResponse([
          'event: status\ndata: {"phase":"retrying"}\n\n',
        ])
      );

      const { result, unmount } = renderHook(() => useEventGenerator(defaultParams));

      await act(async () => {
        void result.current.generateEvent();
        await Promise.resolve();
        await Promise.resolve();
      });

      expect(mockIsRetryingRef.current).toBe(true);

      await act(async () => {
        await jest.advanceTimersByTimeAsync(61000);
      });

      expect(mockIsRetryingRef.current).toBe(false);
      expect(mockGeneratingRef.current).toBe(false);
      expect(mockSetters.setConnectionStatus).toHaveBeenCalledWith('error');
      expect(mockSetters.setPhase).toHaveBeenCalledWith('error');

      unmount();
      jest.useRealTimers();
    });
  });
});
