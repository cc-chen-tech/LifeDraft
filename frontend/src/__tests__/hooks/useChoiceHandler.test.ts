/**
 * useChoiceHandler Tests
 * Tests for the choice handling hook
 */
import { renderHook, act, waitFor } from '@testing-library/react';
import { useChoiceHandler } from '@/hooks/game/useChoiceHandler';
import { useGameStore } from '@/stores/useGameStore';
import type { Phase, ConnectionStatus } from '@/hooks/game/usePhaseManager';
import { createSSEMockResponse } from '@/__tests__/helpers/sse-mock';
import { jsonResponse } from '@/__tests__/helpers/fetch';

/** Create a fresh SSE response for streamChoice calls */
function makeChoiceResponse() {
  return createSSEMockResponse([
    'event: story\ndata: Choice result story\n\n',
    'event: complete\ndata: {"event_description":"Choice result story","options":[{"text":"Next Option"}]}\n\n',
  ]);
}

function makeChoiceCompleteOnlyResponse() {
  return createSSEMockResponse([
    'event: complete\ndata: {"event_description":"Choice result story from complete","options":[{"text":"Next Option"}]}\n\n',
  ]);
}

function makeBrokenChoiceResponse() {
  const reader: ReadableStreamDefaultReader<Uint8Array> = {
    read(): Promise<ReadableStreamReadResult<Uint8Array>> {
      return Promise.reject(new TypeError('network error'));
    },
    cancel(): Promise<void> {
      return Promise.resolve();
    },
    releaseLock(): void {
      // no-op
    },
    get closed(): Promise<undefined> {
      return Promise.resolve(undefined);
    },
  };

  return {
    ok: true,
    status: 200,
    headers: new Headers({ 'content-type': 'text/event-stream' }),
    body: {
      getReader: () => reader,
    } as unknown as ReadableStream<Uint8Array>,
  } as Response;
}

function setupDefaultState() {
  useGameStore.setState({
    progress: { week: 1 },
    storyText: '',
    currentEvent: null,
    roundInfo: { current_round: 1 },
    enableSceneImage: true,
    generateRoundSceneImage: jest.fn().mockResolvedValue(undefined),
  } as never);
}

