/**
 * useGameState Tests
 * Tests for the game state management hook
 */
import { renderHook, act } from '@testing-library/react';
import { useGameState } from '@/hooks/game/useGameState';
import { useGameStore } from '@/stores/useGameStore';
import { createSSEMockResponse } from '@/__tests__/helpers/sse-mock';
import { spyOnStoreMethods } from '@/__tests__/helpers/store-spy';

const STORE_METHODS = ['saveGame', 'syncPlayerState', 'generateSummary'] as const;

type StoreSpy = ReturnType<typeof spyOnStoreMethods<typeof useGameStore, (typeof STORE_METHODS)[number]>>;

function setupDefaultState() {
  useGameStore.setState({
    storyText: 'Frontend story',
    gameId: 1,
  } as never);
}

describe('useGameState', () => {
  let storeSpy: StoreSpy;
  const mockGeneratingRef = { current: false };
  const mockPrefetchAbortRef = { current: null as AbortController | null };
  const mockPrefetchResultRef = { current: null as { story: string; options: any[]; event: any } | null };
  const mockPrefetchingRef = { current: false };
  const mockGenerateEventRef = { current: jest.fn() };

  const mockSetters = {
    setPhase: jest.fn(),
    setStoryText: jest.fn(),
    appendStoryText: jest.fn(),
    setCurrentEvent: jest.fn(),
    setOptions: jest.fn(),
    setProcessing: jest.fn(),
    setIsPrefetching: jest.fn(),
    syncPlayerState: jest.fn().mockResolvedValue(undefined),
  };

  const defaultParams = {
    gameId: 1,
    isGameOver: false,
    setPhase: mockSetters.setPhase,
    setStoryText: mockSetters.setStoryText,
    appendStoryText: mockSetters.appendStoryText,
    setCurrentEvent: mockSetters.setCurrentEvent,
    setOptions: mockSetters.setOptions,
    setProcessing: mockSetters.setProcessing,
    generatingRef: mockGeneratingRef,
    prefetchAbortRef: mockPrefetchAbortRef,
    prefetchResultRef: mockPrefetchResultRef,
    prefetchingRef: mockPrefetchingRef,
    setIsPrefetching: mockSetters.setIsPrefetching,
    generateEventRef: mockGenerateEventRef,
    syncPlayerState: mockSetters.syncPlayerState,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockGeneratingRef.current = false;
    mockPrefetchingRef.current = false;
    setupDefaultState();
    storeSpy = spyOnStoreMethods(useGameStore, STORE_METHODS);
  });

  afterEach(() => {
    storeSpy.restore();
  });

  describe('handleSave', () => {
    it('saves game successfully', async () => {
      const { result } = renderHook(() => useGameState(defaultParams));
      await act(async () => {
        await result.current.handleSave();
      });
      expect(storeSpy.spies.saveGame).toHaveBeenCalled();
    });

    it('handles save failure', async () => {
      storeSpy.spies.saveGame.mockRejectedValueOnce(new Error('Save failed'));
      const { result } = renderHook(() => useGameState(defaultParams));
      await act(async () => {
        await result.current.handleSave();
      });
    });
  });

  describe('handleContinueAfterSummary', () => {
    it('clears summary and sets phase to loading when not game over', async () => {
      const { result } = renderHook(() => useGameState(defaultParams));
      act(() => { result.current.handleContinueAfterSummary(); });
      expect(mockSetters.setCurrentEvent).toHaveBeenCalledWith(null);
    });

    it('sets phase to ending when game over', async () => {
      const { result } = renderHook(() =>
        useGameState({ ...defaultParams, isGameOver: true })
      );
      act(() => { result.current.handleContinueAfterSummary(); });
      expect(mockSetters.setPhase).toHaveBeenCalledWith('ending');
    });
  });

  describe('state management', () => {
    it('manages summary text', async () => {
      const { result } = renderHook(() => useGameState(defaultParams));
      act(() => { result.current.setSummaryText('Test summary'); });
      expect(result.current.summaryText).toBe('Test summary');
    });

    it('manages round summary', async () => {
      const { result } = renderHook(() => useGameState(defaultParams));
      act(() => { result.current.setRoundSummary('Round summary'); });
      expect(result.current.roundSummary).toBe('Round summary');
    });

    it('manages ending data', async () => {
      const { result } = renderHook(() => useGameState(defaultParams));
      expect(result.current.endingData).toBeDefined();
    });
  });

  describe('handleContinueToNextRound', () => {
    it('uses prefetched result when available', async () => {
      mockPrefetchResultRef.current = {
        story: 'Prefetched story',
        options: [{ text: 'Option 1' }, { text: 'Option 2' }],
        event: { story: 'Prefetched story', options: [{ text: 'Option 1' }] },
      };
      const { result } = renderHook(() => useGameState(defaultParams));
      act(() => { result.current.handleContinueToNextRound(); });
      expect(mockSetters.setStoryText).toHaveBeenCalledWith('Prefetched story');
      expect(mockSetters.setOptions).toHaveBeenCalled();
      expect(mockSetters.setPhase).toHaveBeenCalledWith('options');
      expect(mockSetters.syncPlayerState).not.toHaveBeenCalled();
    });

    it('generates normally when no prefetch result', async () => {
      mockPrefetchResultRef.current = null;
      const { result } = renderHook(() => useGameState(defaultParams));
      act(() => { result.current.handleContinueToNextRound(); });
      expect(mockSetters.setCurrentEvent).toHaveBeenCalledWith(null);
      expect(mockSetters.setStoryText).toHaveBeenCalledWith('');
      expect(mockSetters.setPhase).toHaveBeenCalledWith('loading');
    });

    it('cancels ongoing prefetch', async () => {
      mockPrefetchingRef.current = true;
      mockPrefetchAbortRef.current = { abort: jest.fn() } as any;
      mockPrefetchResultRef.current = null;
      const { result } = renderHook(() => useGameState(defaultParams));
      act(() => { result.current.handleContinueToNextRound(); });
      expect(mockPrefetchAbortRef.current?.abort).toHaveBeenCalled();
    });
  });

  describe('handleRegenerate', () => {
    it('starts SSE regeneration', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(createSSEMockResponse([
        'event: story\ndata: New story text\n\n',
        'event: complete\ndata: {"event_description":"Complete story","options":[{"text":"Option 1"},{"text":"Option 2"}]}\n\n',
      ]));

      const { result } = renderHook(() => useGameState(defaultParams));
      await act(async () => { await result.current.handleRegenerate(); });
      expect(mockSetters.appendStoryText).toHaveBeenCalledWith('New story text');
      expect(mockSetters.setPhase).toHaveBeenCalledWith('generating');
    });

    it('uses short normalized backend story over raw streamed text after regeneration', async () => {
      const mockStreamRegenerate = streamRegenerate as jest.Mock;
      mockStreamRegenerate.mockImplementation(async (gameId: number, callbacks: any) => {
        callbacks.onStory('【内部状态】你推开门 . 雨停了');
        callbacks.onComplete({
          event_description: '你推开门。雨停了。',
          options: [{ text: '继续追查' }],
        });
      });

      (useGameStore.getState as jest.Mock).mockReturnValue({
        saveGame: mockSaveGame,
        syncPlayerState: mockSyncPlayerState,
        generateSummary: mockGenerateSummary,
        storyText: '【内部状态】你推开门 . 雨停了',
      });

      const { result } = renderHook(() => useGameState(defaultParams));

      await act(async () => {
        await result.current.handleRegenerate();
      });

      expect(mockSetters.setStoryText).toHaveBeenCalledWith('你推开门。雨停了。');
      expect(mockSetters.setCurrentEvent).toHaveBeenCalledWith({
        story: '你推开门。雨停了。',
        options: [{ text: '继续追查' }],
      });
    });

    it('handles regeneration error', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(createSSEMockResponse([
        'event: error\ndata: {"error":"Regeneration failed"}\n\n',
      ]));
      const { result } = renderHook(() => useGameState(defaultParams));
      await act(async () => {
        try { await result.current.handleRegenerate(); } catch (e) { /* expected */ }
      });
      expect(mockSetters.setPhase).toHaveBeenCalledWith('error');
      expect(mockSetters.setProcessing).toHaveBeenCalledWith(false);
    });

    it('cancels ongoing prefetch before regeneration', async () => {
      mockPrefetchingRef.current = true;
      mockPrefetchAbortRef.current = { abort: jest.fn() } as any;
      (global.fetch as jest.Mock).mockResolvedValue(createSSEMockResponse([
        'event: complete\ndata: {"options":[{"text":"Option 1"}]}\n\n',
      ]));
      const { result } = renderHook(() => useGameState(defaultParams));
      await act(async () => { await result.current.handleRegenerate(); });
      expect(mockPrefetchAbortRef.current?.abort).toHaveBeenCalled();
    });

    it('shows loading toast during regeneration', async () => {
      // Never-resolving fetch so streamRegenerate hangs
      (global.fetch as jest.Mock).mockReturnValue(new Promise(() => {}));
      const { result } = renderHook(() => useGameState(defaultParams));
      act(() => { result.current.handleRegenerate(); });
      expect(result.current.regenerateToast?.type).toBe('loading');
    });
  });

  describe('regenerateToast', () => {
    it('can be set directly', async () => {
      const { result } = renderHook(() => useGameState(defaultParams));
      await act(async () => { result.current.setRegenerateToast({ type: 'success', message: 'Success!' }); });
      expect(result.current.regenerateToast).toEqual({ type: 'success', message: 'Success!' });
    });

    it('can be cleared', async () => {
      const { result } = renderHook(() => useGameState(defaultParams));
      await act(async () => { result.current.setRegenerateToast({ type: 'error', message: 'Error!' }); });
      await act(async () => { result.current.setRegenerateToast(null); });
      expect(result.current.regenerateToast).toBeNull();
    });
  });

  describe('handleSave edge cases', () => {
    it('sets success toast on save', async () => {
      storeSpy.spies.saveGame.mockResolvedValue(undefined);
      const { result } = renderHook(() => useGameState(defaultParams));
      await act(async () => { await result.current.handleSave(); });
      expect(storeSpy.spies.saveGame).toHaveBeenCalled();
    });

    it('sets error toast on save failure', async () => {
      storeSpy.spies.saveGame.mockRejectedValueOnce(new Error('Save failed'));
      const { result } = renderHook(() => useGameState(defaultParams));
      await act(async () => { await result.current.handleSave(); });
      expect(storeSpy.spies.saveGame).toHaveBeenCalled();
    });
  });

  describe('handleRegenerate status callback', () => {
    it('calls setProcessing with status phase', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(createSSEMockResponse([
        'event: status\ndata: {"phase":"generating"}\n\n',
        'event: complete\ndata: {"event_description":"Story","options":[{"text":"Option 1"}]}\n\n',
      ]));
      const { result } = renderHook(() => useGameState(defaultParams));
      await act(async () => { await result.current.handleRegenerate(); });
      expect(mockSetters.setProcessing).toHaveBeenCalledWith(true, 'generating');
    });

    it('sets success toast and clears it after timeout', async () => {
      jest.useFakeTimers();
      (global.fetch as jest.Mock).mockResolvedValue(createSSEMockResponse([
        'event: complete\ndata: {"event_description":"Story","options":[{"text":"Option 1"}]}\n\n',
      ]));
      const { result } = renderHook(() => useGameState(defaultParams));
      await act(async () => { await result.current.handleRegenerate(); });
      expect(result.current.regenerateToast?.type).toBe('success');
      act(() => { jest.advanceTimersByTime(2000); });
      expect(result.current.regenerateToast).toBeNull();
      jest.useRealTimers();
    });
  });
});
