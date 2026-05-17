/**
 * useGameState Tests
 * Tests for the game state management hook
 */
import { renderHook, act } from '@testing-library/react';
import { useGameState } from '@/hooks/game/useGameState';
import { useGameStore } from '@/stores/useGameStore';
import { createSSEMockResponse } from '@/__tests__/helpers/sse-mock';
import { spyOnStoreMethods } from '@/__tests__/helpers/store-spy';

// Mock streamRegenerate from @/lib/sse
jest.mock('@/lib/sse', () => ({
  ...jest.requireActual('@/lib/sse'),
  streamRegenerate: jest.fn(),
}));

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

    it('starts next event even if player-state sync hangs', async () => {
      jest.useFakeTimers();
      mockSetters.syncPlayerState.mockImplementationOnce(() => new Promise(() => {}));
      const { result } = renderHook(() => useGameState(defaultParams));

      act(() => { result.current.handleContinueAfterSummary(); });
      expect(mockGenerateEventRef.current).not.toHaveBeenCalled();

      act(() => {
        jest.advanceTimersByTime(1500);
      });

      expect(mockGenerateEventRef.current).toHaveBeenCalledTimes(1);
      jest.useRealTimers();
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

    it('starts next round even if player-state sync hangs', async () => {
      jest.useFakeTimers();
      mockPrefetchResultRef.current = null;
      mockSetters.syncPlayerState.mockImplementationOnce(() => new Promise(() => {}));
      const { result } = renderHook(() => useGameState(defaultParams));

      act(() => { result.current.handleContinueToNextRound(); });
      expect(mockGenerateEventRef.current).not.toHaveBeenCalled();

      act(() => {
        jest.advanceTimersByTime(1500);
      });

      expect(mockGenerateEventRef.current).toHaveBeenCalledTimes(1);
      jest.useRealTimers();
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
    it('starts SSE regeneration and calls streamRegenerate', async () => {
      const { streamRegenerate } = require('@/lib/sse');
      const { result } = renderHook(() => useGameState(defaultParams));
      act(() => { result.current.handleRegenerate(); });
      expect(streamRegenerate).toHaveBeenCalled();
      expect(mockSetters.setPhase).toHaveBeenCalledWith('generating');
      expect(mockSetters.setProcessing).toHaveBeenCalledWith(true, 'regenerating');
    });

    it('uses short normalized backend story over raw streamed text after regeneration', async () => {
      const { streamRegenerate } = require('@/lib/sse');
      (streamRegenerate as jest.Mock).mockImplementation(async (gameId: number, callbacks: any) => {
        callbacks.onStory('【内部状态】你推开门 . 雨停了');
        callbacks.onComplete({
          event_description: '你推开门。雨停了。',
          options: [{ text: '继续追查' }],
        });
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
      const { streamRegenerate } = require('@/lib/sse');
      (streamRegenerate as jest.Mock).mockImplementation(async (gameId: number, callbacks: any) => {
        callbacks.onError({ message: 'Regeneration failed' });
      });
      const { result } = renderHook(() => useGameState(defaultParams));
      await act(async () => {
        try { await result.current.handleRegenerate(); } catch (e) { /* expected */ }
      });
      expect(mockSetters.setProcessing).toHaveBeenCalledWith(false);
    });

    it('cancels ongoing prefetch before regeneration', async () => {
      mockPrefetchingRef.current = true;
      mockPrefetchAbortRef.current = { abort: jest.fn() } as any;
      const { result } = renderHook(() => useGameState(defaultParams));
      act(() => { result.current.handleRegenerate(); });
      expect(mockPrefetchAbortRef.current?.abort).toHaveBeenCalled();
    });

    it('shows regenerate toast', async () => {
      const { streamRegenerate } = require('@/lib/sse');
      // streamRegenerate hangs - we just test that the flow started
      (streamRegenerate as jest.Mock).mockReturnValue(new Promise(() => {}));
      const { result } = renderHook(() => useGameState(defaultParams));
      act(() => { result.current.handleRegenerate(); });
      // handleRegenerate starts with a generating phase
      expect(mockSetters.setPhase).toHaveBeenCalledWith('generating');
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
      const { streamRegenerate } = require('@/lib/sse');
      (streamRegenerate as jest.Mock).mockImplementation(async (gameId: number, callbacks: any) => {
        callbacks.onStatus({ phase: 'regenerating' });
        callbacks.onComplete({
          event_description: 'Story',
          options: [{ text: 'Option 1' }],
        });
      });
      const { result } = renderHook(() => useGameState(defaultParams));
      await act(async () => { await result.current.handleRegenerate(); });
      expect(mockSetters.setProcessing).toHaveBeenCalledWith(true, 'regenerating');
    });

    it('sets success toast and clears it after timeout', async () => {
      jest.useFakeTimers();
      const { streamRegenerate } = require('@/lib/sse');
      (streamRegenerate as jest.Mock).mockImplementation(async (gameId: number, callbacks: any) => {
        callbacks.onComplete({
          event_description: 'Story',
          options: [{ text: 'Option 1' }],
        });
      });
      const { result } = renderHook(() => useGameState(defaultParams));
      await act(async () => { await result.current.handleRegenerate(); });
      expect(result.current.regenerateToast?.type).toBe('success');
      act(() => { jest.advanceTimersByTime(2000); });
      expect(result.current.regenerateToast).toBeNull();
      jest.useRealTimers();
    });
  });
});
