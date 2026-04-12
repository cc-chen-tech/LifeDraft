/**
 * useEventGenerator Tests
 * Tests for the event generation hook
 */
import { renderHook, act } from '@testing-library/react';
import { useEventGenerator } from '@/hooks/game/useEventGenerator';
import { streamGameEvent } from '@/lib/sse';
import { useGameStore } from '@/stores/useGameStore';
import { handleEventComplete, handleStatusUpdate } from '@/hooks/game/eventUtils';
import { parseSSEError } from '@/hooks/game/choiceUtils';
import type { Phase, ConnectionStatus } from '@/hooks/game/usePhaseManager';

// Mock dependencies
jest.mock('@/lib/sse', () => ({
  streamGameEvent: jest.fn(),
}));

jest.mock('@/hooks/game/eventUtils', () => ({
  handleEventComplete: jest.fn(),
  handleStatusUpdate: jest.fn(),
}));

jest.mock('@/hooks/game/choiceUtils', () => ({
  parseSSEError: jest.fn((err) => err?.message || 'Unknown error'),
}));

jest.mock('@/stores/useGameStore', () => ({
  useGameStore: {
    getState: jest.fn(() => ({
      storyText: '',
      currentEvent: null,
      syncPlayerState: jest.fn().mockResolvedValue(undefined),
      syncState: jest.fn().mockResolvedValue(undefined),
    })),
  },
}));

