/**
 * hooks/game/eventUtils.ts Tests
 * Tests for event handling utilities
 */
import {
  selectFinalStory,
  streamRemainingText,
  handleEventComplete,
  handleStatusUpdate,
  EventHandlers,
  EventData,
} from '@/hooks/game/eventUtils';
import { useGameStore } from '@/stores/useGameStore';
import { spyOnStoreMethods } from '@/__tests__/helpers/store-spy';

const STORE_METHODS = ['generateRoundSceneImage'] as const;

function setupDefaultState(overrides: Record<string, unknown> = {}) {
  useGameStore.setState({
    storyText: 'Frontend story text',
    currentEvent: {
      story: 'Event story',
      options: [{ text: 'Old Option' }],
    },
    roundInfo: { current_round: 1 },
    enableSceneImage: true,
    ...overrides,
  } as never);
}

type StoreSpy = ReturnType<typeof spyOnStoreMethods<typeof useGameStore, (typeof STORE_METHODS)[number]>>;

describe('eventUtils', () => {
  let storeSpy: StoreSpy;
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
    setupDefaultState();
    storeSpy = spyOnStoreMethods(useGameStore, STORE_METHODS);
  });

  afterEach(() => {
    storeSpy.restore();
    jest.useRealTimers();
  });

  describe('selectFinalStory', () => {
    it('uses backend story when frontend is very short (< 10 chars)', () => {
      const result = selectFinalStory('This is a longer backend story with more content', 'Short');
      expect(result.useBackend).toBe(true);
      expect(result.finalStory).toBe('This is a longer backend story with more content');
    });

    it('uses backend story when frontend is very short', () => {
      const result = selectFinalStory('Backend', 'Hi');
      expect(result.useBackend).toBe(true);
    });

    it('uses frontend story when frontend is long enough (>= 10 chars)', () => {
      const result = selectFinalStory('Short', 'This is a longer frontend story');
      expect(result.useBackend).toBe(false);
      expect(result.finalStory).toBe('This is a longer frontend story');
    });

    it('returns remainingText when backend is longer but frontend is long enough', () => {
      const result = selectFinalStory('This is the complete backend story', 'This is the');
      expect(result.useBackend).toBe(false);
      expect(result.finalStory).toBe('This is the');
      expect(result.remainingText).toBe(' complete backend story');
    });

    it('handles empty backend story', () => {
      const result = selectFinalStory('', 'Frontend story');
      expect(result.useBackend).toBe(false);
      expect(result.finalStory).toBe('Frontend story');
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
      expect(appendStoryText).toHaveBeenCalledWith('Hel');
      act(() => { jest.advanceTimersByTime(10); });
      expect(appendStoryText).toHaveBeenCalledWith('lo ');
      act(() => { jest.advanceTimersByTime(10); });
      expect(appendStoryText).toHaveBeenCalledWith('Wor');
    });

    it('calls onComplete when done', () => {
      const appendStoryText = jest.fn();
      const onComplete = jest.fn();
      streamRemainingText('Hi', appendStoryText, onComplete, 1, 10);
      act(() => { jest.advanceTimersByTime(10); });
      act(() => { jest.advanceTimersByTime(10); });
      act(() => { jest.advanceTimersByTime(10); });
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
      handleEventComplete({ game_over: true } as Record<string, unknown>, mockHandlers);
      expect(mockHandlers.setPhase).toHaveBeenCalledWith('ending');
      expect(mockHandlers.setGameOver).toHaveBeenCalledWith(true);
      expect(mockHandlers.setProcessing).toHaveBeenCalledWith(false);
    });

    it('handles no options error', () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      handleEventComplete({ options: [] } as Record<string, unknown>, mockHandlers);
      expect(consoleSpy).toHaveBeenCalledWith('[onComplete] No options in complete event');
      expect(mockHandlers.setConnectionStatus).toHaveBeenCalledWith('error');
      expect(mockHandlers.setPhase).toHaveBeenCalledWith('error');
      consoleSpy.mockRestore();
    });

    it('does not expose options when complete payload has no recoverable story body', () => {
      const data: EventData = {
        event_description: '',
        story: '',
        options: [{ text: 'Option without story' }],
      };

      setupDefaultState({
        storyText: '',
        currentEvent: null,
      });

      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();

      handleEventComplete(data as Record<string, unknown>, mockHandlers);

      expect(consoleSpy).toHaveBeenCalledWith('[onComplete] No story text in complete event');
      expect(mockHandlers.setOptions).not.toHaveBeenCalledWith([{ text: 'Option without story' }]);
      expect(mockHandlers.setCurrentEvent).not.toHaveBeenCalledWith({
        story: '',
        options: [{ text: 'Option without story' }],
      });
      expect(mockHandlers.setPhase).not.toHaveBeenCalledWith('options');
      expect(mockHandlers.setConnectionStatus).toHaveBeenCalledWith('error');
      expect(mockHandlers.setPhase).toHaveBeenCalledWith('error');

      consoleSpy.mockRestore();
    });

    it('sets options phase with valid data', () => {
      setupDefaultState({ storyText: '', currentEvent: null });
      const data = { event_description: 'A new story event', options: [{ text: 'Option 1' }, { text: 'Option 2' }] };
      handleEventComplete(data as Record<string, unknown>, mockHandlers);
      expect(mockHandlers.setPhase).toHaveBeenCalledWith('options');
      expect(mockHandlers.setOptions).toHaveBeenCalled();
      expect(mockHandlers.setRoundSummary).toHaveBeenCalledWith(null);
    });

    it('clears processing state', () => {
      setupDefaultState({ storyText: '', currentEvent: null });
      handleEventComplete({ event_description: 'Story', options: [{ text: 'Option' }] } as Record<string, unknown>, mockHandlers);
      expect(mockHandlers.setProcessing).toHaveBeenCalledWith(false);
      expect(mockHandlers.setConnectionStatus).toHaveBeenCalledWith(null);
      expect(mockHandlers.generatingRef.current).toBe(false);
    });

    it('uses backend story when longer', () => {
      setupDefaultState({ storyText: 'Short', currentEvent: null });
      handleEventComplete({ event_description: 'A very long backend story that is definitely longer', options: [{ text: 'Option' }] } as Record<string, unknown>, mockHandlers);
      expect(mockHandlers.setStoryText).toHaveBeenCalledWith('A very long backend story that is definitely longer');
    });

    it('prefers event_description over story', () => {
      setupDefaultState({ storyText: '', currentEvent: null });
      handleEventComplete({ event_description: 'Event description', story: 'Story field', options: [{ text: 'Option' }] } as Record<string, unknown>, mockHandlers);
      expect(mockHandlers.setStoryText).toHaveBeenCalledWith('Event description');
    });

    it('replaces raw streamed frontend text with normalized backend complete story', () => {
      const data: EventData = {
        event_description: '你推开门。雨声停了。',
        options: [{ text: '继续追查' }],
      };

      setupDefaultState({
        storyText: '【内部状态】energy -5\n你推开门 . 雨声停了',
        currentEvent: null,
      });

      handleEventComplete(data as Record<string, unknown>, mockHandlers);

      expect(mockHandlers.setStoryText).toHaveBeenCalledWith('你推开门。雨声停了。');
      expect(mockHandlers.setCurrentEvent).toHaveBeenCalledWith({
        story: '你推开门。雨声停了。',
        options: [{ text: '继续追查' }],
      });
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
      const setStateSpy = jest.spyOn(useGameStore, 'setState');
      handleStatusUpdate({ phase: 'retry' }, setProcessing);
      expect(setStateSpy).toHaveBeenCalledWith({ storyText: '' });
      expect(setProcessing).toHaveBeenCalledWith(true, 'retrying');
      setStateSpy.mockRestore();
    });

    it('passes through other status phases', () => {
      const setProcessing = jest.fn();
      handleStatusUpdate({ phase: 'generating_story' }, setProcessing);
      expect(setProcessing).toHaveBeenCalledWith(true, 'generating_story');
    });
  });

  describe('Edge cases', () => {
    it('handles undefined options in data', () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      handleEventComplete({ event_description: 'Story', options: undefined } as Record<string, unknown>, mockHandlers);
      expect(consoleSpy).toHaveBeenCalled();
      consoleSpy.mockRestore();
    });

    it('handles null current event', () => {
      setupDefaultState({ storyText: 'Frontend', currentEvent: null });
      handleEventComplete({ event_description: 'Story', options: [{ text: 'Option' }] } as Record<string, unknown>, mockHandlers);
      expect(mockHandlers.setOptions).toHaveBeenCalled();
    });

    it('handles streaming remaining text', () => {
      setupDefaultState({ storyText: 'Full backend story', currentEvent: null });
      handleEventComplete({ event_description: 'Full backend story that is longer than frontend', options: [{ text: 'Option' }] } as Record<string, unknown>, mockHandlers);
      expect(mockHandlers.setOptions).toHaveBeenCalled();
    });

    it('handles optionsChanged and storyChanged', () => {
      setupDefaultState({
        storyText: 'Old story',
        currentEvent: { story: 'Old story', options: [{ text: 'Old Option' }] },
        enableSceneImage: false,
      });
      handleEventComplete({ event_description: 'New story', options: [{ text: 'New Option' }] } as Record<string, unknown>, mockHandlers);
      expect(mockHandlers.setOptions).toHaveBeenCalled();
      expect(mockHandlers.setStoryText).toHaveBeenCalled();
      expect(mockHandlers.setCurrentEvent).toHaveBeenCalled();
    });

    it('handles when options and story are unchanged', () => {
      setupDefaultState({
        storyText: 'Same story',
        currentEvent: { story: 'Same story', options: [{ text: 'Same Option' }] },
        enableSceneImage: false,
      });
      handleEventComplete({ event_description: 'Same story', options: [{ text: 'Same Option' }] } as Record<string, unknown>, mockHandlers);
      jest.advanceTimersByTime(600);
      expect(mockHandlers.setPhase).toHaveBeenCalledWith('options');
    });

    it('triggers scene image generation when enabled', () => {
      storeSpy.spies.generateRoundSceneImage.mockResolvedValue(undefined);
      setupDefaultState({ storyText: 'Old story', currentEvent: null, enableSceneImage: true });
      handleEventComplete({ event_description: 'New story', options: [{ text: 'Option' }] } as Record<string, unknown>, mockHandlers);
      expect(mockHandlers.setPhase).toHaveBeenCalledWith('options');
    });

    it('handles remainingText streaming path', () => {
      setupDefaultState({ storyText: 'A very long backend story that exceeds', currentEvent: null, enableSceneImage: false });
      handleEventComplete({
        event_description: 'A very long backend story that exceeds the frontend story length by a significant amount',
        options: [{ text: 'Option' }],
      } as Record<string, unknown>, mockHandlers);
      expect(mockHandlers.setOptions).toHaveBeenCalled();
    });

    it('handles scene image generation with no roundInfo', () => {
      setupDefaultState({ storyText: '', currentEvent: null, roundInfo: null, enableSceneImage: true });
      handleEventComplete({ event_description: 'Story', options: [{ text: 'Option' }] } as Record<string, unknown>, mockHandlers);
      expect(mockHandlers.setPhase).toHaveBeenCalledWith('options');
    });

    it('handles scene image generation with negative round', () => {
      setupDefaultState({ storyText: '', currentEvent: null, roundInfo: { current_round: -1 }, enableSceneImage: true });
      handleEventComplete({ event_description: 'Story', options: [{ text: 'Option' }] } as Record<string, unknown>, mockHandlers);
      expect(mockHandlers.setPhase).toHaveBeenCalledWith('options');
    });
  });

  describe('selectFinalStory remainingText branch', () => {
    it('returns remainingText when frontend is a prefix of backend', () => {
      const result = selectFinalStory('This is a frontend story that is longer', 'This is a frontend');
      expect(result.useBackend).toBe(false);
      expect(result.finalStory).toBe('This is a frontend');
      expect(result.remainingText).toBe(' story that is longer');
    });

    it('uses backend when frontend is not a prefix of backend (divergence)', () => {
      const result = selectFinalStory('This is a backend story that is longer than the frontend story', 'This is a frontend');
      expect(result.useBackend).toBe(true);
      expect(result.finalStory).toBe('This is a backend story that is longer than the frontend story');
      expect(result.remainingText).toBeUndefined();
    });

    it('preserves frontend story when substantial content exists (>100 chars) despite divergence', () => {
      const result = selectFinalStory('Backend fallback story that diverged from frontend', 'A'.repeat(150));
      expect(result.useBackend).toBe(false);
      expect(result.finalStory).toBe('A'.repeat(150));
    });

    it('uses frontend when it is longer than backend', () => {
      const result = selectFinalStory('Short', 'This is a longer frontend story');
      expect(result.useBackend).toBe(false);
      expect(result.finalStory).toBe('This is a longer frontend story');
      expect(result.remainingText).toBeUndefined();
    });

    it('uses backend when frontend is very short', () => {
      const result = selectFinalStory('Backend story here', 'Short');
      expect(result.useBackend).toBe(true);
      expect(result.finalStory).toBe('Backend story here');
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
      jest.isolateModules(() => {
        const { checkAndClearRetry } = require('@/hooks/game/eventUtils');
        const result = checkAndClearRetry();
        expect(result).toBe(false);
      });
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
      jest.isolateModules(() => {
        const { useGameStore } = require('@/stores/useGameStore');
        useGameStore.setState({ storyText: 'Short', currentEvent: null } as never);

        const { markRetry, handleEventComplete: localHandleEventComplete } = require('@/hooks/game/eventUtils');
        jest.spyOn(console, 'log').mockImplementation();
        markRetry();

        const localHandlers = {
          setStoryText: jest.fn(), setOptions: jest.fn(), setCurrentEvent: jest.fn(),
          setPhase: jest.fn(), setGameOver: jest.fn(), setRoundSummary: jest.fn(),
          setProcessing: jest.fn(), setConnectionStatus: jest.fn(), appendStoryText: jest.fn(),
          generatingRef: { current: true }, isRetryingRef: { current: false },
        };

        localHandleEventComplete({
          event_description: 'Backend story after retry',
          options: [{ text: 'Option' }],
        } as Record<string, unknown>, localHandlers);

        expect(localHandlers.setStoryText).toHaveBeenCalledWith('Backend story after retry');
        expect(localHandlers.setPhase).toHaveBeenCalledWith('options');
      });
    });

    it('uses frontend story when retry detected but backend returns fallback', () => {
      jest.isolateModules(() => {
        const { useGameStore } = require('@/stores/useGameStore');
        useGameStore.setState({ storyText: 'A'.repeat(200), currentEvent: null } as never);

        const { markRetry, handleEventComplete: localHandleEventComplete } = require('@/hooks/game/eventUtils');
        jest.spyOn(console, 'log').mockImplementation();
        markRetry();

        const localHandlers = {
          setStoryText: jest.fn(), setOptions: jest.fn(), setCurrentEvent: jest.fn(),
          setPhase: jest.fn(), setGameOver: jest.fn(), setRoundSummary: jest.fn(),
          setProcessing: jest.fn(), setConnectionStatus: jest.fn(), appendStoryText: jest.fn(),
          generatingRef: { current: true }, isRetryingRef: { current: false },
        };

        localHandleEventComplete({
          event_description: '这一天平静地度过了。',
          options: [{ text: '继续前进' }, { text: '思考一下' }],
        } as Record<string, unknown>, localHandlers);

        expect(localHandlers.setProcessing).toHaveBeenCalledWith(false);
        expect(localHandlers.setStoryText).toHaveBeenCalledWith('A'.repeat(200));
        expect(localHandlers.setPhase).toHaveBeenCalledWith('options');
      });
    });

    it('keeps long retry stream when backend complete only returns a short event summary', () => {
      jest.isolateModules(() => {
        const { useGameStore } = require('@/stores/useGameStore');
        const streamedStory = [
          '第1周·周一 晨光与抉择',
          '清晨七点半，上海的天空还带着冬日特有的灰蓝色调。',
          '许知夏站在租住的小公寓窗前，反复权衡独立游戏路演、搭档林悦的提醒，以及陆一鸣对声音叙事的建议。',
          '她把《第七封来信》的主题旋律重新拆成三段，让玩家先听见角色的犹豫，再听见城市的雨声。',
        ].join('\n').repeat(10);
        useGameStore.setState({ storyText: streamedStory, currentEvent: null } as never);

        const { markRetry, handleEventComplete: localHandleEventComplete } = require('@/hooks/game/eventUtils');
        jest.spyOn(console, 'log').mockImplementation();
        markRetry();

        const localHandlers = {
          setStoryText: jest.fn(), setOptions: jest.fn(), setCurrentEvent: jest.fn(),
          setPhase: jest.fn(), setGameOver: jest.fn(), setRoundSummary: jest.fn(),
          setProcessing: jest.fn(), setConnectionStatus: jest.fn(), appendStoryText: jest.fn(),
          generatingRef: { current: true }, isRetryingRef: { current: false },
        };
        const options = [{ text: '细读合作条款' }, { text: '请伙伴一起把关' }, { text: '先锁定关键风险' }];
        const shortSummary = [
          '在21世纪20年代的上海，中国独立游戏产业蓬勃发展，数字创意与音乐艺术交汇的时代。',
          '玩家作为独立游戏开发者，身处科技与人文交织的都市，关注叙事设计与音乐创作，追求个人表达与商业创新的平衡。',
          '周初，许知夏没有遇到突发的巨大转折，但生活仍然留下了需要判断的细节。',
          '她需要确认身边人的态度，并衡量接下来要投入多少精力。',
        ].join('');

        localHandleEventComplete({
          event_description: shortSummary,
          options,
        } as Record<string, unknown>, localHandlers);

        expect(localHandlers.setStoryText).toHaveBeenCalledWith(streamedStory);
        expect(localHandlers.setCurrentEvent).toHaveBeenCalledWith({ story: streamedStory, options });
        expect(localHandlers.setPhase).toHaveBeenCalledWith('options');
      });
    });
  });

  describe('Scene image generation branches', () => {
    it('generates scene image when roundNumber is 0', () => {
      storeSpy.spies.generateRoundSceneImage.mockResolvedValue(undefined);
      setupDefaultState({ storyText: '', currentEvent: null, roundInfo: { current_round: 0 }, enableSceneImage: true });
      handleEventComplete({ event_description: 'Story', options: [{ text: 'Option' }] } as Record<string, unknown>, mockHandlers);
      expect(mockHandlers.setPhase).toHaveBeenCalledWith('options');
    });

    it('does not generate scene image when enableSceneImage is false', () => {
      const mockGenerateScene = jest.fn().mockResolvedValue(undefined);
      const store = useGameStore.getState() as Record<string, unknown>;
      store.generateRoundSceneImage = mockGenerateScene;
      setupDefaultState({ storyText: '', currentEvent: null, enableSceneImage: false });
      handleEventComplete({ event_description: 'Story', options: [{ text: 'Option' }] } as Record<string, unknown>, mockHandlers);
      expect(mockGenerateScene).not.toHaveBeenCalled();
      store.generateRoundSceneImage = storeSpy.spies.generateRoundSceneImage;
    });

    it('does not generate scene image when storyText is empty', () => {
      const mockGenerateScene = jest.fn().mockResolvedValue(undefined);
      const store = useGameStore.getState() as Record<string, unknown>;
      store.generateRoundSceneImage = mockGenerateScene;
      setupDefaultState({ storyText: '', currentEvent: null, enableSceneImage: true });
      handleEventComplete({ event_description: '', options: [{ text: 'Option' }] } as Record<string, unknown>, mockHandlers);
      expect(mockGenerateScene).not.toHaveBeenCalled();
      store.generateRoundSceneImage = storeSpy.spies.generateRoundSceneImage;
    });

    it('handles scene image generation error gracefully', () => {
      const store = useGameStore.getState() as Record<string, unknown>;
      store.generateRoundSceneImage = jest.fn().mockRejectedValue(new Error('Image generation failed'));
      setupDefaultState({ storyText: '', currentEvent: null, enableSceneImage: true });
      expect(() => {
        handleEventComplete({ event_description: 'Story', options: [{ text: 'Option' }] } as Record<string, unknown>, mockHandlers);
      }).not.toThrow();
      expect(mockHandlers.setPhase).toHaveBeenCalledWith('options');
      store.generateRoundSceneImage = storeSpy.spies.generateRoundSceneImage;
    });
  });

  describe('streamRemainingText edge cases', () => {
    it('handles single character text', () => {
      const appendStoryText = jest.fn();
      const onComplete = jest.fn();
      streamRemainingText('A', appendStoryText, onComplete, 1, 10);
      expect(appendStoryText).toHaveBeenCalledWith('A');
      act(() => { jest.advanceTimersByTime(10); });
      expect(onComplete).toHaveBeenCalled();
    });

    it('handles text shorter than chunk size', () => {
      const appendStoryText = jest.fn();
      const onComplete = jest.fn();
      streamRemainingText('Hi', appendStoryText, onComplete, 10, 10);
      expect(appendStoryText).toHaveBeenCalledWith('Hi');
      act(() => { jest.advanceTimersByTime(10); });
      expect(onComplete).toHaveBeenCalled();
    });

    it('handles exact chunk size text', () => {
      const appendStoryText = jest.fn();
      const onComplete = jest.fn();
      streamRemainingText('ABC', appendStoryText, onComplete, 3, 10);
      expect(appendStoryText).toHaveBeenCalledWith('ABC');
      act(() => { jest.advanceTimersByTime(10); });
      expect(onComplete).toHaveBeenCalled();
    });
  });
});

function act(fn: () => void) {
  fn();
}
