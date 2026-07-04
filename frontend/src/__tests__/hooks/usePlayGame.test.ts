/**
 * Tests for usePlayGame hook
 * Tests session recovery, initialization, ending data, and scene images
 */
import { renderHook, act, waitFor } from '@testing-library/react';
import { useGameStore } from '@/stores/useGameStore';
import { spyOnStoreMethods } from '@/__tests__/helpers/store-spy';

// Mock the sub-hooks before importing usePlayGame
const mockPush = jest.fn();
const mockReplace = jest.fn();
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: mockReplace,
  }),
}));

// Import helpers for global.fetch mocking
import { jsonResponse, errorResponse } from '@/__tests__/helpers/fetch';
import { createSSEMockResponse } from '@/__tests__/helpers/sse-mock';

// -- Store method spying --
const STORE_METHODS = [
  'appendStoryText', 'setStoryText', 'setCurrentEvent', 'setGameOver',
  'syncState', 'syncPlayerState', 'saveGame',
  'fetchRoundSceneImage', 'fetchAllRoundSceneImages', 'regenerateRoundSceneImage',
  'setEventSceneImage', 'setResultSceneImage', 'generateRoundSceneImage',
] as const;

type StoreSpy = ReturnType<typeof spyOnStoreMethods<typeof useGameStore, (typeof STORE_METHODS)[number]>>;

function setupDefaultState() {
  useGameStore.setState({
    gameId: null,
    playerState: null,
    progress: null,
    roundInfo: null,
    storyText: '',
    currentEvent: null,
    isGameOver: false,
    roundSceneImages: [],
    currentRoundSceneImage: null,
    eventSceneImage: null,
    resultSceneImage: null,
    isLoadingRoundSceneImage: false,
    isRegeneratingRoundScene: false,
    roundSceneRegenerateError: null,
    enableSceneImage: true,
  } as never);
}

// Import after mocks
import { usePlayGame } from '@/hooks/usePlayGame';

