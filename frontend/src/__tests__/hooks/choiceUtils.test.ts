/**
 * hooks/game/choiceUtils.ts Tests
 * Tests for choice handling utilities
 */
import {
  parseSSEError,
  isRecoverableChoiceStreamError,
  handleChoiceComplete,
  enterResultPhase,
  handleChoiceAlreadyProcessed,
  handleNoCurrentEvent,
  handleFallbackChoice,
  handleChoiceError,
  ChoiceHandlers,
  ChoiceErrorContext,
} from '@/hooks/game/choiceUtils';
import { useGameStore } from '@/stores/useGameStore';
import { jsonResponse } from '@/__tests__/helpers/fetch';
import { spyOnStoreMethods } from '@/__tests__/helpers/store-spy';

const STORE_METHODS = ['syncPlayerState', 'syncState', 'generateRoundSceneImage', 'setLastChoiceEffects'] as const;

type StoreSpy = ReturnType<typeof spyOnStoreMethods<typeof useGameStore, (typeof STORE_METHODS)[number]>>;

function setupDefaultState() {
  useGameStore.setState({
    storyText: 'Existing story',
    currentEvent: {
      story: 'Event story',
      options: [{ text: 'Option 1' }, { text: 'Option 2' }],
    } as Record<string, unknown>,
    roundInfo: { current_round: 1 },
  });
}

function setStoreState(overrides: Record<string, unknown>) {
  useGameStore.setState(overrides as never);
}