describe('useChoiceHandler', () => {
  const mockAbortRef: React.MutableRefObject<AbortController | null> = { current: null };
  const mockGeneratingRef: React.MutableRefObject<boolean> = { current: false };
  const mockRunTokenRef: React.MutableRefObject<number> = { current: 0 };

  const mockSetters = {
    setPhase: jest.fn(),
    setConnectionStatus: jest.fn(),
    setReconnectAttempt: jest.fn(),
    setTransport: jest.fn(),
    setLoadingIdentity: jest.fn(),
    setProcessing: jest.fn(),
    appendStoryText: jest.fn(),
    setCurrentEvent: jest.fn(),
    setGameOver: jest.fn(),
    setSummaryText: jest.fn(),
    setRoundSummary: jest.fn(),
    setOptions: jest.fn(),
    setStoryText: jest.fn(),
  };

  const defaultParams = {
    gameId: 1,
    abortRef: mockAbortRef,
    generatingRef: mockGeneratingRef,
    runTokenRef: mockRunTokenRef,
    setPhase: mockSetters.setPhase,
    setConnectionStatus: mockSetters.setConnectionStatus,
    setReconnectAttempt: mockSetters.setReconnectAttempt,
    setTransport: mockSetters.setTransport,
    setLoadingIdentity: mockSetters.setLoadingIdentity,
    setProcessing: mockSetters.setProcessing,
    appendStoryText: mockSetters.appendStoryText,
    setCurrentEvent: mockSetters.setCurrentEvent,
    setGameOver: mockSetters.setGameOver,
    setSummaryText: mockSetters.setSummaryText,
    setRoundSummary: mockSetters.setRoundSummary,
    setOptions: mockSetters.setOptions,
    setStoryText: mockSetters.setStoryText,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    (global.fetch as jest.Mock).mockReset();
    mockGeneratingRef.current = false;
    mockAbortRef.current = null;
    mockRunTokenRef.current = 0;
    setupDefaultState();
  });

  describe('handleChoice', () => {
    it('does nothing when gameId is null', async () => {
      const { result } = renderHook(() =>
        useChoiceHandler({ ...defaultParams, gameId: null })
      );
      await act(async () => { await result.current.handleChoice(0); });
      expect(global.fetch).not.toHaveBeenCalledWith(
        expect.stringContaining('/choice'),
        expect.anything()
      );
    });

    it('sets phase to choosing when handling choice', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(makeChoiceResponse());
      const { result } = renderHook(() => useChoiceHandler(defaultParams));
      await act(async () => { await result.current.handleChoice(0); });
      expect(mockSetters.setPhase).toHaveBeenCalledWith('choosing');
    });

    it('uses complete event story when the choice stream has no story chunks', async () => {
      useGameStore.setState({
        storyText: 'Base story before choice.',
        currentEvent: { options: [{ text: 'Option 1' }] },
      } as never);
      (global.fetch as jest.Mock).mockResolvedValue(makeChoiceCompleteOnlyResponse());

      const { result } = renderHook(() => useChoiceHandler(defaultParams));

      await act(async () => { await result.current.handleChoice(0); });

      await waitFor(() => {
        expect(mockSetters.setPhase).toHaveBeenCalledWith('result');
      });
      expect(mockSetters.setStoryText).toHaveBeenCalledWith(
        expect.stringContaining('Choice result story from complete')
      );
    });

    it('aborts previous request when handling new choice', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(makeChoiceResponse());
      const mockAbort = jest.fn();
      mockAbortRef.current = { abort: mockAbort, signal: {} as AbortSignal };
      const { result } = renderHook(() => useChoiceHandler(defaultParams));
      await act(async () => { await result.current.handleChoice(0); });
      expect(mockAbort).toHaveBeenCalled();
    });

    it('does not surface stream rejections after onError fallback handling starts', async () => {
      const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
      useGameStore.setState({
        currentEvent: { options: [{ text: 'Option 1' }] },
      } as never);
      (global.fetch as jest.Mock)
        .mockResolvedValueOnce(makeBrokenChoiceResponse())
        .mockResolvedValue(jsonResponse({
          current_event: null,
          player_state: {
            round_history: [{ choice: 'Option 1', story_continuation: '同步恢复后的选择结果' }],
            resume_view: { phase: 'result', story_text: '同步恢复后的选择结果' },
          },
          progress: { week: 1, total_weeks: 52 },
        }));

      const { result } = renderHook(() => useChoiceHandler(defaultParams));

      await expect(act(async () => {
        await result.current.handleChoice(0);
      })).resolves.toBeUndefined();
      await waitFor(() => {
        expect(mockSetters.setPhase).toHaveBeenCalledWith('result');
      });
      expect(
        warnSpy.mock.calls.some((args) =>
          args.some((arg) => String(arg).includes('TypeError') || String(arg).includes('network error'))
        )
      ).toBe(false);
      warnSpy.mockRestore();
    });

    it('does not surface custom-choice stream rejections after fallback handling starts', async () => {
      const warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});
      (global.fetch as jest.Mock)
        .mockResolvedValueOnce(makeBrokenChoiceResponse())
        .mockResolvedValue(jsonResponse({
          current_event: null,
          player_state: {
            round_history: [{ choice: '继续调查异常数据', story_continuation: '同步恢复后的自定义选择结果' }],
            resume_view: { phase: 'result', story_text: '同步恢复后的自定义选择结果' },
          },
          progress: { week: 1, total_weeks: 52 },
        }));

      const { result } = renderHook(() => useChoiceHandler(defaultParams));

      await expect(act(async () => {
        await result.current.handleCustomChoice('继续调查异常数据');
      })).resolves.toBeUndefined();
      await waitFor(() => {
        expect(mockSetters.setPhase).toHaveBeenCalledWith('result');
      });
      expect(
        warnSpy.mock.calls.some((args) =>
          args.some((arg) => String(arg).includes('TypeError') || String(arg).includes('network error'))
        )
      ).toBe(false);
      warnSpy.mockRestore();
    });

    it('recovers through fallback without starting a duplicate choice worker', async () => {
      useGameStore.setState({
        storyText: '原始故事',
        currentEvent: { options: [{ text: 'Option 1' }] },
      } as never);
      (global.fetch as jest.Mock)
        .mockResolvedValueOnce(makeBrokenChoiceResponse())
        .mockResolvedValueOnce(jsonResponse({
          current_event: null,
          player_state: {
            round_history: [{ choice: 'Option 1', story_continuation: '同步恢复后的选择结果' }],
            resume_view: { phase: 'result', story_text: '原始故事\n\n同步恢复后的选择结果' },
          },
          progress: { week: 1, total_weeks: 52 },
        }));

      const { result } = renderHook(() => useChoiceHandler(defaultParams));

      await act(async () => {
        await result.current.handleChoice(0);
      });

      expect((global.fetch as jest.Mock).mock.calls.filter(([url]) =>
        String(url).includes('/choice-sync')
      )).toHaveLength(0);
      expect(
        (global.fetch as jest.Mock).mock.calls.filter(([url]) =>
          String(url).endsWith('/choice')
        )
      ).toHaveLength(1);
      expect(mockSetters.setStoryText).toHaveBeenCalledWith(
        expect.stringContaining('同步恢复后的选择结果')
      );
      expect(mockSetters.setPhase).toHaveBeenCalledWith('result');
    });
  });
});
