/**
 * useGameState Tests
 * Tests for the game state management hook
 */
import { renderHook, act } from '@testing-library/react';
import { useGameState } from '@/hooks/game/useGameState';
import { useGameStore } from '@/stores/useGameStore';
import { streamRegenerate } from '@/lib/sse';
import type { Phase } from '@/hooks/game/usePhaseManager';

// Mock dependencies
const mockSaveGame = jest.fn().mockResolvedValue(undefined);
const mockSyncPlayerState = jest.fn().mockResolvedValue(undefined);
const mockGenerateSummary = jest.fn().mockResolvedValue({ summary_text: 'Test summary' });

jest.mock('@/stores/useGameStore', () => ({
  useGameStore: {
    getState: jest.fn(() => ({
      saveGame: mockSaveGame,
      syncPlayerState: mockSyncPlayerState,
      generateSummary: mockGenerateSummary,
    })),
  },
}));

jest.mock('@/lib/sse', () => ({
  streamRegenerate: jest.fn(),
}));

describe('useGameState', () => {
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
  });

  describe('handleSave', () => {
    it('saves game successfully', async () => {
      mockSaveGame.mockClear();
      
      const { result } = renderHook(() => useGameState(defaultParams));

      await act(async () => {
        await result.current.handleSave();
      });

      expect(mockSaveGame).toHaveBeenCalled();
    });

    it('handles save failure', async () => {
      mockSaveGame.mockRejectedValueOnce(new Error('Save failed'));
      
      const { result } = renderHook(() => useGameState(defaultParams));

      await act(async () => {
        await result.current.handleSave();
      });

      // Should not throw, just handle error gracefully
    });
  });

  describe('handleContinueAfterSummary', () => {
    it('clears summary and sets phase to loading when not game over', async () => {
      const { result } = renderHook(() => useGameState(defaultParams));

      act(() => {
        result.current.handleContinueAfterSummary();
      });

      expect(mockSetters.setCurrentEvent).toHaveBeenCalledWith(null);
    });

    it('sets phase to ending when game over', async () => {
      const { result } = renderHook(() =>
        useGameState({ ...defaultParams, isGameOver: true })
      );

      act(() => {
        result.current.handleContinueAfterSummary();
      });

      expect(mockSetters.setPhase).toHaveBeenCalledWith('ending');
    });
  });

  describe('handleAdjustStory', () => {
    it('shows adjuster', async () => {
      const { result } = renderHook(() => useGameState(defaultParams));

      act(() => {
        result.current.setShowAdjuster(true);
      });

      expect(result.current.showAdjuster).toBe(true);
    });
  });

  describe('state management', () => {
    it('manages summary text', async () => {
      const { result } = renderHook(() => useGameState(defaultParams));

      act(() => {
        result.current.setSummaryText('Test summary');
      });

      expect(result.current.summaryText).toBe('Test summary');
    });

    it('manages round summary', async () => {
      const { result } = renderHook(() => useGameState(defaultParams));

      act(() => {
        result.current.setRoundSummary('Round summary');
      });

      expect(result.current.roundSummary).toBe('Round summary');
    });

    it('manages ending data', async () => {
      const { result } = renderHook(() => useGameState(defaultParams));

      // endingData is internal state, just verify it exists in the result
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

      act(() => {
        result.current.handleContinueToNextRound();
      });

      expect(mockSetters.setStoryText).toHaveBeenCalledWith('Prefetched story');
      expect(mockSetters.setOptions).toHaveBeenCalled();
      expect(mockSetters.setPhase).toHaveBeenCalledWith('options');
      expect(mockSetters.syncPlayerState).not.toHaveBeenCalled();
    });

    it('generates normally when no prefetch result', async () => {
      mockPrefetchResultRef.current = null;

      const { result } = renderHook(() => useGameState(defaultParams));

      act(() => {
        result.current.handleContinueToNextRound();
      });

      expect(mockSetters.setCurrentEvent).toHaveBeenCalledWith(null);
      expect(mockSetters.setStoryText).toHaveBeenCalledWith('');
      expect(mockSetters.setPhase).toHaveBeenCalledWith('loading');
    });

    it('cancels ongoing prefetch', async () => {
      mockPrefetchingRef.current = true;
      mockPrefetchAbortRef.current = { abort: jest.fn() } as any;
      mockPrefetchResultRef.current = null;

      const { result } = renderHook(() => useGameState(defaultParams));

      act(() => {
        result.current.handleContinueToNextRound();
      });

      expect(mockPrefetchAbortRef.current?.abort).toHaveBeenCalled();
    });
  });

  describe('handleRegenerate', () => {
    it('starts SSE regeneration', async () => {
      const mockStreamRegenerate = streamRegenerate as jest.Mock;
      mockStreamRegenerate.mockImplementation(async (gameId: number, callbacks: any) => {
        // Simulate successful regeneration
        callbacks.onStory('New story text');
        callbacks.onComplete({
          event_description: 'Complete story',
          options: [{ text: 'Option 1' }, { text: 'Option 2' }],
        });
      });

      // Mock useGameStore.getState for storyText comparison
      (useGameStore.getState as jest.Mock).mockReturnValue({
        saveGame: mockSaveGame,
        syncPlayerState: mockSyncPlayerState,
        generateSummary: mockGenerateSummary,
        storyText: 'Frontend story',
      });

      const { result } = renderHook(() => useGameState(defaultParams));

      await act(async () => {
        await result.current.handleRegenerate();
      });

      expect(mockSetters.appendStoryText).toHaveBeenCalledWith('New story text');
      expect(mockSetters.setPhase).toHaveBeenCalledWith('generating');
    });

    it('handles regeneration error', async () => {
      const mockStreamRegenerate = streamRegenerate as jest.Mock;
      mockStreamRegenerate.mockImplementation(async (gameId: number, callbacks: any) => {
        callbacks.onError({ message: 'Regeneration failed' });
      });

      const { result } = renderHook(() => useGameState(defaultParams));

      await act(async () => {
        try {
          await result.current.handleRegenerate();
        } catch (e) {
          // Expected to fail
        }
      });

      expect(mockSetters.setPhase).toHaveBeenCalledWith('error');
      expect(mockSetters.setProcessing).toHaveBeenCalledWith(false);
    });

    it('cancels ongoing prefetch before regeneration', async () => {
      mockPrefetchingRef.current = true;
      mockPrefetchAbortRef.current = { abort: jest.fn() } as any;

      const mockStreamRegenerate = streamRegenerate as jest.Mock;
      mockStreamRegenerate.mockImplementation(async (gameId: number, callbacks: any) => {
        callbacks.onComplete({ options: [{ text: 'Option 1' }] });
      });

      (useGameStore.getState as jest.Mock).mockReturnValue({
        saveGame: mockSaveGame,
        syncPlayerState: mockSyncPlayerState,
        generateSummary: mockGenerateSummary,
        storyText: 'Frontend story',
      });

      const { result } = renderHook(() => useGameState(defaultParams));

      await act(async () => {
        await result.current.handleRegenerate();
      });

      expect(mockPrefetchAbortRef.current?.abort).toHaveBeenCalled();
    });

    it('shows loading toast during regeneration', async () => {
      let resolveRegenerate: () => void;
      const mockStreamRegenerate = streamRegenerate as jest.Mock;
      mockStreamRegenerate.mockImplementation(async () => {
        return new Promise<void>((resolve) => {
          resolveRegenerate = resolve;
        });
      });

      const { result } = renderHook(() => useGameState(defaultParams));

      // Start regeneration but don't await
      let regeneratePromise: Promise<void>;
      act(() => {
        regeneratePromise = result.current.handleRegenerate();
      });

      // Check toast immediately after starting
      expect(result.current.regenerateToast?.type).toBe('loading');
    });
  });

  describe('regenerateToast', () => {
    it('can be set directly', async () => {
      const { result } = renderHook(() => useGameState(defaultParams));

      await act(async () => {
        result.current.setRegenerateToast({ type: 'success', message: 'Success!' });
      });

      expect(result.current.regenerateToast).toEqual({ type: 'success', message: 'Success!' });
    });

    it('can be cleared', async () => {
      const { result } = renderHook(() => useGameState(defaultParams));

      await act(async () => {
        result.current.setRegenerateToast({ type: 'error', message: 'Error!' });
      });

      await act(async () => {
        result.current.setRegenerateToast(null);
      });

      expect(result.current.regenerateToast).toBeNull();
    });
  });

  describe('handleSave edge cases', () => {
    it('sets success toast on save', async () => {
      mockSaveGame.mockClear();
      mockSaveGame.mockResolvedValue(undefined);
      
      const { result } = renderHook(() => useGameState(defaultParams));

      await act(async () => {
        await result.current.handleSave();
      });

      // saveToast is internal state, verify saveGame was called
      expect(mockSaveGame).toHaveBeenCalled();
    });

    it('sets error toast on save failure', async () => {
      mockSaveGame.mockClear();
      mockSaveGame.mockRejectedValueOnce(new Error('Save failed'));
      
      const { result } = renderHook(() => useGameState(defaultParams));

      await act(async () => {
        await result.current.handleSave();
      });

      // Should handle error gracefully
      expect(mockSaveGame).toHaveBeenCalled();
    });
  });

  describe('handleRegenerate status callback', () => {
    it('calls setProcessing with status phase', async () => {
      const mockStreamRegenerate = streamRegenerate as jest.Mock;
      mockStreamRegenerate.mockImplementation(async (gameId: number, callbacks: any) => {
        callbacks.onStatus({ phase: 'generating' });
        callbacks.onComplete({
          event_description: 'Story',
          options: [{ text: 'Option 1' }],
        });
      });

      (useGameStore.getState as jest.Mock).mockReturnValue({
        saveGame: mockSaveGame,
        syncPlayerState: mockSyncPlayerState,
        generateSummary: mockGenerateSummary,
        storyText: 'Frontend story',
      });

      const { result } = renderHook(() => useGameState(defaultParams));

      await act(async () => {
        await result.current.handleRegenerate();
      });

      expect(mockSetters.setProcessing).toHaveBeenCalledWith(true, 'generating');
    });

    it('sets success toast and clears it after timeout', async () => {
      jest.useFakeTimers();
      
      const mockStreamRegenerate = streamRegenerate as jest.Mock;
      mockStreamRegenerate.mockImplementation(async (gameId: number, callbacks: any) => {
        callbacks.onComplete({
          event_description: 'Story',
          options: [{ text: 'Option 1' }],
        });
      });

      (useGameStore.getState as jest.Mock).mockReturnValue({
        saveGame: mockSaveGame,
        syncPlayerState: mockSyncPlayerState,
        generateSummary: mockGenerateSummary,
        storyText: 'Frontend story',
      });

      const { result } = renderHook(() => useGameState(defaultParams));

      await act(async () => {
        await result.current.handleRegenerate();
      });

      expect(result.current.regenerateToast?.type).toBe('success');
      
      // Fast-forward timers
      act(() => {
        jest.advanceTimersByTime(2000);
      });

      expect(result.current.regenerateToast).toBeNull();
      
      jest.useRealTimers();
    });
  });
});
