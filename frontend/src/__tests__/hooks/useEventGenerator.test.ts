/**
 * useEventGenerator Tests
 * Tests for the event generation hook
 */
import { renderHook, act } from '@testing-library/react';
import { useEventGenerator } from '@/hooks/game/useEventGenerator';
import { useGameStore } from '@/stores/useGameStore';
import type { Phase, ConnectionStatus } from '@/hooks/game/usePhaseManager';
import { createSSEMockResponse } from '@/__tests__/helpers/sse-mock';

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
  });
});