describe('usePlayGame', () => {
  let storeSpy: StoreSpy;

  beforeEach(() => {
    jest.clearAllMocks();
    setupDefaultState();
    storeSpy = spyOnStoreMethods(useGameStore, STORE_METHODS);

    mockPush.mockClear();
    mockReplace.mockClear();
  });

  afterEach(() => {
    storeSpy.restore();
  });

  describe('Initial state', () => {
    it('returns initial values correctly', () => {
      const { result } = renderHook(() => usePlayGame());

      expect(result.current.phase).toBe('loading');
      expect(result.current.options).toEqual([]);
      expect(result.current.gameId).toBeNull();
      expect(result.current.hydrated).toBe(true);
    });

    it('returns hydrated state correctly', () => {
      const { result } = renderHook(() => usePlayGame());

      expect(result.current.hydrated).toBe(true);
    });
  });

  describe('Session Recovery', () => {
    it('redirects to home when no gameId and no active game on server', async () => {
      (global.fetch as jest.Mock).mockResolvedValue(errorResponse(404));

      renderHook(() => usePlayGame());

      await waitFor(() => {
        expect(mockReplace).toHaveBeenCalledWith('/');
      });
    });

    it('recovers session from server when no gameId in localStorage', async () => {
      const mockActiveGame = {
        game_id: 42,
        player_state: { player_name: 'TestPlayer', age: 25 },
        progress: { week: 5 },
        round_info: { current_round: 10 },
        current_event: {
          event_description: 'Test event',
          options: [{ text: 'Option 1' }],
        },
      };
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockActiveGame));

      renderHook(() => usePlayGame());

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith('/api/games/active', expect.objectContaining({ credentials: 'include' }));
      });
    });

    it('recovers completed active event story from story_text after refresh', async () => {
      const mockActiveGame = {
        game_id: 42,
        player_state: { player_name: 'TestPlayer', age: 25 },
        progress: { week: 2, current_round: 1, rounds_per_week: 3 },
        round_info: { current_round: 1, week: 2 },
        current_event: {
          story_text: '后端已完成的周二故事。',
          options: [{ text: '继续查账' }, { text: '去码头' }],
        },
      };
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockActiveGame));

      renderHook(() => usePlayGame());

      await waitFor(() => {
        expect(useGameStore.getState().storyText).toBe('后端已完成的周二故事。');
      });
      expect(useGameStore.getState().currentEvent).toEqual({
        story: '后端已完成的周二故事。',
        options: [{ text: '继续查账' }, { text: '去码头' }],
      });
    });

    it('exposes recovered active event through play UI state instead of staying in loading', async () => {
      const mockActiveGame = {
        game_id: 42,
        player_state: {
          player_name: '林见微',
          age: 25,
          current_round: 0,
          week: 0,
        },
        progress: { week: 0, current_round: 0, rounds_per_week: 3 },
        round_info: { current_round: 0, week: 0 },
        current_event: {
          event_description: '林见微推开书铺木门，掌柜从柜台后抬头。',
          options: [{ text: '询问掌柜' }, { text: '查看账册' }, { text: '退出书铺' }],
        },
      };
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockActiveGame));

      const { result } = renderHook(() => usePlayGame());

      await waitFor(() => {
        expect(result.current.storyText).toBe('林见微推开书铺木门，掌柜从柜台后抬头。');
      });
      expect(result.current.currentEvent).toEqual({
        story: '林见微推开书铺木门，掌柜从柜台后抬头。',
        options: [{ text: '询问掌柜' }, { text: '查看账册' }, { text: '退出书铺' }],
      });
      expect(result.current.options).toEqual([{ text: '询问掌柜' }, { text: '查看账册' }, { text: '退出书铺' }]);
      expect(result.current.phase).toBe('options');
      expect(mockReplace).not.toHaveBeenCalled();
    });

    it('recovers story from last_round_full_story', async () => {
      const mockActiveGame = {
        game_id: 42,
        player_state: {
          player_name: 'TestPlayer',
          last_round_full_story: 'Last round story content',
        },
        progress: { week: 5 },
        round_info: { current_round: 10 },
        current_event: null,
      };
      (global.fetch as jest.Mock).mockImplementation((url: string) => {
        if (url === '/api/games/active') {
          return Promise.resolve(jsonResponse(mockActiveGame));
        }
        // SSE event generation triggered because current_event is null
        return Promise.resolve(createSSEMockResponse([
          'event: complete\ndata: {"event_description":"Generated story","options":[{"text":"Option 1"}]}\n\n',
        ]));
      });

      renderHook(() => usePlayGame());

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith('/api/games/active', expect.objectContaining({ credentials: 'include' }));
      });
    });

    it('recovers story from round_history when no last_round_full_story', async () => {
      const mockActiveGame = {
        game_id: 42,
        player_state: {
          player_name: 'TestPlayer',
          round_history: [
            { event_description: 'Event 1', story_continuation: 'Story 1' },
            { event_description: 'Event 2', story_continuation: 'Story 2' },
          ],
        },
        progress: { week: 5 },
        round_info: { current_round: 10 },
        current_event: null,
      };
      (global.fetch as jest.Mock).mockImplementation((url: string) => {
        if (url === '/api/games/active') {
          return Promise.resolve(jsonResponse(mockActiveGame));
        }
        // SSE event generation triggered because current_event is null
        return Promise.resolve(createSSEMockResponse([
          'event: complete\ndata: {"event_description":"Generated story","options":[{"text":"Option 1"}]}\n\n',
        ]));
      });

      renderHook(() => usePlayGame());

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith('/api/games/active', expect.objectContaining({ credentials: 'include' }));
      });
    });

    it('handles server error during recovery by redirecting home', async () => {
      const consoleSpy = jest.spyOn(console, 'error').mockImplementation();
      // Use 4xx non-401 so fetchWithRetry returns immediately without retries
      (global.fetch as jest.Mock).mockResolvedValue(errorResponse(400));

      renderHook(() => usePlayGame());

      await waitFor(() => {
        expect(mockReplace).toHaveBeenCalledWith('/');
      });

      consoleSpy.mockRestore();
    });
  });

  describe('Initial Load', () => {
    it('does not initialize when no gameId', async () => {
      renderHook(() => usePlayGame());

      expect(storeSpy.spies.syncState).not.toHaveBeenCalled();
    });

    it('initializes when gameId exists', async () => {
      useGameStore.setState({ gameId: 42, currentEvent: { story: 'Test', options: [{ text: 'Option 1' }] } } as never);
      storeSpy.spies.syncState.mockResolvedValue(undefined);

      renderHook(() => usePlayGame());

      await waitFor(() => {
        expect(storeSpy.spies.syncState).toHaveBeenCalled();
      });
    });

    it('keeps recovery available without generating an event when initial sync rejects a stale gameId', async () => {
      useGameStore.setState({ gameId: 46, storyText: '', currentEvent: null } as never);
      storeSpy.spies.syncState.mockRejectedValue(
        Object.assign(new Error('Game not found'), { status: 404 })
      );

      const { result } = renderHook(() => usePlayGame());

      await waitFor(() => {
        expect(storeSpy.spies.syncState).toHaveBeenCalled();
      });

      await waitFor(() => {
        expect(result.current.phase).toBe('error');
      });
      expect(mockReplace).not.toHaveBeenCalled();
      expect(global.fetch).not.toHaveBeenCalledWith(
        expect.stringContaining('/api/games/46/event'),
        expect.anything()
      );
      expect(global.fetch).not.toHaveBeenCalledWith(
        expect.stringContaining('/api/games/active'),
        expect.anything()
      );
    });
  });

  describe('Ending Data', () => {
    it('exposes endingData state', () => {
      const { result } = renderHook(() => usePlayGame());

      expect(result.current.endingData).toBeNull();
    });
  });

  describe('Round Scene Images', () => {
    it('exposes roundSceneImages state', () => {
      const { result } = renderHook(() => usePlayGame());

      expect(result.current.roundSceneImages).toEqual([]);
    });

    it('exposes scene image loading states', () => {
      const { result } = renderHook(() => usePlayGame());

      expect(result.current.isLoadingRoundSceneImage).toBe(false);
      expect(result.current.isRegeneratingRoundScene).toBe(false);
    });

    it('exposes scene image actions', () => {
      const { result } = renderHook(() => usePlayGame());

      expect(typeof result.current.fetchRoundSceneImage).toBe('function');
      expect(typeof result.current.fetchAllRoundSceneImages).toBe('function');
      expect(typeof result.current.regenerateRoundSceneImage).toBe('function');
    });

    it('fetches result scene for the just completed round after choice advances current_round', async () => {
      useGameStore.setState({
        gameId: 42,
        roundInfo: { current_round: 1, week: 0 },
        storyText: '刚完成的第 0 轮结果正文。',
        currentEvent: {
          story: '刚完成的第 0 轮结果正文。',
          options: [{ text: '继续查证' }],
        },
      } as never);
      storeSpy.spies.syncState.mockResolvedValue(undefined);

      const { result } = renderHook(() => usePlayGame());

      await waitFor(() => {
        expect(storeSpy.spies.fetchAllRoundSceneImages).toHaveBeenCalled();
      });
      storeSpy.spies.fetchRoundSceneImage.mockClear();

      act(() => {
        result.current.setPhase('result');
      });

      await waitFor(() => {
        expect(storeSpy.spies.fetchRoundSceneImage).toHaveBeenCalledWith(0, 'result');
      });
      expect(storeSpy.spies.fetchRoundSceneImage).not.toHaveBeenCalledWith(1, 'result');
    });

    it('does not fetch a scene image before the generating round has story text', async () => {
      useGameStore.setState({
        gameId: 42,
        roundInfo: { current_round: 2, week: 0 },
        storyText: '',
        currentEvent: null,
      } as never);
      storeSpy.spies.syncState.mockImplementation(() => new Promise(() => {}));

      renderHook(() => usePlayGame());

      await waitFor(() => {
        expect(storeSpy.spies.fetchAllRoundSceneImages).toHaveBeenCalled();
      });
      expect(storeSpy.spies.fetchRoundSceneImage).not.toHaveBeenCalled();
    });
  });

  describe('Handler functions', () => {
    it('provides handleChoice', () => {
      const { result } = renderHook(() => usePlayGame());
      expect(typeof result.current.handleChoice).toBe('function');
    });

    it('provides handleCustomChoice', () => {
      const { result } = renderHook(() => usePlayGame());
      expect(typeof result.current.handleCustomChoice).toBe('function');
    });

    it('provides handleSave', () => {
      const { result } = renderHook(() => usePlayGame());
      expect(typeof result.current.handleSave).toBe('function');
    });

    it('provides handleRegenerate', () => {
      const { result } = renderHook(() => usePlayGame());
      expect(typeof result.current.handleRegenerate).toBe('function');
    });

    it('provides generateEvent', () => {
      const { result } = renderHook(() => usePlayGame());
      expect(typeof result.current.generateEvent).toBe('function');
    });
  });

  describe('History functions', () => {
    it('provides history state and handlers', () => {
      const { result } = renderHook(() => usePlayGame());
      expect(result.current.showHistory).toBe(false);
      expect(typeof result.current.handleOpenHistory).toBe('function');
      expect(typeof result.current.handleSelectHistoryRound).toBe('function');
      expect(typeof result.current.handleBackToCurrent).toBe('function');
    });
  });

  describe('Utility functions', () => {
    it('provides getLoadingMessage', () => {
      const { result } = renderHook(() => usePlayGame());
      expect(typeof result.current.getLoadingMessage).toBe('function');
    });

    it('provides router instance', () => {
      const { result } = renderHook(() => usePlayGame());
      expect(result.current.router).toBeDefined();
      expect(typeof result.current.router.push).toBe('function');
    });
  });

  describe('Store values', () => {
    it('exposes playerState from store', () => {
      const { result } = renderHook(() => usePlayGame());

      expect(result.current.playerState).toBeNull();
    });

    it('exposes progress from store', () => {
      const { result } = renderHook(() => usePlayGame());

      expect(result.current.progress).toBeNull();
    });

    it('exposes roundInfo from store', () => {
      const { result } = renderHook(() => usePlayGame());

      expect(result.current.roundInfo).toBeNull();
    });

    it('exposes storyText from store', () => {
      const { result } = renderHook(() => usePlayGame());

      expect(result.current.storyText).toBe('');
    });

    it('exposes currentEvent from store', () => {
      const { result } = renderHook(() => usePlayGame());

      expect(result.current.currentEvent).toBeNull();
    });

    it('exposes isGameOver from store', () => {
      const { result } = renderHook(() => usePlayGame());

      expect(result.current.isGameOver).toBe(false);
    });
  });

  describe('Actions', () => {
    it('provides setPhase action', () => {
      const { result } = renderHook(() => usePlayGame());
      expect(typeof result.current.setPhase).toBe('function');
    });

    it('provides setOptions action', () => {
      const { result } = renderHook(() => usePlayGame());
      expect(typeof result.current.setOptions).toBe('function');
    });

    it('provides setStoryText action', () => {
      const { result } = renderHook(() => usePlayGame());
      expect(result.current.setStoryText).toBe(storeSpy.spies.setStoryText);
    });
  });
});
