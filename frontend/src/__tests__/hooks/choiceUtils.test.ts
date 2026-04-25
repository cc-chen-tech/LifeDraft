/**
 * hooks/game/choiceUtils.ts Tests
 * Tests for choice handling utilities
 */

// Mock dependencies
jest.mock('@/stores/useGameStore', () => ({
  useGameStore: {
    getState: jest.fn(() => ({
      syncPlayerState: jest.fn().mockResolvedValue(undefined),
      syncState: jest.fn(),
      storyText: 'Existing story',
      currentEvent: {
        story: 'Event story',
        options: [{ text: 'Option 1' }, { text: 'Option 2' }],
      },
      roundInfo: { current_round: 1 },
      generateRoundSceneImage: jest.fn().mockResolvedValue(undefined),
      setLastChoiceEffects: jest.fn(),
    })),
  },
}));

jest.mock('@/lib/api', () => ({
  gameplay: {
    makeChoiceSync: jest.fn(),
    makeCustomChoiceSync: jest.fn(),
  },
}));

import {
  parseSSEError,
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
import { gameplay } from '@/lib/api';

// ★ 辅助函数：重置 mock 状态
const resetMockStore = (overrides = {}) => {
  (useGameStore.getState as jest.Mock).mockReturnValue({
    syncPlayerState: jest.fn().mockResolvedValue(undefined),
    syncState: jest.fn(),
    storyText: 'Existing story',
    currentEvent: {
      story: 'Event story',
      options: [{ text: 'Option 1' }, { text: 'Option 2' }],
    },
    roundInfo: { current_round: 1 },
    generateRoundSceneImage: jest.fn().mockResolvedValue(undefined),
    setLastChoiceEffects: jest.fn(),
    ...overrides,
  });
};

describe('choiceUtils', () => {
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
  });

  describe('parseSSEError', () => {
    it('extracts message from error object', () => {
      const error = { message: 'Test error message' };
      expect(parseSSEError(error)).toBe('Test error message');
    });

    it('extracts error property', () => {
      const error = { error: 'Error from error property' };
      expect(parseSSEError(error)).toBe('Error from error property');
    });

    it('prefers message over error', () => {
      const error = { message: 'Message', error: 'Error' };
      expect(parseSSEError(error)).toBe('Message');
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

  describe('handleChoiceComplete', () => {
    it('sets summary when present', () => {
      const result = { summary: 'Round summary text' };

      handleChoiceComplete(result, mockHandlers);

      expect(mockHandlers.setRoundSummary).toHaveBeenCalledWith('Round summary text');
    });

    it('clears summary when not present', () => {
      const result = {};

      handleChoiceComplete(result, mockHandlers);

      expect(mockHandlers.setRoundSummary).toHaveBeenCalledWith(null);
    });

    it('enters summary phase on weekly summary', () => {
      const result = {
        need_weekly_summary: true,
        weekly_summary: 'Weekly summary text',
      };

      handleChoiceComplete(result, mockHandlers);

      expect(mockHandlers.setSummaryText).toHaveBeenCalledWith('Weekly summary text');
      expect(mockHandlers.setPhase).toHaveBeenCalledWith('summary');
    });

    it('enters ending phase on game over', () => {
      const result = { game_over: true };

      handleChoiceComplete(result, mockHandlers);

      expect(mockHandlers.setPhase).toHaveBeenCalledWith('ending');
      expect(mockHandlers.setGameOver).toHaveBeenCalledWith(true);
    });

    it('enters result phase by default', () => {
      const result = {};

      handleChoiceComplete(result, mockHandlers);

      expect(mockHandlers.setOptions).toHaveBeenCalledWith([]);
      expect(mockHandlers.setPhase).toHaveBeenCalledWith('result');
    });

    it('clears current event', () => {
      const result = {};

      handleChoiceComplete(result, mockHandlers);

      expect(mockHandlers.setCurrentEvent).toHaveBeenCalledWith(null);
    });

    it('clears processing state', () => {
      const result = {};

      handleChoiceComplete(result, mockHandlers);

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
      const mockSyncPlayerState = jest.fn().mockResolvedValue({
        player_state: {
          round_history: [
            { story_continuation: 'The story continues...' },
          ],
        },
      });
      (useGameStore.getState as jest.Mock).mockReturnValue({
        syncPlayerState: mockSyncPlayerState,
        storyText: 'Current story',
      });

      await handleChoiceAlreadyProcessed('Option text', mockHandlers, 'test');

      expect(mockHandlers.setPhase).toHaveBeenCalledWith('result');
    });
  });

  describe('handleNoCurrentEvent', () => {
    it('handles no current event error', async () => {
      const mockSyncPlayerState = jest.fn().mockResolvedValue({
        player_state: {
          round_history: [],
        },
      });
      (useGameStore.getState as jest.Mock).mockReturnValue({
        syncPlayerState: mockSyncPlayerState,
        storyText: 'Current story',
      });

      await handleNoCurrentEvent('Choice text', mockHandlers, 'test');

      expect(mockHandlers.setPhase).toHaveBeenCalledWith('result');
    });
  });

  describe('handleFallbackChoice', () => {
    it('uses option index for fallback', async () => {
      const mockResult = {
        summary: 'Fallback result',
        need_weekly_summary: false,
        game_over: false,
      };
      (gameplay.makeChoiceSync as jest.Mock).mockResolvedValue(mockResult);

      const context: ChoiceErrorContext = {
        optionIndex: 0,
        isRetry: false,
        sseSucceeded: false,
      };

      const result = await handleFallbackChoice(123, context, mockHandlers, 'test');

      expect(gameplay.makeChoiceSync).toHaveBeenCalledWith(123, { option_index: 0 });
      // Verify that the fallback was attempted
      expect(gameplay.makeChoiceSync).toHaveBeenCalled();
    });

    it('uses custom text for fallback', async () => {
      const mockResult = {
        summary: 'Custom result',
        need_weekly_summary: false,
        game_over: false,
      };
      (gameplay.makeCustomChoiceSync as jest.Mock).mockResolvedValue(mockResult);

      const context: ChoiceErrorContext = {
        customText: 'Custom action',
        isRetry: false,
        sseSucceeded: false,
      };

      const result = await handleFallbackChoice(123, context, mockHandlers, 'test');

      expect(gameplay.makeCustomChoiceSync).toHaveBeenCalledWith(123, { custom_text: 'Custom action' });
      // Verify that the fallback was attempted
      expect(gameplay.makeCustomChoiceSync).toHaveBeenCalled();
    });

    it('returns false without option or custom text', async () => {
      const context: ChoiceErrorContext = {
        isRetry: false,
        sseSucceeded: false,
      };

      const result = await handleFallbackChoice(123, context, mockHandlers, 'test');

      expect(result).toBe(false);
    });

    it('handles fallback failure with no current event', async () => {
      // Mock the error as an object with message property to ensure parseSSEError works correctly
      (gameplay.makeChoiceSync as jest.Mock).mockRejectedValue({ message: 'No current event' });

      const context: ChoiceErrorContext = {
        optionIndex: 0,
        isRetry: false,
        sseSucceeded: false,
      };

      const result = await handleFallbackChoice(123, context, mockHandlers, 'test');

      expect(result).toBe(true);
      expect(mockHandlers.setPhase).toHaveBeenCalledWith('result');
    });

    it('handles fallback failure with other error', async () => {
      (gameplay.makeChoiceSync as jest.Mock).mockRejectedValue(new Error('Network error'));

      const context: ChoiceErrorContext = {
        optionIndex: 0,
        isRetry: false,
        sseSucceeded: false,
      };

      const result = await handleFallbackChoice(123, context, mockHandlers, 'test');

      expect(result).toBe(false);
    });
  });

  describe('handleChoiceError', () => {
    it('handles choice_already_processed error', async () => {
      const mockSyncPlayerState = jest.fn().mockResolvedValue({
        player_state: { round_history: [] },
      });
      (useGameStore.getState as jest.Mock).mockReturnValue({
        syncPlayerState: mockSyncPlayerState,
        storyText: 'Story',
        currentEvent: { options: [{ text: 'Option 1' }] },
      });

      const context: ChoiceErrorContext = {
        optionIndex: 0,
        isRetry: false,
        sseSucceeded: false,
      };

      await handleChoiceError(
        { message: 'choice_already_processed' },
        123,
        mockHandlers,
        context,
        'test'
      );

      expect(mockHandlers.setPhase).toHaveBeenCalledWith('result');
    });

    it('handles No current event error', async () => {
      const mockSyncPlayerState = jest.fn().mockResolvedValue({
        player_state: { round_history: [] },
      });
      (useGameStore.getState as jest.Mock).mockReturnValue({
        syncPlayerState: mockSyncPlayerState,
        storyText: 'Story',
        currentEvent: { options: [{ text: 'Option 1' }] },
      });

      const context: ChoiceErrorContext = {
        optionIndex: 0,
        isRetry: false,
        sseSucceeded: false,
      };

      await handleChoiceError(
        { message: 'No current event found' },
        123,
        mockHandlers,
        context,
        'test'
      );

      expect(mockHandlers.setPhase).toHaveBeenCalledWith('result');
    });

    it('handles session expired (404)', async () => {
      const mockSyncState = jest.fn().mockResolvedValue(undefined);
      (useGameStore.getState as jest.Mock).mockReturnValue({
        syncState: mockSyncState,
        syncPlayerState: jest.fn(),
        currentEvent: null,
        storyText: 'Story',
      });

      const context: ChoiceErrorContext = {
        optionIndex: 0,
        isRetry: false,
        sseSucceeded: false,
        retryChoice: jest.fn(),
      };

      await handleChoiceError(
        { message: '404 Not Found' },
        123,
        mockHandlers,
        context,
        'test'
      );

      expect(mockHandlers.setProcessing).toHaveBeenCalledWith(true, '恢复游戏状态...');
    });

    it('handles fallback when SSE not succeeded', async () => {
      (gameplay.makeChoiceSync as jest.Mock).mockResolvedValue({
        summary: 'Result',
        need_weekly_summary: false,
        game_over: false,
      });

      const context: ChoiceErrorContext = {
        optionIndex: 0,
        isRetry: false,
        sseSucceeded: false,
      };

      await handleChoiceError(
        { message: 'Some error' },
        123,
        mockHandlers,
        context,
        'test'
      );

      expect(gameplay.makeChoiceSync).toHaveBeenCalled();
    });

    it('sets error phase for unhandled errors', async () => {
      const context: ChoiceErrorContext = {
        optionIndex: 0,
        isRetry: true,
        sseSucceeded: true,
      };

      await handleChoiceError(
        { message: 'Unknown error' },
        123,
        mockHandlers,
        context,
        'test'
      );

      expect(mockHandlers.setProcessing).toHaveBeenCalledWith(false);
      expect(mockHandlers.setConnectionStatus).toHaveBeenCalledWith('error');
      expect(mockHandlers.setPhase).toHaveBeenCalledWith('error');
    });
  });
});
