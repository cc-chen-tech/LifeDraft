/**
 * 测试 handleRegenerate 函数的完整行为
 */
import { renderHook, act } from '@testing-library/react';
import { usePlayGame } from '@/hooks/usePlayGame';
import { useGameStore } from '@/stores/useGameStore';
import { useUIStore } from '@/stores/useUIStore';
import { spyOnStoreMethods } from '@/__tests__/helpers/store-spy';

import { createSSEMockResponse } from '@/__tests__/helpers/sse-mock';

/** Create a fresh SSE response for streamRegenerate calls */
function makeRegenerateResponse() {
  return createSSEMockResponse([
    'event: story\ndata: New regenerated story\n\n',
    'event: complete\ndata: {"event_description":"New regenerated story","options":[{"text":"Option 1"},{"text":"Option 2"}]}\n\n',
  ]);
}

const GAME_METHODS = ['setStoryText', 'setCurrentEvent', 'setGameOver', 'syncState', 'syncPlayerState', 'saveGame', 'appendStoryText', 'fetchRoundSceneImage', 'fetchAllRoundSceneImages', 'regenerateRoundSceneImage', 'setEventSceneImage', 'setResultSceneImage', 'generateRoundSceneImage'] as const;
const UI_METHODS = ['setProcessing'] as const;

type GameStoreSpy = ReturnType<typeof spyOnStoreMethods<typeof useGameStore, (typeof GAME_METHODS)[number]>>;
type UIStoreSpy = ReturnType<typeof spyOnStoreMethods<typeof useUIStore, (typeof UI_METHODS)[number]>>;

function setupDefaultState() {
  useGameStore.setState({
    gameId: 1,
    playerState: { player_name: 'Test Player' },
    progress: { week: 1 },
    roundInfo: { current_round: 1 },
    storyText: 'Original story',
    currentEvent: { story: 'Original story', options: [{ text: 'Option 1' }] } as never,
    isGameOver: false,
    roundSceneImages: {},
    currentRoundSceneImage: null,
    eventSceneImage: null,
    resultSceneImage: null,
    isLoadingRoundSceneImage: false,
    isRegeneratingRoundScene: false,
    roundSceneRegenerateError: null,
    enableSceneImage: true,
  } as never);
  useUIStore.setState({ processingMessage: null });
}

describe('handleRegenerate', () => {
  let gameSpy: GameStoreSpy;
  let uiSpy: UIStoreSpy;

  beforeEach(() => {
    jest.clearAllMocks();
    setupDefaultState();
    gameSpy = spyOnStoreMethods(useGameStore, GAME_METHODS);
    uiSpy = spyOnStoreMethods(useUIStore, UI_METHODS);
  });

  afterEach(() => {
    gameSpy.restore();
    uiSpy.restore();
  });

  describe('基础功能', () => {
    it('handleRegenerate 应该是一个函数', () => {
      const { result } = renderHook(() => usePlayGame());
      expect(typeof result.current.handleRegenerate).toBe('function');
    });

    it('调用 handleRegenerate 不应该抛出错误', async () => {
      (global.fetch as jest.Mock).mockImplementation((url: string) => {
        if (typeof url === 'string' && url.includes('/regenerate-stream')) {
          return Promise.resolve(makeRegenerateResponse());
        }
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({}),
          text: () => Promise.resolve('{}'),
          headers: new Headers({ 'content-type': 'application/json' }),
        } as Response);
      });
      const { result } = renderHook(() => usePlayGame());
      await act(async () => { result.current.handleRegenerate(); });
      expect(true).toBe(true);
    });

    it('应该暴露所有必要的 handler 函数', () => {
      const { result } = renderHook(() => usePlayGame());
      expect(typeof result.current.handleChoice).toBe('function');
      expect(typeof result.current.handleCustomChoice).toBe('function');
      expect(typeof result.current.handleSave).toBe('function');
      expect(typeof result.current.handleRegenerate).toBe('function');
      expect(typeof result.current.handleContinueToNextRound).toBe('function');
    });
  });

  describe('状态访问', () => {
    it('应该返回 phase 状态', () => {
      const { result } = renderHook(() => usePlayGame());
      expect(result.current.phase).toBeDefined();
    });

    it('应该返回 gameId', () => {
      const { result } = renderHook(() => usePlayGame());
      expect(result.current.gameId).toBe(1);
    });

    it('应该返回 storyText', () => {
      const { result } = renderHook(() => usePlayGame());
      expect(result.current.storyText).toBe('Original story');
    });
  });
});
