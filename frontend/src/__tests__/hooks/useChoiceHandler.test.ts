/**
 * useChoiceHandler Tests
 * Tests for the choice handling hook
 */
import { renderHook, act } from '@testing-library/react';
import { useChoiceHandler } from '@/hooks/game/useChoiceHandler';
import { streamChoice, streamCustomChoice } from '@/lib/sse';
import { handleChoiceComplete, handleChoiceError } from '@/hooks/game/choiceUtils';
import { markRetry } from '@/hooks/game/eventUtils';
import { useGameStore } from '@/stores/useGameStore';
import type { Phase, ConnectionStatus } from '@/hooks/game/usePhaseManager';

// Mock dependencies
jest.mock('@/lib/sse', () => ({
  streamChoice: jest.fn(),
  streamCustomChoice: jest.fn(),
}));

jest.mock('@/hooks/game/choiceUtils', () => ({
  handleChoiceComplete: jest.fn(),
  handleChoiceError: jest.fn(),
}));

jest.mock('@/hooks/game/eventUtils', () => ({
  markRetry: jest.fn(),
  checkAndClearRetry: jest.fn(),
}));

jest.mock('@/stores/useGameStore', () => ({
  useGameStore: {
    getState: jest.fn(() => ({
      progress: { week: 1 },
    })),
    setState: jest.fn(),
  },
}));