describe('choiceUtils', () => {
  let storeSpy: StoreSpy;
  const mockHandlers: ChoiceHandlers = {
    setProcessing: jest.fn(),
    setConnectionStatus: jest.fn(),
    setReconnectAttempt: jest.fn(),
    setRoundSummary: jest.fn(),
    setSummaryText: jest.fn(),
    setCurrentEvent: jest.fn(),
    setGameOver: jest.fn(),
    setOptions: jest.fn(),
    setStoryText: jest.fn(),
    setPhase: jest.fn(),
    generatingRef: { current: true },
  };

  beforeEach(() => {
    jest.clearAllMocks();
    (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({}));
    setupDefaultState();
    storeSpy = spyOnStoreMethods(useGameStore, STORE_METHODS);
  });

  afterEach(() => {
    storeSpy.restore();
  });

  describe('parseSSEError', () => {
    it('extracts message from error object', () => {
      expect(parseSSEError({ message: 'Test error message' })).toBe('Test error message');
    });

    it('extracts error property', () => {
      expect(parseSSEError({ error: 'Error from error property' })).toBe('Error from error property');
    });

    it('prefers message over error', () => {
      expect(parseSSEError({ message: 'Message', error: 'Error' })).toBe('Message');
    });

    it('handles empty object', () => {
      expect(parseSSEError({})).toBe('Unknown error');
    });

    it('handles string error', () => {
      expect(parseSSEError('String error')).toBe('String error');
    });

    it('handles null', () => {
      expect(parseSSEError(null)).toBe('Unknown error');
    });

    it('handles undefined', () => {
      expect(parseSSEError(undefined)).toBe('Unknown error');
    });

    it('handles number', () => {
      expect(parseSSEError(404)).toBe('404');
    });
  });

  describe('isRecoverableChoiceStreamError', () => {
    it('treats interrupted browser streams as recoverable', () => {
      expect(isRecoverableChoiceStreamError('network error')).toBe(true);
      expect(isRecoverableChoiceStreamError('net::ERR_INCOMPLETE_CHUNKED_ENCODING')).toBe(true);
      expect(isRecoverableChoiceStreamError('Unknown error')).toBe(true);
    });

    it('does not treat domain validation errors as recoverable stream failures', () => {
      expect(isRecoverableChoiceStreamError('Invalid option index')).toBe(false);
    });
  });

  describe('handleChoiceComplete', () => {
    it('sets summary when present', () => {
      handleChoiceComplete({ summary: 'Round summary text' }, mockHandlers);
      expect(mockHandlers.setRoundSummary).toHaveBeenCalledWith('Round summary text');
    });

    it('clears summary when not present', () => {
      handleChoiceComplete({}, mockHandlers);
      expect(mockHandlers.setRoundSummary).toHaveBeenCalledWith(null);
    });

    it('enters summary phase on weekly summary', () => {
      handleChoiceComplete({
        need_weekly_summary: true,
        weekly_summary: 'Weekly summary text',
      }, mockHandlers);
      expect(mockHandlers.setSummaryText).toHaveBeenCalledWith('Weekly summary text');
      expect(mockHandlers.setPhase).toHaveBeenCalledWith('summary');
    });

    it('enters ending phase on game over', () => {
      handleChoiceComplete({ game_over: true }, mockHandlers);
      expect(mockHandlers.setPhase).toHaveBeenCalledWith('ending');
      expect(mockHandlers.setGameOver).toHaveBeenCalledWith(true);
    });

    it('enters result phase by default', () => {
      handleChoiceComplete({}, mockHandlers);
      expect(mockHandlers.setOptions).toHaveBeenCalledWith([]);
      expect(mockHandlers.setPhase).toHaveBeenCalledWith('result');
    });

    it('clears current event', () => {
      handleChoiceComplete({}, mockHandlers);
      expect(mockHandlers.setCurrentEvent).toHaveBeenCalledWith(null);
    });

    it('clears processing state', () => {
      handleChoiceComplete({}, mockHandlers);
      expect(mockHandlers.setProcessing).toHaveBeenCalledWith(false);
      expect(mockHandlers.setConnectionStatus).toHaveBeenCalledWith(null);
    });
  });

  describe('enterResultPhase', () => {
    it('enters result phase correctly', () => {
      enterResultPhase(mockHandlers);
      expect(mockHandlers.setProcessing).toHaveBeenCalledWith(false);
      expect(mockHandlers.generatingRef.current).toBe(false);
      expect(mockHandlers.setOptions).toHaveBeenCalledWith([]);
      expect(mockHandlers.setCurrentEvent).toHaveBeenCalledWith(null);
      expect(mockHandlers.setPhase).toHaveBeenCalledWith('result');
    });
  });

  describe('handleChoiceAlreadyProcessed', () => {
    it('handles choice already processed error', async () => {
      storeSpy.spies.syncPlayerState.mockResolvedValue({
        player_state: { round_history: [{ story_continuation: 'The story continues...' }] },
      });

      await handleChoiceAlreadyProcessed('Option text', mockHandlers, 'test');
      expect(mockHandlers.setPhase).toHaveBeenCalledWith('result');
    });
  });

  describe('handleNoCurrentEvent', () => {
    it('handles no current event error', async () => {
      storeSpy.spies.syncPlayerState.mockResolvedValue({
        player_state: { round_history: [] },
      });

      await handleNoCurrentEvent('Choice text', mockHandlers, 'test');
      expect(mockHandlers.setPhase).toHaveBeenCalledWith('result');
    });
  });

  describe('handleFallbackChoice', () => {
    it('uses option index for fallback', async () => {
      const mockResult = { summary: 'Fallback result', need_weekly_summary: false, game_over: false };
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockResult));

      const context: ChoiceErrorContext = { optionIndex: 0, isRetry: false, sseSucceeded: false };
      const result = await handleFallbackChoice(123, context, mockHandlers, 'test');

      expect(result).toBeTruthy();
      const calls = (global.fetch as jest.Mock).mock.calls;
      expect(calls[0][0]).toBe('/api/games/123/choice-sync');
      expect(JSON.parse(calls[0][1].body)).toEqual({ option_index: 0 });
    });

    it('uses custom text for fallback', async () => {
      const mockResult = { summary: 'Custom result', need_weekly_summary: false, game_over: false };
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockResult));

      const context: ChoiceErrorContext = { customText: 'Custom action', isRetry: false, sseSucceeded: false };
      const result = await handleFallbackChoice(123, context, mockHandlers, 'test');

      expect(result).toBeTruthy();
      const calls = (global.fetch as jest.Mock).mock.calls;
      expect(calls[0][0]).toBe('/api/games/123/custom-choice-sync');
      expect(JSON.parse(calls[0][1].body)).toEqual({ custom_text: 'Custom action' });
    });

    it('returns false without option or custom text', async () => {
      const context: ChoiceErrorContext = { isRetry: false, sseSucceeded: false };
      const result = await handleFallbackChoice(123, context, mockHandlers, 'test');
      expect(result).toBe(false);
    });

    it('handles fallback failure with no current event', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ message: 'No current event' }, 400));

      const context: ChoiceErrorContext = { optionIndex: 0, isRetry: false, sseSucceeded: false };
      const result = await handleFallbackChoice(123, context, mockHandlers, 'test');

      expect(result).toBe(true);
      expect(mockHandlers.setPhase).toHaveBeenCalledWith('result');
    });

    it('handles fallback failure when the streaming choice already completed server-side', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        detail: {
          error: 'choice_already_processed',
          message: 'Choice was already processed. Please continue to next round.',
        },
      }, 400));

      const context: ChoiceErrorContext = {
        optionIndex: 0,
        isRetry: false,
        sseSucceeded: true,
        baseStoryText: 'Base story',
      };
      const result = await handleFallbackChoice(123, context, mockHandlers, 'test');

      expect(result).toBe(true);
      expect(mockHandlers.setPhase).toHaveBeenCalledWith('result');
    });

    it('preserves structured FastAPI detail errors for already-processed fallback recovery', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        detail: {
          error: 'choice_already_processed',
          message: 'Choice was already processed. Please continue to next round.',
        },
      }, 400));

      const context: ChoiceErrorContext = {
        optionIndex: 0,
        isRetry: false,
        sseSucceeded: true,
        baseStoryText: 'Base story',
      };

      await handleChoiceError(
        { message: 'network error' },
        123, mockHandlers, context, 'test'
      );

      expect(mockHandlers.setPhase).toHaveBeenCalledWith('result');
      expect(mockHandlers.setConnectionStatus).not.toHaveBeenCalledWith('error');
    });

    it('handles fallback failure with other error', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ message: 'Network error' }, 400));

      const context: ChoiceErrorContext = { optionIndex: 0, isRetry: false, sseSucceeded: false };
      const result = await handleFallbackChoice(123, context, mockHandlers, 'test');

      expect(result).toBe(false);
    });

    it('recovers from a transient choice-sync network failure when backend already saved history', async () => {
      (global.fetch as jest.Mock).mockRejectedValue(new TypeError('Failed to fetch'));
      storeSpy.spies.syncPlayerState.mockImplementation(async () => {
        useGameStore.setState({
          playerState: {
            round_history: [{ story_continuation: '后端已经保存的选择结果' }],
          } as never,
        });
      });

      const context: ChoiceErrorContext = {
        optionIndex: 0,
        isRetry: false,
        sseSucceeded: true,
        baseStoryText: 'Base story',
      };
      const result = await handleFallbackChoice(123, context, mockHandlers, 'test');

      expect(result).toBe(true);
      expect(mockHandlers.setStoryText).toHaveBeenCalledWith(
        'Base story\n\n--- 主角选择了：Option 1 ---\n\n后端已经保存的选择结果'
      );
      expect(mockHandlers.setPhase).toHaveBeenCalledWith('result');
    });
  });

  describe('handleChoiceError', () => {
    it('handles choice_already_processed error', async () => {
      storeSpy.spies.syncPlayerState.mockResolvedValue({
        player_state: { round_history: [] },
      });
      useGameStore.setState({
        currentEvent: { options: [{ text: 'Option 1' }] } as Record<string, unknown>,
      });

      const context: ChoiceErrorContext = { optionIndex: 0, isRetry: false, sseSucceeded: false };

      await handleChoiceError(
        { message: 'choice_already_processed' },
        123, mockHandlers, context, 'test'
      );

      expect(mockHandlers.setPhase).toHaveBeenCalledWith('result');
    });

    it('handles No current event error', async () => {
      storeSpy.spies.syncPlayerState.mockResolvedValue({
        player_state: { round_history: [] },
      });
      useGameStore.setState({
        currentEvent: { options: [{ text: 'Option 1' }] } as Record<string, unknown>,
      });

      const context: ChoiceErrorContext = { optionIndex: 0, isRetry: false, sseSucceeded: false };

      await handleChoiceError(
        { message: 'No current event found' },
        123, mockHandlers, context, 'test'
      );

      expect(mockHandlers.setPhase).toHaveBeenCalledWith('result');
    });

    it('handles session expired (404)', async () => {
      storeSpy.spies.syncState.mockResolvedValue(undefined);

      const context: ChoiceErrorContext = {
        optionIndex: 0, isRetry: false, sseSucceeded: false,
        retryChoice: jest.fn(),
      };

      await handleChoiceError(
        { message: '404 Not Found' },
        123, mockHandlers, context, 'test'
      );

      expect(mockHandlers.setProcessing).toHaveBeenCalledWith(true, '恢复游戏状态...');
    });

    it('handles fallback when SSE not succeeded', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        summary: 'Result', need_weekly_summary: false, game_over: false,
      }));

      const context: ChoiceErrorContext = { optionIndex: 0, isRetry: false, sseSucceeded: false };

      await handleChoiceError(
        { message: 'Some error' },
        123, mockHandlers, context, 'test'
      );

      const choiceCalls = (global.fetch as jest.Mock).mock.calls.filter(
        (c: unknown[]) => (c[0] as string).includes('choice-sync')
      );
      expect(choiceCalls.length).toBeGreaterThan(0);
    });

    it('falls back when an already-started SSE choice stream is interrupted', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({
        story_continuation: '完整的同步续写结果',
        summary: 'Result',
        need_weekly_summary: false,
        game_over: false,
      }));
      useGameStore.setState({
        storyText: 'Base story plus partial broken stream',
        currentEvent: { options: [{ text: 'Option 1' }] } as Record<string, unknown>,
      });

      const context: ChoiceErrorContext = {
        optionIndex: 0,
        isRetry: false,
        sseSucceeded: true,
        baseStoryText: 'Base story',
      };

      await handleChoiceError(
        { message: 'network error' },
        123, mockHandlers, context, 'test'
      );

      const choiceCalls = (global.fetch as jest.Mock).mock.calls.filter(
        (c: unknown[]) => (c[0] as string).includes('choice-sync')
      );
      expect(choiceCalls.length).toBeGreaterThan(0);
      expect(mockHandlers.setStoryText).toHaveBeenCalledWith(
        'Base story\n\n--- 主角选择了：Option 1 ---\n\n完整的同步续写结果'
      );
      expect(mockHandlers.setPhase).toHaveBeenCalledWith('result');
    });

    it('sets error phase for unhandled errors', async () => {
      const context: ChoiceErrorContext = { optionIndex: 0, isRetry: true, sseSucceeded: true };

      await handleChoiceError(
        { message: 'Invalid option index' },
        123, mockHandlers, context, 'test'
      );

      expect(mockHandlers.setProcessing).toHaveBeenCalledWith(false);
      expect(mockHandlers.setConnectionStatus).toHaveBeenCalledWith('error');
      expect(mockHandlers.setPhase).toHaveBeenCalledWith('error');
    });
  });
});
