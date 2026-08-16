/**
 * useEventGenerator Tests
 * Tests for the event generation hook
 */
import { renderHook, act, waitFor } from '@testing-library/react';
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
  const defaultSyncState = useGameStore.getState().syncState;
  const mockPhaseRef: React.MutableRefObject<Phase> = { current: 'loading' as Phase };
  const mockRunTokenRef: React.MutableRefObject<number> = { current: 0 };
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
    setTransport: jest.fn(),
    setLoadingOperation: jest.fn(),
    setLoadingIdentity: jest.fn(),
    setProcessing: jest.fn(),
    setOptions: jest.fn(),
    setStoryText: jest.fn(),
    appendStoryText: jest.fn(),
    setCurrentEvent: jest.fn(),
    setGameOver: jest.fn(),
    setRoundSummary: jest.fn(),
    setRegenerationFailure: jest.fn(),
    setIsPrefetching: jest.fn(),
  };

  const defaultParams = {
    gameId: 1,
    phaseRef: mockPhaseRef,
    setPhase: mockSetters.setPhase,
    setConnectionStatus: mockSetters.setConnectionStatus,
    setReconnectAttempt: mockSetters.setReconnectAttempt,
    setTransport: mockSetters.setTransport,
    setLoadingOperation: mockSetters.setLoadingOperation,
    setLoadingIdentity: mockSetters.setLoadingIdentity,
    setProcessing: mockSetters.setProcessing,
    setOptions: mockSetters.setOptions,
    setStoryText: mockSetters.setStoryText,
    appendStoryText: mockSetters.appendStoryText,
    setCurrentEvent: mockSetters.setCurrentEvent,
    setGameOver: mockSetters.setGameOver,
    setRoundSummary: mockSetters.setRoundSummary,
    setRegenerationFailure: mockSetters.setRegenerationFailure,
    isGameOver: false,
    setIsPrefetching: mockSetters.setIsPrefetching,
    runTokenRef: mockRunTokenRef,
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
    useGameStore.setState({ syncState: defaultSyncState } as never);
    mockPhaseRef.current = 'loading' as Phase;
    mockRunTokenRef.current = 0;
    mockGeneratingRef.current = false;
    mockPollingRef.current = false;
    mockPrefetchingRef.current = false;
    mockIsRetryingRef.current = false;
    mockAbortRef.current = null;
    mockPrefetchAbortRef.current = null;
    mockPrefetchResultRef.current = null;
    window.sessionStorage.clear();
    setupDefaultState();
  });

  describe('generateEvent', () => {
    it('preserves structured failure details for the player retry panel', async () => {
      (global.fetch as jest.Mock).mockResolvedValueOnce(
        createSSEMockResponse([
          'event: error\ndata: {"error":"角色一致性失败","code":"REQUIRED_CAST_MISSING","summary":"角色一致性失败","detail":"陈晓雨没有登场。","retryable":true,"attempts_used":3,"quality_level":"expert","operation_id":"op-live"}\n\n',
        ])
      );
      const { result } = renderHook(() => useEventGenerator(defaultParams));

      await act(async () => { await result.current.generateEvent(); });

      expect(mockSetters.setRegenerationFailure).toHaveBeenCalledWith(
        expect.objectContaining({
          code: 'REQUIRED_CAST_MISSING',
          detail: '陈晓雨没有登场。',
          operation_id: 'op-live',
        })
      );
    });

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

    it('recovers by resuming the current stream without clearing visible progress', async () => {
      const abort = jest.fn();
      mockAbortRef.current = { abort } as unknown as AbortController;
      mockGeneratingRef.current = true;
      mockPollingRef.current = true;
      mockPhaseRef.current = 'generating' as Phase;
      useGameStore.setState({
        storyText: '已经显示的故事',
        currentEvent: { story: '已经显示的故事', options: [] },
      } as never);

      (global.fetch as jest.Mock).mockResolvedValue(
        createSSEMockResponse([
          'id: 8\nevent: story\ndata: "后续片段"\n\n',
          'event: complete\ndata: {"event_description":"已经显示的故事后续片段","options":[{"text":"继续","effects":{}}]}\n\n',
        ])
      );

      const { result } = renderHook(() => useEventGenerator(defaultParams));

      await act(async () => { await result.current.recoverEventGeneration(); });

      expect(abort).toHaveBeenCalled();
      expect(mockPollingRef.current).toBe(false);
      expect(mockIsRetryingRef.current).toBe(false);
      expect(mockSetters.setStoryText).not.toHaveBeenCalledWith('');
      expect(mockSetters.setOptions).not.toHaveBeenCalledWith([]);
      expect(global.fetch).toHaveBeenCalledTimes(1);
    });

    it('restores the saved SSE cursor when recovery follows a page refresh', async () => {
      window.sessionStorage.setItem('story101:event-cursor:1', '4');
      window.sessionStorage.setItem('story101:event-story:1', '刷新前已经显示的故事');
      mockGeneratingRef.current = true;
      mockPhaseRef.current = 'generating' as Phase;
      (global.fetch as jest.Mock).mockResolvedValue(
        createSSEMockResponse([
          'id: 5\nevent: story\ndata: "刷新后的片段"\n\n',
          'event: complete\ndata: {"event_description":"完整故事","options":[{"text":"继续","effects":{}}]}\n\n',
        ])
      );

      const { result } = renderHook(() => useEventGenerator(defaultParams));

      await waitFor(() => {
        expect(mockSetters.setStoryText).toHaveBeenCalledWith('刷新前已经显示的故事');
      });

      await act(async () => { await result.current.recoverEventGeneration(); });

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/games/1/event',
        expect.objectContaining({
          headers: { 'Last-Event-ID': '4' },
          signal: expect.any(AbortSignal),
        })
      );
    });

    it('replays from the beginning when a saved cursor has no matching story snapshot', async () => {
      window.sessionStorage.setItem('story101:event-cursor:1', '4');
      mockGeneratingRef.current = true;
      mockPhaseRef.current = 'generating' as Phase;
      (global.fetch as jest.Mock).mockResolvedValue(
        createSSEMockResponse([
          'id: 0\nevent: story\ndata: "完整重放"\n\n',
          'event: complete\ndata: {"event_description":"完整重放","options":[{"text":"继续","effects":{}}]}\n\n',
        ])
      );

      const { result } = renderHook(() => useEventGenerator(defaultParams));

      await act(async () => { await result.current.recoverEventGeneration(); });

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/games/1/event',
        expect.objectContaining({ headers: { 'Last-Event-ID': '-1' } })
      );
      expect(window.sessionStorage.getItem('story101:event-cursor:1')).toBeNull();
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

  });
});
