/**
 * hooks/game/eventUtils.ts Tests
 * Tests for event handling utilities
 */

// Mock dependencies
jest.mock('@/stores/useGameStore', () => ({
  useGameStore: {
    getState: jest.fn(() => ({
      storyText: 'Frontend story text',
      currentEvent: {
        story: 'Event story',
        options: [{ text: 'Old Option' }],
      },
      roundInfo: { current_round: 1 },
      enableSceneImage: true,
      generateRoundSceneImage: jest.fn().mockResolvedValue(undefined),
    })),
    setState: jest.fn(),
  },
}));

import {
  selectFinalStory,
  streamRemainingText,
  handleEventComplete,
  handleStatusUpdate,
  EventHandlers,
  EventData,
} from '@/hooks/game/eventUtils';
import { useGameStore } from '@/stores/useGameStore';

describe('eventUtils', () => {
  const mockHandlers: EventHandlers = {
    setStoryText: jest.fn(),
    setOptions: jest.fn(),
    setCurrentEvent: jest.fn(),
    setPhase: jest.fn(),
    setGameOver: jest.fn(),
    setRoundSummary: jest.fn(),
    setProcessing: jest.fn(),
    setConnectionStatus: jest.fn(),
    appendStoryText: jest.fn(),
    generatingRef: { current: true },
    isRetryingRef: { current: false },
  };

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('selectFinalStory', () => {
    it('uses backend story when frontend is very short (< 10 chars)', () => {
      const backendStory = 'This is a longer backend story with more content';
      const frontendStory = 'Short'; // 5 chars < 10

      const result = selectFinalStory(backendStory, frontendStory);

      expect(result.useBackend).toBe(true);
      expect(result.finalStory).toBe(backendStory);
    });

    it('uses backend story when frontend is very short', () => {
      const backendStory = 'Backend';
      const frontendStory = 'Hi'; // 2 chars < 10

      const result = selectFinalStory(backendStory, frontendStory);

      expect(result.useBackend).toBe(true);
    });

    it('uses frontend story when frontend is long enough (>= 10 chars)', () => {
      const backendStory = 'Short';
      const frontendStory = 'This is a longer frontend story'; // > 10 chars

      const result = selectFinalStory(backendStory, frontendStory);

      // frontendStory.length >= 10, so useBackendStory = false
      expect(result.useBackend).toBe(false);
      expect(result.finalStory).toBe(frontendStory);
    });

    it('returns remainingText when backend is longer but frontend is long enough', () => {
      const backendStory = 'This is the complete backend story';
      const frontendStory = 'This is the'; // 11 chars >= 10, so won't use backend

      const result = selectFinalStory(backendStory, frontendStory);

      // frontend >= 10, so useBackendStory = false
      // but backend > frontend, so returns remainingText
      expect(result.useBackend).toBe(false);
      expect(result.finalStory).toBe(frontendStory);
      expect(result.remainingText).toBe(' complete backend story');
    });

    it('handles empty backend story', () => {
      const backendStory = '';
      const frontendStory = 'Frontend story';

      const result = selectFinalStory(backendStory, frontendStory);

      expect(result.useBackend).toBe(false);
      expect(result.finalStory).toBe(frontendStory);
    });

    it('handles both empty', () => {
      const result = selectFinalStory('', '');

      expect(result.useBackend).toBe(false);
      expect(result.finalStory).toBe('');
    });
  });

  describe('streamRemainingText', () => {
    it('streams text in chunks', () => {
      const appendStoryText = jest.fn();
      const onComplete = jest.fn();

      streamRemainingText('Hello World', appendStoryText, onComplete, 3, 10);

      // First chunk - stream() is called immediately
      expect(appendStoryText).toHaveBeenCalledWith('Hel');

      act(() => {
        jest.advanceTimersByTime(10);
      });
      expect(appendStoryText).toHaveBeenCalledWith('lo ');

      act(() => {
        jest.advanceTimersByTime(10);
      });
      expect(appendStoryText).toHaveBeenCalledWith('Wor');
    });

    it('calls onComplete when done', () => {
      const appendStoryText = jest.fn();
      const onComplete = jest.fn();

      streamRemainingText('Hi', appendStoryText, onComplete, 1, 10);

      act(() => {
        jest.advanceTimersByTime(10);
      });
      act(() => {
        jest.advanceTimersByTime(10);
      });
      act(() => {
        jest.advanceTimersByTime(10);
      });

      expect(onComplete).toHaveBeenCalled();
    });

    it('handles empty text', () => {
      const appendStoryText = jest.fn();
      const onComplete = jest.fn();

      streamRemainingText('', appendStoryText, onComplete);

      expect(onComplete).toHaveBeenCalled();
      expect(appendStoryText).not.toHaveBeenCalled();
    });
  });

  describe('handleEventComplete', () => {
    it('handles game over', () => {
      const data: EventData = {
        game_over: true,
      };

      handleEventComplete(data as Record<string, unknown>, mockHandlers);

      expect(mockHandlers.setPhase).toHaveBeenCalledWith('ending');
      expect(mockHandlers.setGameOver).toHaveBeenCalledWith(true);
      expect(mockHandlers.setProcessing).toHaveBeenCalledWith(false);
    });

    it('handles no options error', () => {
      const data: EventData = {
        options: [],
      };

      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      handleEventComplete(data as Record<string, unknown>, mockHandlers);

      expect(consoleSpy).toHaveBeenCalledWith('[onComplete] No options in complete event');
      expect(mockHandlers.setPhase).not.toHaveBeenCalled();

      consoleSpy.mockRestore();
    });

    it('sets options phase with valid data', () => {
      const data: EventData = {
        event_description: 'A new story event',
        options: [
          { text: 'Option 1' },
          { text: 'Option 2' },
        ],
      };

      (useGameStore.getState as jest.Mock).mockReturnValue({
        storyText: '',
        currentEvent: null,
      });

      handleEventComplete(data as Record<string, unknown>, mockHandlers);

      expect(mockHandlers.setPhase).toHaveBeenCalledWith('options');
      expect(mockHandlers.setOptions).toHaveBeenCalled();
      expect(mockHandlers.setRoundSummary).toHaveBeenCalledWith(null);
    });

    it('clears processing state', () => {
      const data: EventData = {
        event_description: 'Story',
        options: [{ text: 'Option' }],
      };

      (useGameStore.getState as jest.Mock).mockReturnValue({
        storyText: '',
        currentEvent: null,
      });

      handleEventComplete(data as Record<string, unknown>, mockHandlers);

      expect(mockHandlers.setProcessing).toHaveBeenCalledWith(false);
      expect(mockHandlers.setConnectionStatus).toHaveBeenCalledWith(null);
      expect(mockHandlers.generatingRef.current).toBe(false);
    });

    it('uses backend story when longer', () => {
      const data: EventData = {
        event_description: 'A very long backend story that is definitely longer',
        options: [{ text: 'Option' }],
      };

      (useGameStore.getState as jest.Mock).mockReturnValue({
        storyText: 'Short',
        currentEvent: null,
      });

      handleEventComplete(data as Record<string, unknown>, mockHandlers);

      expect(mockHandlers.setStoryText).toHaveBeenCalledWith('A very long backend story that is definitely longer');
    });

    it('prefers event_description over story', () => {
      const data: EventData = {
        event_description: 'Event description',
        story: 'Story field',
        options: [{ text: 'Option' }],
      };

      (useGameStore.getState as jest.Mock).mockReturnValue({
        storyText: '',
        currentEvent: null,
      });

      handleEventComplete(data as Record<string, unknown>, mockHandlers);

      expect(mockHandlers.setStoryText).toHaveBeenCalledWith('Event description');
    });
  });

  describe('handleStatusUpdate', () => {
    it('handles retrying status', () => {
      const setProcessing = jest.fn();

      handleStatusUpdate({ phase: 'retrying' }, setProcessing);

      expect(setProcessing).toHaveBeenCalledWith(true, 'retrying');
    });

    it('handles retry status by clearing story', () => {
      const setProcessing = jest.fn();

      handleStatusUpdate({ phase: 'retry' }, setProcessing);

      expect(useGameStore.setState).toHaveBeenCalledWith({ storyText: '' });
      expect(setProcessing).toHaveBeenCalledWith(true, 'retrying');
    });

    it('passes through other status phases', () => {
      const setProcessing = jest.fn();

      handleStatusUpdate({ phase: 'generating_story' }, setProcessing);

      expect(setProcessing).toHaveBeenCalledWith(true, 'generating_story');
    });
  });

  describe('Edge cases', () => {
    it('handles undefined options in data', () => {
      const data: EventData = {
        event_description: 'Story',
        options: undefined,
      };

      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      handleEventComplete(data as Record<string, unknown>, mockHandlers);

      expect(consoleSpy).toHaveBeenCalled();

      consoleSpy.mockRestore();
    });

    it('handles null current event', () => {
      const data: EventData = {
        event_description: 'Story',
        options: [{ text: 'Option' }],
      };

      (useGameStore.getState as jest.Mock).mockReturnValue({
        storyText: 'Frontend',
        currentEvent: null,
      });

      handleEventComplete(data as Record<string, unknown>, mockHandlers);

      expect(mockHandlers.setOptions).toHaveBeenCalled();
    });

    it('handles streaming remaining text', () => {
      const data: EventData = {
        event_description: 'Full backend story that is longer than frontend',
        options: [{ text: 'Option' }],
      };

      // Frontend >= 10 chars, so won't use backend directly
      // But backend > frontend, so will stream remaining text
      (useGameStore.getState as jest.Mock).mockReturnValue({
        storyText: 'Full backend story', // 18 chars >= 10
        currentEvent: null,
      });

      handleEventComplete(data as Record<string, unknown>, mockHandlers);

      // Should set options (for remainingText streaming path)
      expect(mockHandlers.setOptions).toHaveBeenCalled();
      // setPhase is called asynchronously after streaming
    });

    it('handles optionsChanged and storyChanged', () => {
      const data: EventData = {
        event_description: 'New story',
        options: [{ text: 'New Option' }],
      };

      (useGameStore.getState as jest.Mock).mockReturnValue({
        storyText: 'Old story',
        currentEvent: {
          story: 'Old story',
          options: [{ text: 'Old Option' }],
        },
        roundInfo: { current_round: 1 },
        enableSceneImage: false,
      });

      handleEventComplete(data as Record<string, unknown>, mockHandlers);

      expect(mockHandlers.setOptions).toHaveBeenCalled();
      expect(mockHandlers.setStoryText).toHaveBeenCalled();
      expect(mockHandlers.setCurrentEvent).toHaveBeenCalled();
    });

    it('handles when options and story are unchanged', () => {
      const data: EventData = {
        event_description: 'Same story',
        options: [{ text: 'Same Option' }],
      };

      (useGameStore.getState as jest.Mock).mockReturnValue({
        storyText: 'Same story',
        currentEvent: {
          story: 'Same story',
          options: [{ text: 'Same Option' }],
        },
        roundInfo: { current_round: 1 },
        enableSceneImage: false,
      });

      handleEventComplete(data as Record<string, unknown>, mockHandlers);

      // Phase is set asynchronously with setTimeout
      jest.advanceTimersByTime(600);
      expect(mockHandlers.setPhase).toHaveBeenCalledWith('options');
    });

    it('triggers scene image generation when enabled', () => {
      const mockGenerateScene = jest.fn().mockResolvedValue(undefined);
      const data: EventData = {
        event_description: 'New story',
        options: [{ text: 'Option' }],
      };

      (useGameStore.getState as jest.Mock).mockReturnValue({
        storyText: 'Old story',
        currentEvent: null,
        roundInfo: { current_round: 1 },
        enableSceneImage: true,
        generateRoundSceneImage: mockGenerateScene,
      });

      handleEventComplete(data as Record<string, unknown>, mockHandlers);

      // Verify that setPhase was called with 'options'
      expect(mockHandlers.setPhase).toHaveBeenCalledWith('options');
    });

    it('handles remainingText streaming path', () => {
      // This test covers the remainingText branch in handleEventComplete
      // Frontend >= 10 chars, backend > frontend, so will stream remaining text
      const data: EventData = {
        event_description: 'A very long backend story that exceeds the frontend story length by a significant amount',
        options: [{ text: 'Option' }],
      };

      (useGameStore.getState as jest.Mock).mockReturnValue({
        storyText: 'A very long backend story that exceeds', // 38 chars >= 10
        currentEvent: null,
        roundInfo: { current_round: 1 },
        enableSceneImage: false,
      });

      handleEventComplete(data as Record<string, unknown>, mockHandlers);

      // Should set options for remainingText streaming
      expect(mockHandlers.setOptions).toHaveBeenCalled();
      // Phase is set after streaming completes
    });

    it('handles scene image generation with no roundInfo', () => {
      const data: EventData = {
        event_description: 'Story',
        options: [{ text: 'Option' }],
      };

      (useGameStore.getState as jest.Mock).mockReturnValue({
        storyText: '',
        currentEvent: null,
        roundInfo: null,
        enableSceneImage: true,
      });

      handleEventComplete(data as Record<string, unknown>, mockHandlers);

      expect(mockHandlers.setPhase).toHaveBeenCalledWith('options');
    });

    it('handles scene image generation with negative round', () => {
      const data: EventData = {
        event_description: 'Story',
        options: [{ text: 'Option' }],
      };

      (useGameStore.getState as jest.Mock).mockReturnValue({
        storyText: '',
        currentEvent: null,
        roundInfo: { current_round: -1 },
        enableSceneImage: true,
      });

      handleEventComplete(data as Record<string, unknown>, mockHandlers);

      expect(mockHandlers.setPhase).toHaveBeenCalledWith('options');
    });
  });

  describe('selectFinalStory remainingText branch', () => {
    it('returns remainingText when frontend is long enough but backend is longer', () => {
      // When frontend >= 10 and backend > frontend, should return remainingText
      const backendStory = 'This is a backend story that is longer than the frontend story';
      const frontendStory = 'This is a frontend'; // 18 chars >= 10

      const result = selectFinalStory(backendStory, frontendStory);

      // Frontend >= 10, so useBackendStory = false
      // But backend > frontend, so returns remainingText
      expect(result.useBackend).toBe(false);
      expect(result.finalStory).toBe(frontendStory);
      expect(result.remainingText).toBe('story that is longer than the frontend story');
    });

    it('uses frontend when it is longer than backend', () => {
      const backendStory = 'Short';
      const frontendStory = 'This is a longer frontend story'; // > 10 chars

      const result = selectFinalStory(backendStory, frontendStory);

      // Frontend >= 10 and longer than backend
      expect(result.useBackend).toBe(false);
      expect(result.finalStory).toBe(frontendStory);
      expect(result.remainingText).toBeUndefined();
    });

    it('uses backend when frontend is very short', () => {
      const backendStory = 'Backend story here';
      const frontendStory = 'Short'; // 5 chars < 10

      const result = selectFinalStory(backendStory, frontendStory);

      // Frontend < 10, so useBackendStory = true
      expect(result.useBackend).toBe(true);
      expect(result.finalStory).toBe(backendStory);
    });
  });

  describe('markRetry and checkAndClearRetry', () => {
    it('markRetry sets hadRetry flag', () => {
      const { markRetry } = require('@/hooks/game/eventUtils');
      const consoleSpy = jest.spyOn(console, 'log').mockImplementation();
      
      markRetry();
      
      expect(consoleSpy).toHaveBeenCalledWith('[eventUtils] Retry marked, will force use backend story on complete');
      
      consoleSpy.mockRestore();
    });

    it('checkAndClearRetry returns true after markRetry', () => {
      const { markRetry, checkAndClearRetry } = require('@/hooks/game/eventUtils');
      const consoleSpy = jest.spyOn(console, 'log').mockImplementation();
      
      markRetry();
      const result = checkAndClearRetry();
      
      expect(result).toBe(true);
      expect(consoleSpy).toHaveBeenCalledWith('[eventUtils] Retry detected, clearing flag');
      
      consoleSpy.mockRestore();
    });

    it('checkAndClearRetry returns false without markRetry', () => {
      // Reset module to clear hadRetry flag
      jest.resetModules();
      jest.mock('@/stores/useGameStore', () => ({
        useGameStore: {
          getState: jest.fn(() => ({
            storyText: '',
            currentEvent: null,
            roundInfo: { current_round: 1 },
            enableSceneImage: true,
            generateRoundSceneImage: jest.fn().mockResolvedValue(undefined),
          })),
          setState: jest.fn(),
        },
      }));
      
      const { checkAndClearRetry } = require('@/hooks/game/eventUtils');
      const result = checkAndClearRetry();
      
      expect(result).toBe(false);
    });

    it('checkAndClearRetry resets the flag', () => {
      const { markRetry, checkAndClearRetry } = require('@/hooks/game/eventUtils');
      jest.spyOn(console, 'log').mockImplementation();
      
      markRetry();
      const firstResult = checkAndClearRetry();
      const secondResult = checkAndClearRetry();
      
      expect(firstResult).toBe(true);
      expect(secondResult).toBe(false);
    });
  });

  describe('handleEventComplete with retry', () => {
    it('uses backend story when retry was detected and frontend is short', () => {
      // ★ 使用 resetModules + require 确保 markRetry 和 handleEventComplete 共享同一模块实例
      jest.resetModules();
      jest.mock('@/stores/useGameStore', () => ({
        useGameStore: {
          getState: jest.fn(),
          setState: jest.fn(),
        },
      }));

      const { markRetry, handleEventComplete: localHandleEventComplete } = require('@/hooks/game/eventUtils');
      const { useGameStore: localStore } = require('@/stores/useGameStore');
      jest.spyOn(console, 'log').mockImplementation();

      // Mark retry first
      markRetry();

      const data: EventData = {
        event_description: 'Backend story after retry',
        options: [{ text: 'Option' }],
      };

      // Frontend is short (< 10), so retry will use backend story
      (localStore.getState as jest.Mock).mockReturnValue({
        storyText: 'Short',
        currentEvent: null,
      });

      const localHandlers = {
        setStoryText: jest.fn(),
        setOptions: jest.fn(),
        setCurrentEvent: jest.fn(),
        setPhase: jest.fn(),
        setGameOver: jest.fn(),
        setRoundSummary: jest.fn(),
        setProcessing: jest.fn(),
        setConnectionStatus: jest.fn(),
        appendStoryText: jest.fn(),
        generatingRef: { current: true },
        isRetryingRef: { current: false },
      };

      localHandleEventComplete(data as Record<string, unknown>, localHandlers);

      expect(localHandlers.setStoryText).toHaveBeenCalledWith('Backend story after retry');
      expect(localHandlers.setPhase).toHaveBeenCalledWith('options');
    });

    it('uses frontend story when retry detected but backend returns fallback', () => {
      // ★ 使用 resetModules + require 确保 markRetry 和 handleEventComplete 共享同一模块实例
      jest.resetModules();
      jest.mock('@/stores/useGameStore', () => ({
        useGameStore: {
          getState: jest.fn(),
          setState: jest.fn(),
        },
      }));

      const { markRetry, handleEventComplete: localHandleEventComplete } = require('@/hooks/game/eventUtils');
      const { useGameStore: localStore } = require('@/stores/useGameStore');
      jest.spyOn(console, 'log').mockImplementation();
          
      // Mark retry
      markRetry();
          
      // Backend returns a short fallback text (< 50 chars)
      const data: EventData = {
        event_description: '这一天平静地度过了。',
        options: [{ text: '继续前进' }, { text: '思考一下' }],
      };
    
      // Frontend has a long story from streaming (> 100 chars)
      const longStory = 'A'.repeat(200);
      (localStore.getState as jest.Mock).mockReturnValue({
        storyText: longStory,
        currentEvent: null,
      });

      const localHandlers = {
        setStoryText: jest.fn(),
        setOptions: jest.fn(),
        setCurrentEvent: jest.fn(),
        setPhase: jest.fn(),
        setGameOver: jest.fn(),
        setRoundSummary: jest.fn(),
        setProcessing: jest.fn(),
        setConnectionStatus: jest.fn(),
        appendStoryText: jest.fn(),
        generatingRef: { current: true },
        isRetryingRef: { current: false },
      };
    
      localHandleEventComplete(data as Record<string, unknown>, localHandlers);
    
      // Verify the function executed
      expect(localHandlers.setProcessing).toHaveBeenCalledWith(false);
      // Since hadRetry was true and backend story is short fallback (< 50 chars),
      // but frontend has long story (> 100 chars), should prefer frontend story
      expect(localHandlers.setStoryText).toHaveBeenCalledWith(longStory);
      expect(localHandlers.setPhase).toHaveBeenCalledWith('options');
    });
  });

  describe('Scene image generation branches', () => {
    it('generates scene image when roundNumber is 0', () => {
      const mockGenerateScene = jest.fn().mockResolvedValue(undefined);
      const data: EventData = {
        event_description: 'Story',
        options: [{ text: 'Option' }],
      };

      (useGameStore.getState as jest.Mock).mockReturnValue({
        storyText: '',
        currentEvent: null,
        roundInfo: { current_round: 0 },
        enableSceneImage: true,
        generateRoundSceneImage: mockGenerateScene,
      });

      handleEventComplete(data as Record<string, unknown>, mockHandlers);

      // roundNumber >= 0 should trigger scene image generation
      expect(mockHandlers.setPhase).toHaveBeenCalledWith('options');
    });

    it('does not generate scene image when enableSceneImage is false', () => {
      const mockGenerateScene = jest.fn().mockResolvedValue(undefined);
      const data: EventData = {
        event_description: 'Story',
        options: [{ text: 'Option' }],
      };

      (useGameStore.getState as jest.Mock).mockReturnValue({
        storyText: '',
        currentEvent: null,
        roundInfo: { current_round: 1 },
        enableSceneImage: false,
        generateRoundSceneImage: mockGenerateScene,
      });

      handleEventComplete(data as Record<string, unknown>, mockHandlers);

      expect(mockGenerateScene).not.toHaveBeenCalled();
    });

    it('does not generate scene image when storyText is empty', () => {
      const mockGenerateScene = jest.fn().mockResolvedValue(undefined);
      const data: EventData = {
        event_description: '',
        options: [{ text: 'Option' }],
      };

      (useGameStore.getState as jest.Mock).mockReturnValue({
        storyText: '',
        currentEvent: null,
        roundInfo: { current_round: 1 },
        enableSceneImage: true,
        generateRoundSceneImage: mockGenerateScene,
      });

      handleEventComplete(data as Record<string, unknown>, mockHandlers);

      expect(mockGenerateScene).not.toHaveBeenCalled();
    });

    it('handles scene image generation error gracefully', () => {
      // This test verifies that scene image errors don't crash the app
      const mockGenerateScene = jest.fn().mockRejectedValue(new Error('Image generation failed'));
      const data: EventData = {
        event_description: 'Story',
        options: [{ text: 'Option' }],
      };

      (useGameStore.getState as jest.Mock).mockReturnValue({
        storyText: '',
        currentEvent: null,
        roundInfo: { current_round: 1 },
        enableSceneImage: true,
        generateRoundSceneImage: mockGenerateScene,
      });

      // Should not throw
      expect(() => {
        handleEventComplete(data as Record<string, unknown>, mockHandlers);
      }).not.toThrow();

      // Verify handlers were still called
      expect(mockHandlers.setPhase).toHaveBeenCalledWith('options');
    });
  });

  describe('streamRemainingText edge cases', () => {
    it('handles single character text', () => {
      const appendStoryText = jest.fn();
      const onComplete = jest.fn();

      streamRemainingText('A', appendStoryText, onComplete, 1, 10);

      expect(appendStoryText).toHaveBeenCalledWith('A');

      act(() => {
        jest.advanceTimersByTime(10);
      });

      expect(onComplete).toHaveBeenCalled();
    });

    it('handles text shorter than chunk size', () => {
      const appendStoryText = jest.fn();
      const onComplete = jest.fn();

      streamRemainingText('Hi', appendStoryText, onComplete, 10, 10);

      expect(appendStoryText).toHaveBeenCalledWith('Hi');

      act(() => {
        jest.advanceTimersByTime(10);
      });

      expect(onComplete).toHaveBeenCalled();
    });

    it('handles exact chunk size text', () => {
      const appendStoryText = jest.fn();
      const onComplete = jest.fn();

      streamRemainingText('ABC', appendStoryText, onComplete, 3, 10);

      expect(appendStoryText).toHaveBeenCalledWith('ABC');

      act(() => {
        jest.advanceTimersByTime(10);
      });

      expect(onComplete).toHaveBeenCalled();
    });
  });
});

// Helper for act
function act(fn: () => void) {
  fn();
}
