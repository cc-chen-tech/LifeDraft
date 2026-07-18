import { act, renderHook, waitFor } from '@testing-library/react';
import { useChoiceHandler } from '@/hooks/game/useChoiceHandler';
import { useGameStore } from '@/stores/useGameStore';
import { createSSEMockResponse } from '@/__tests__/helpers/sse-mock';

const setters = {
  setPhase: jest.fn(), setConnectionStatus: jest.fn(), setReconnectAttempt: jest.fn(),
  setProcessing: jest.fn(), appendStoryText: jest.fn(), setCurrentEvent: jest.fn(),
  setGameOver: jest.fn(), setSummaryText: jest.fn(), setRoundSummary: jest.fn(),
  setOptions: jest.fn(), setStoryText: jest.fn(),
};
const abortRef: React.MutableRefObject<AbortController | null> = { current: null };
const generatingRef: React.MutableRefObject<boolean> = { current: false };

function renderChoiceHandler() {
  return renderHook(() => useChoiceHandler({
    gameId: 44, abortRef, generatingRef, ...setters,
  }));
}

describe('useChoiceHandler recovery contracts', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    abortRef.current = null;
    generatingRef.current = false;
    useGameStore.setState({
      storyText: 'Base story before choice.', currentEvent: { options: [{ text: '调查' }] },
      roundInfo: { current_round: 1 }, enableSceneImage: false,
      generateRoundSceneImage: jest.fn().mockResolvedValue(undefined),
      syncPlayerState: jest.fn().mockResolvedValue(undefined),
    } as never);
  });

  it('restores base story when a choice stream retries before replacement content', async () => {
    (global.fetch as jest.Mock).mockResolvedValue(createSSEMockResponse([
      'event: story\ndata: {"content":"partial content"}\n\n',
      'event: status\ndata: {"phase":"retry"}\n\n',
      'event: story\ndata: {"content":"replacement content"}\n\n',
      'event: complete\ndata: {"event_description":"replacement content","options":[]}\n\n',
    ]));
    const { result } = renderChoiceHandler();

    await act(async () => { await result.current.handleChoice(0); });

    expect(setters.setStoryText).toHaveBeenCalledWith('Base story before choice.');
    expect(setters.setProcessing).toHaveBeenCalledWith(true, 'retrying');
    expect(setters.appendStoryText).toHaveBeenCalledWith('replacement content');
    await waitFor(() => expect(setters.setPhase).toHaveBeenCalledWith('result'));
  });

  it('uses complete-only story continuation for a custom choice', async () => {
    (global.fetch as jest.Mock).mockResolvedValue(createSSEMockResponse([
      'event: complete\ndata: {"story_continuation":"custom terminal story","options":[]}\n\n',
    ]));
    const { result } = renderChoiceHandler();

    await act(async () => { await result.current.handleCustomChoice('继续调查'); });

    expect(setters.setStoryText).toHaveBeenCalledWith(
      'Base story before choice.\n\ncustom terminal story'
    );
    await waitFor(() => expect(setters.setPhase).toHaveBeenCalledWith('result'));
  });
});