describe('useChoiceHandler', () => {
  const mockAbortRef: React.MutableRefObject<AbortController | null> = { current: null };
  const mockGeneratingRef: React.MutableRefObject<boolean> = { current: false };

  const mockSetters = {
    setPhase: jest.fn(),
    setConnectionStatus: jest.fn(),
    setReconnectAttempt: jest.fn(),
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
    setPhase: mockSetters.setPhase,
    setConnectionStatus: mockSetters.setConnectionStatus,
    setReconnectAttempt: mockSetters.setReconnectAttempt,
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
    mockGeneratingRef.current = false;
    mockAbortRef.current = null;
  });

  describe('handleChoice', () => {
    it('does nothing when gameId is null', async () => {
      const { result } = renderHook(() =>
        useChoiceHandler({ ...defaultParams, gameId: null })
      );

      await act(async () => {
        await result.current.handleChoice(0);
      });

      expect(streamChoice).not.toHaveBeenCalled();
    });

    it('sets phase to choosing when handling choice', async () => {
      (streamChoice as jest.Mock).mockImplementation(async () => {
        // Simulate SSE completion
      });

      const { result } = renderHook(() => useChoiceHandler(defaultParams));

      await act(async () => {
        await result.current.handleChoice(0);
      });

      expect(mockSetters.setPhase).toHaveBeenCalledWith('choosing');
    });

    it('aborts previous request when handling new choice', async () => {
      const mockAbort = jest.fn();
      mockAbortRef.current = { abort: mockAbort, signal: {} as AbortSignal };

      (streamChoice as jest.Mock).mockImplementation(async () => {});

      const { result } = renderHook(() => useChoiceHandler(defaultParams));

      await act(async () => {
        await result.current.handleChoice(0);
      });

      expect(mockAbort).toHaveBeenCalled();
    });
  });

  describe('handleCustomChoice', () => {
    it('does nothing when gameId is null', async () => {
      const { result } = renderHook(() =>
        useChoiceHandler({ ...defaultParams, gameId: null })
      );

      await act(async () => {
        await result.current.handleCustomChoice('custom input');
      });

      expect(streamCustomChoice).not.toHaveBeenCalled();
    });

    it('handles custom choice with valid input', async () => {
      (streamCustomChoice as jest.Mock).mockImplementation(async () => {});

      const { result } = renderHook(() => useChoiceHandler(defaultParams));

      await act(async () => {
        await result.current.handleCustomChoice('I want to explore the forest');
      });

      expect(streamCustomChoice).toHaveBeenCalled();
    });

    it('passes custom input to API', async () => {
      (streamCustomChoice as jest.Mock).mockImplementation(async () => {});

      const { result } = renderHook(() => useChoiceHandler(defaultParams));

      await act(async () => {
        await result.current.handleCustomChoice('  test input  ');
      });

      expect(streamCustomChoice).toHaveBeenCalledWith(
        1,
        '  test input  ',
        expect.any(Object),
        expect.any(Object)
      );
    });
  });

  describe('SSE callbacks', () => {
    it('handles onStory callback', async () => {
      (streamChoice as jest.Mock).mockImplementation(async (_gameId, _index, callbacks) => {
        callbacks.onStory('Story chunk');
        callbacks.onComplete({});
      });

      const { result } = renderHook(() => useChoiceHandler(defaultParams));

      await act(async () => {
        await result.current.handleChoice(0);
      });

      expect(mockSetters.appendStoryText).toHaveBeenCalledWith('Story chunk');
    });

    it('handles onStatus callback', async () => {
      (streamChoice as jest.Mock).mockImplementation(async (_gameId, _index, callbacks) => {
        callbacks.onStatus({ phase: 'generating' });
        callbacks.onComplete({});
      });

      const { result } = renderHook(() => useChoiceHandler(defaultParams));

      await act(async () => {
        await result.current.handleChoice(0);
      });

      expect(mockSetters.setProcessing).toHaveBeenCalledWith(true, 'generating');
    });

    it('handles onConnectionStatus callback', async () => {
      (streamChoice as jest.Mock).mockImplementation(async (_gameId, _index, callbacks) => {
        callbacks.onConnectionStatus('connecting');
        callbacks.onComplete({});
      });

      const { result } = renderHook(() => useChoiceHandler(defaultParams));

      await act(async () => {
        await result.current.handleChoice(0);
      });

      expect(mockSetters.setConnectionStatus).toHaveBeenCalledWith('connecting');
    });

    it('handles onReconnecting callback', async () => {
      (streamChoice as jest.Mock).mockImplementation(async (_gameId, _index, callbacks) => {
        callbacks.onReconnecting(2, 5);
        callbacks.onComplete({});
      });

      const { result } = renderHook(() => useChoiceHandler(defaultParams));

      await act(async () => {
        await result.current.handleChoice(0);
      });

      expect(mockSetters.setReconnectAttempt).toHaveBeenCalledWith({ current: 2, max: 5 });
    });

    it('handles onComplete callback', async () => {
      (streamChoice as jest.Mock).mockImplementation(async (_gameId, _index, callbacks) => {
        callbacks.onComplete({ event_description: 'Test', options: [] });
      });

      const { result } = renderHook(() => useChoiceHandler(defaultParams));

      await act(async () => {
        await result.current.handleChoice(0);
      });

      expect(handleChoiceComplete).toHaveBeenCalled();
    });

    it('handles onError callback', async () => {
      (streamChoice as jest.Mock).mockImplementation(async (_gameId, _index, callbacks) => {
        callbacks.onError(new Error('Test error'));
      });

      const { result } = renderHook(() => useChoiceHandler(defaultParams));

      await act(async () => {
        await result.current.handleChoice(0);
      });

      expect(handleChoiceError).toHaveBeenCalled();
    });

    it('clears reconnect attempt on non-reconnecting status', async () => {
      (streamChoice as jest.Mock).mockImplementation(async (_gameId, _index, callbacks) => {
        callbacks.onConnectionStatus('connected');
        callbacks.onComplete({});
      });

      const { result } = renderHook(() => useChoiceHandler(defaultParams));

      await act(async () => {
        await result.current.handleChoice(0);
      });

      expect(mockSetters.setReconnectAttempt).toHaveBeenCalledWith(null);
    });
  });

  describe('handleChoice error handling', () => {
    it('calls handleChoiceError when SSE fails', async () => {
      (streamChoice as jest.Mock).mockImplementation(async (_gameId, _index, callbacks) => {
        callbacks.onError(new Error('SSE failed'));
      });

      const { result } = renderHook(() => useChoiceHandler(defaultParams));

      await act(async () => {
        await result.current.handleChoice(0);
      });

      expect(handleChoiceError).toHaveBeenCalledWith(
        expect.any(Error),
        1,
        expect.any(Object),
        expect.objectContaining({
          optionIndex: 0,
          isRetry: false,
        }),
        'handleChoice'
      );
    });

    it('marks SSE as succeeded after receiving story', async () => {
      (streamChoice as jest.Mock).mockImplementation(async (_gameId, _index, callbacks) => {
        callbacks.onStory('Story text');
        callbacks.onError(new Error('Connection lost'));
      });

      const { result } = renderHook(() => useChoiceHandler(defaultParams));

      await act(async () => {
        await result.current.handleChoice(0);
      });

      // Error handler should be called with sseSucceeded = true
      expect(handleChoiceError).toHaveBeenCalledWith(
        expect.any(Error),
        1,
        expect.any(Object),
        expect.objectContaining({
          sseSucceeded: true,
        }),
        'handleChoice'
      );
    });

    it('marks SSE as succeeded after receiving status', async () => {
      (streamChoice as jest.Mock).mockImplementation(async (_gameId, _index, callbacks) => {
        callbacks.onStatus({ phase: 'generating' });
        callbacks.onError(new Error('Connection lost'));
      });

      const { result } = renderHook(() => useChoiceHandler(defaultParams));

      await act(async () => {
        await result.current.handleChoice(0);
      });

      expect(handleChoiceError).toHaveBeenCalledWith(
        expect.any(Error),
        1,
        expect.any(Object),
        expect.objectContaining({
          sseSucceeded: true,
        }),
        'handleChoice'
      );
    });
  });

  describe('handleCustomChoice error handling', () => {
    it('calls handleChoiceError when custom choice SSE fails', async () => {
      (streamCustomChoice as jest.Mock).mockImplementation(async (_gameId, _text, callbacks) => {
        callbacks.onError(new Error('Custom choice failed'));
      });

      const { result } = renderHook(() => useChoiceHandler(defaultParams));

      await act(async () => {
        await result.current.handleCustomChoice('custom text');
      });

      expect(handleChoiceError).toHaveBeenCalledWith(
        expect.any(Error),
        1,
        expect.any(Object),
        expect.objectContaining({
          customText: 'custom text',
          isRetry: false,
        }),
        'handleCustomChoice'
      );
    });

    it('marks SSE as succeeded after receiving story in custom choice', async () => {
      (streamCustomChoice as jest.Mock).mockImplementation(async (_gameId, _text, callbacks) => {
        callbacks.onStory('Story text');
        callbacks.onError(new Error('Connection lost'));
      });

      const { result } = renderHook(() => useChoiceHandler(defaultParams));

      await act(async () => {
        await result.current.handleCustomChoice('custom text');
      });

      expect(handleChoiceError).toHaveBeenCalledWith(
        expect.any(Error),
        1,
        expect.any(Object),
        expect.objectContaining({
          sseSucceeded: true,
        }),
        'handleCustomChoice'
      );
    });
  });

  describe('AbortController handling', () => {
    it('creates new AbortController on each choice', async () => {
      (streamChoice as jest.Mock).mockImplementation(async () => {});

      const { result } = renderHook(() => useChoiceHandler(defaultParams));

      await act(async () => {
        await result.current.handleChoice(0);
      });

      expect(mockAbortRef.current).not.toBeNull();
      expect(mockAbortRef.current).toBeInstanceOf(AbortController);
    });

    it('aborts previous request when new choice is made', async () => {
      const mockAbort = jest.fn();
      mockAbortRef.current = { abort: mockAbort, signal: {} as AbortSignal } as AbortController;

      (streamChoice as jest.Mock).mockImplementation(async () => {});

      const { result } = renderHook(() => useChoiceHandler(defaultParams));

      await act(async () => {
        await result.current.handleChoice(0);
      });

      expect(mockAbort).toHaveBeenCalled();
    });

    it('aborts previous request when custom choice is made', async () => {
      const mockAbort = jest.fn();
      mockAbortRef.current = { abort: mockAbort, signal: {} as AbortSignal } as AbortController;

      (streamCustomChoice as jest.Mock).mockImplementation(async () => {});

      const { result } = renderHook(() => useChoiceHandler(defaultParams));

      await act(async () => {
        await result.current.handleCustomChoice('custom text');
      });

      expect(mockAbort).toHaveBeenCalled();
    });
  });

  describe('retry status handling', () => {
    it('clears story text when retry status is received', async () => {
      (streamChoice as jest.Mock).mockImplementation(async (_gameId, _index, callbacks) => {
        callbacks.onStory('First story chunk');
        callbacks.onStatus({ phase: 'retry' });
        callbacks.onStory('New story after retry');
        callbacks.onComplete({});
      });

      const { result } = renderHook(() => useChoiceHandler(defaultParams));

      await act(async () => {
        await result.current.handleChoice(0);
      });

      // Should mark retry and clear story text on retry
      expect(markRetry).toHaveBeenCalled();
      expect(useGameStore.setState).toHaveBeenCalledWith({ storyText: '' });
      // Should set processing to retrying
      expect(mockSetters.setProcessing).toHaveBeenCalledWith(true, 'retrying');
    });

    it('sets processing to retrying on retrying status', async () => {
      (streamChoice as jest.Mock).mockImplementation(async (_gameId, _index, callbacks) => {
        callbacks.onStatus({ phase: 'retrying' });
        callbacks.onComplete({});
      });

      const { result } = renderHook(() => useChoiceHandler(defaultParams));

      await act(async () => {
        await result.current.handleChoice(0);
      });

      expect(mockSetters.setProcessing).toHaveBeenCalledWith(true, 'retrying');
    });

    it('handles retry status for custom choice', async () => {
      (streamCustomChoice as jest.Mock).mockImplementation(async (_gameId, _text, callbacks) => {
        callbacks.onStory('First story');
        callbacks.onStatus({ phase: 'retry' });
        callbacks.onStory('New story');
        callbacks.onComplete({});
      });

      const { result } = renderHook(() => useChoiceHandler(defaultParams));

      await act(async () => {
        await result.current.handleCustomChoice('custom choice');
      });

      expect(markRetry).toHaveBeenCalled();
      expect(useGameStore.setState).toHaveBeenCalledWith({ storyText: '' });
      expect(mockSetters.setProcessing).toHaveBeenCalledWith(true, 'retrying');
    });
  });
});
