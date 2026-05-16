/**
 * useChoiceHandler Tests
 * Tests for the choice handling hook
 */
import { renderHook, act } from '@testing-library/react';
import { useChoiceHandler } from '@/hooks/game/useChoiceHandler';
import { useGameStore } from '@/stores/useGameStore';
import type { Phase, ConnectionStatus } from '@/hooks/game/usePhaseManager';
import { createSSEMockResponse } from '@/__tests__/helpers/sse-mock';

/** Create a fresh SSE response for streamChoice calls */
function makeChoiceResponse() {
  return createSSEMockResponse([
    'event: story\ndata: Choice result story\n\n',
    'event: complete\ndata: {"event_description":"Choice result story","options":[{"text":"Next Option"}]}\n\n',
  ]);
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

    it('aborts previous request when handling new choice', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(makeChoiceResponse());
      const mockAbort = jest.fn();
      mockAbortRef.current = { abort: mockAbort, signal: {} as AbortSignal };
      const { result } = renderHook(() => useChoiceHandler(defaultParams));
      await act(async () => { await result.current.handleChoice(0); });
      expect(mockAbort).toHaveBeenCalled();
    });
  });
});