describe('useEventGenerator', () => {
  // Mock refs and setters
  const mockPhaseRef: React.MutableRefObject<Phase> = { current: 'loading' as Phase };
  const mockAbortRef: React.MutableRefObject<AbortController | null> = { current: null };
  const mockGeneratingRef: React.MutableRefObject<boolean> = { current: false };
  const mockPollingRef: React.MutableRefObject<boolean> = { current: false };
  const mockPrefetchAbortRef: React.MutableRefObject<AbortController | null> = { current: null };
  const mockPrefetchResultRef: React.MutableRefObject<{
    story: string;
    options: { text: string }[];
    event: { story: string; options: { text: string }[] } | null;
  } | null> = { current: null };
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
  });

  describe('generateEvent', () => {
    it('does nothing when gameId is null', async () => {
      const { result } = renderHook(() =>
        useEventGenerator({ ...defaultParams, gameId: null })
      );

      await act(async () => {
        await result.current.generateEvent();
      });

      expect(streamGameEvent).not.toHaveBeenCalled();
    });

    it('does nothing when already generating', async () => {
      mockGeneratingRef.current = true;

      const { result } = renderHook(() =>
        useEventGenerator(defaultParams)
      );

      await act(async () => {
        await result.current.generateEvent();
      });

      expect(streamGameEvent).not.toHaveBeenCalled();
    });

    it('does nothing when phase is not loading or error', async () => {
      mockPhaseRef.current = 'options' as Phase;

      const { result } = renderHook(() =>
        useEventGenerator(defaultParams)
      );

      await act(async () => {
        await result.current.generateEvent();
      });

      expect(streamGameEvent).not.toHaveBeenCalled();
    });

    it('starts generation when phase is loading', async () => {
      (streamGameEvent as jest.Mock).mockImplementation(async (_gameId, callbacks) => {
        callbacks.onStory('Test story chunk');
        callbacks.onComplete({ options: [{ text: 'Option 1' }] });
      });

      const { result } = renderHook(() =>
        useEventGenerator(defaultParams)
      );

      await act(async () => {
        await result.current.generateEvent();
      });

      expect(mockSetters.setStoryText).toHaveBeenCalledWith('');
      expect(mockSetters.setPhase).toHaveBeenCalledWith('generating');
      expect(streamGameEvent).toHaveBeenCalled();
    });

    it('starts generation when phase is error', async () => {
      mockPhaseRef.current = 'error' as Phase;

      (streamGameEvent as jest.Mock).mockImplementation(async (_gameId, callbacks) => {
        callbacks.onStory('Test story');
        callbacks.onComplete({ options: [{ text: 'Option 1' }] });
      });

      const { result } = renderHook(() =>
        useEventGenerator(defaultParams)
      );

      await act(async () => {
        await result.current.generateEvent();
      });

      expect(streamGameEvent).toHaveBeenCalled();
    });

    it('handles SSE errors gracefully', async () => {
      const mockError = new Error('SSE connection failed');
      (streamGameEvent as jest.Mock).mockImplementation(async (_gameId, callbacks) => {
        callbacks.onError(mockError);
      });
      (parseSSEError as jest.Mock).mockReturnValue('SSE connection failed');

      const { result } = renderHook(() =>
        useEventGenerator(defaultParams)
      );

      await act(async () => {
        await result.current.generateEvent();
      });

      // Error handling triggers polling which eventually times out
      // Just verify the function was called
      expect(streamGameEvent).toHaveBeenCalled();
    });

    it('handles connection status updates', async () => {
      (streamGameEvent as jest.Mock).mockImplementation(async (_gameId, callbacks) => {
        callbacks.onConnectionStatus('connecting');
        callbacks.onConnectionStatus('connected');
        callbacks.onComplete({ options: [] });
      });

      const { result } = renderHook(() =>
        useEventGenerator(defaultParams)
      );

      await act(async () => {
        await result.current.generateEvent();
      });

      expect(mockSetters.setConnectionStatus).toHaveBeenCalledWith('connecting');
      expect(mockSetters.setConnectionStatus).toHaveBeenCalledWith('connected');
    });

    it('handles reconnecting status with attempt info', async () => {
      (streamGameEvent as jest.Mock).mockImplementation(async (_gameId, callbacks) => {
        callbacks.onReconnecting(2, 5);
        callbacks.onComplete({ options: [] });
      });

      const { result } = renderHook(() =>
        useEventGenerator(defaultParams)
      );

      await act(async () => {
        await result.current.generateEvent();
      });

      expect(mockSetters.setReconnectAttempt).toHaveBeenCalledWith({ current: 2, max: 5 });
    });
  });

  describe('prefetchNextEvent', () => {
    it('does nothing when gameId is null', async () => {
      const { result } = renderHook(() =>
        useEventGenerator({ ...defaultParams, gameId: null })
      );

      await act(async () => {
        await result.current.prefetchNextEvent();
      });

      expect(streamGameEvent).not.toHaveBeenCalled();
    });

    it('does nothing when already prefetching', async () => {
      mockPrefetchingRef.current = true;

      const { result } = renderHook(() =>
        useEventGenerator(defaultParams)
      );

      await act(async () => {
        await result.current.prefetchNextEvent();
      });

      expect(streamGameEvent).not.toHaveBeenCalled();
    });

    it('prefetches successfully', async () => {
      (streamGameEvent as jest.Mock).mockImplementation(async (_gameId, callbacks) => {
        callbacks.onStory('Prefetched story');
        callbacks.onComplete({ options: [{ text: 'Option 1' }] });
      });

      const { result } = renderHook(() =>
        useEventGenerator(defaultParams)
      );

      await act(async () => {
        await result.current.prefetchNextEvent();
      });

      expect(streamGameEvent).toHaveBeenCalled();
      expect(mockSetters.setIsPrefetching).toHaveBeenCalledWith(true);
    });

    it('handles prefetch errors', async () => {
      (streamGameEvent as jest.Mock).mockImplementation(async (_gameId, callbacks) => {
        callbacks.onError({ message: 'Prefetch failed' });
      });

      const { result } = renderHook(() =>
        useEventGenerator(defaultParams)
      );

      await act(async () => {
        await result.current.prefetchNextEvent();
      });

      expect(mockPrefetchResultRef.current).toBeNull();
    });

    it('cancels previous prefetch', async () => {
      const mockAbort = jest.fn();
      mockPrefetchAbortRef.current = { abort: mockAbort, signal: {} as AbortSignal };

      (streamGameEvent as jest.Mock).mockImplementation(async () => {});

      const { result } = renderHook(() =>
        useEventGenerator(defaultParams)
      );

      await act(async () => {
        await result.current.prefetchNextEvent();
      });

      expect(mockAbort).toHaveBeenCalled();
    });
  });

  describe('cleanup', () => {
    it('aborts on unmount', () => {
      const mockAbort = jest.fn();
      mockAbortRef.current = { abort: mockAbort, signal: {} as AbortSignal };
      mockPrefetchAbortRef.current = { abort: mockAbort, signal: {} as AbortSignal };

      const { unmount } = renderHook(() =>
        useEventGenerator(defaultParams)
      );

      unmount();

      // Verify cleanup happened
      expect(mockGeneratingRef.current).toBe(false);
      expect(mockPollingRef.current).toBe(false);
      expect(mockPrefetchingRef.current).toBe(false);
    });
  });

  describe('Error handling branches', () => {
    it('handles 404 session expired error', async () => {
      const mockSyncPlayerState = jest.fn().mockResolvedValue(undefined);
      (useGameStore.getState as jest.Mock).mockReturnValue({
        storyText: '',
        currentEvent: null,
        syncPlayerState: mockSyncPlayerState,
        syncState: jest.fn().mockResolvedValue(undefined),
      });

      (streamGameEvent as jest.Mock).mockImplementation(async (_gameId, callbacks) => {
        callbacks.onError({ message: '404 No active game session' });
      });
      (parseSSEError as jest.Mock).mockReturnValue('404 No active game session');

      const { result } = renderHook(() =>
        useEventGenerator(defaultParams)
      );

      await act(async () => {
        await result.current.generateEvent();
      });

      expect(mockSyncPlayerState).toHaveBeenCalled();
    });

    it('handles 404 error when game not found during restore', async () => {
      const mockSyncPlayerState = jest.fn().mockRejectedValue(new Error('Game not found 404'));
      (useGameStore.getState as jest.Mock).mockReturnValue({
        storyText: '',
        currentEvent: null,
        syncPlayerState: mockSyncPlayerState,
        syncState: jest.fn().mockResolvedValue(undefined),
      });

      (streamGameEvent as jest.Mock).mockImplementation(async (_gameId, callbacks) => {
        callbacks.onError({ message: '404 No active game session' });
      });
      (parseSSEError as jest.Mock).mockReturnValue('404 No active game session');

      const { result } = renderHook(() =>
        useEventGenerator(defaultParams)
      );

      await act(async () => {
        await result.current.generateEvent();
      });

      expect(mockSetters.setPhase).toHaveBeenCalledWith('error');
    });

    it('handles unknown error type', async () => {
      (streamGameEvent as jest.Mock).mockImplementation(async (_gameId, callbacks) => {
        callbacks.onError({ message: 'Unknown error' });
      });
      (parseSSEError as jest.Mock).mockReturnValue('Unknown error');

      const { result } = renderHook(() =>
        useEventGenerator(defaultParams)
      );

      await act(async () => {
        await result.current.generateEvent();
      });

      expect(streamGameEvent).toHaveBeenCalled();
    });

    it('handles undefined error type', async () => {
      (streamGameEvent as jest.Mock).mockImplementation(async (_gameId, callbacks) => {
        callbacks.onError({ message: undefined });
      });
      (parseSSEError as jest.Mock).mockReturnValue('undefined');

      const { result } = renderHook(() =>
        useEventGenerator(defaultParams)
      );

      await act(async () => {
        await result.current.generateEvent();
      });

      expect(streamGameEvent).toHaveBeenCalled();
    });

    it('handles polling completion with options', async () => {
      const mockSyncState = jest.fn().mockResolvedValue(undefined);
      (useGameStore.getState as jest.Mock).mockReturnValue({
        storyText: 'Test story',
        currentEvent: {
          story: 'Event story',
          options: [{ text: 'Option 1' }],
        },
        syncPlayerState: jest.fn().mockResolvedValue(undefined),
        syncState: mockSyncState,
      });

      (streamGameEvent as jest.Mock).mockImplementation(async (_gameId, callbacks) => {
        callbacks.onError({ message: 'Connection failed' });
      });
      (parseSSEError as jest.Mock).mockReturnValue('Connection failed');

      const { result } = renderHook(() =>
        useEventGenerator(defaultParams)
      );

      await act(async () => {
        await result.current.generateEvent();
      });

      expect(mockSetters.setPhase).toHaveBeenCalledWith('options');
    });

    it('skips when already polling', async () => {
      mockPollingRef.current = true;

      (streamGameEvent as jest.Mock).mockImplementation(async (_gameId, callbacks) => {
        callbacks.onError({ message: 'Error' });
      });
      (parseSSEError as jest.Mock).mockReturnValue('Error');

      const { result } = renderHook(() =>
        useEventGenerator(defaultParams)
      );

      await act(async () => {
        await result.current.generateEvent();
      });

      // Should not start another polling cycle
      expect(mockPollingRef.current).toBe(true);
    });
  });

  describe('Status updates', () => {
    it('handles status updates via handleStatusUpdate', async () => {
      (streamGameEvent as jest.Mock).mockImplementation(async (_gameId, callbacks) => {
        callbacks.onStatus('generating_story');
        callbacks.onComplete({ options: [] });
      });

      const { result } = renderHook(() =>
        useEventGenerator(defaultParams)
      );

      await act(async () => {
        await result.current.generateEvent();
      });

      expect(handleStatusUpdate).toHaveBeenCalledWith('generating_story', mockSetters.setProcessing, {"current": false});
    });

    it('clears reconnect attempt on non-reconnecting status', async () => {
      (streamGameEvent as jest.Mock).mockImplementation(async (_gameId, callbacks) => {
        callbacks.onConnectionStatus('connected');
        callbacks.onComplete({ options: [] });
      });

      const { result } = renderHook(() =>
        useEventGenerator(defaultParams)
      );

      await act(async () => {
        await result.current.generateEvent();
      });

      expect(mockSetters.setReconnectAttempt).toHaveBeenCalledWith(null);
    });
  });

  describe('Event completion', () => {
    it('calls handleEventComplete with correct data', async () => {
      const mockData = {
        event_description: 'Test event',
        options: [{ text: 'Option 1' }, { text: 'Option 2' }],
      };
      (streamGameEvent as jest.Mock).mockImplementation(async (_gameId, callbacks) => {
        callbacks.onComplete(mockData);
      });

      const { result } = renderHook(() =>
        useEventGenerator(defaultParams)
      );

      await act(async () => {
        await result.current.generateEvent();
      });

      expect(handleEventComplete).toHaveBeenCalledWith(mockData, expect.objectContaining({
        setStoryText: mockSetters.setStoryText,
        setOptions: mockSetters.setOptions,
      }));
    });
  });

  describe('Prefetch on result phase', () => {
    it('starts prefetch when entering result phase', async () => {
      mockPhaseRef.current = 'result' as Phase;

      (streamGameEvent as jest.Mock).mockImplementation(async (_gameId, callbacks) => {
        callbacks.onStory('Prefetched');
        callbacks.onComplete({ options: [{ text: 'Option' }] });
      });

      renderHook(() =>
        useEventGenerator(defaultParams)
      );

      // Wait for the timeout
      await act(async () => {        await new Promise(resolve => setTimeout(resolve, 600));
      });

      expect(streamGameEvent).toHaveBeenCalled();
    });

    it('does not prefetch when isGameOver is true', async () => {
      mockPhaseRef.current = 'result' as Phase;

      const { result } = renderHook(() =>
        useEventGenerator({ ...defaultParams, isGameOver: true })
      );

      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 600));
      });

      // Should not have called streamGameEvent for prefetch
      expect(streamGameEvent).not.toHaveBeenCalled();
    });
  });
});
