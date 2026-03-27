/**
 * useSessionStore Tests
 * 
 * Tests for session management state that may be extracted from useGameStore.
 * These tests ensure that session-related functionality remains consistent
 * after any future store refactoring.
 */
import { act, renderHook } from '@testing-library/react';

// Mock the API before importing the store
jest.mock('@/lib/api', () => ({
  __esModule: true,
  default: {
    games: {
      list: jest.fn().mockResolvedValue([]),
      create: jest.fn().mockResolvedValue({ game_id: 1 }),
      load: jest.fn().mockResolvedValue({
        game_id: 1,
        player_state: { player_name: 'Test' },
        progress: { week: 1 },
        round_info: { current_round: 1 },
        current_event: null,
      }),
      save: jest.fn().mockResolvedValue({ success: true }),
      delete: jest.fn().mockResolvedValue({ success: true }),
    },
    presets: {
      list: jest.fn().mockResolvedValue([]),
      create: jest.fn().mockResolvedValue({ preset_id: 1 }),
      delete: jest.fn().mockResolvedValue({ success: true }),
    },
    gameplay: {
      getState: jest.fn().mockResolvedValue({
        player_state: { player_name: 'Test' },
        progress: { week: 1 },
        round_info: { current_round: 1 },
        current_event: null,
      }),
    },
    images: {
      listByGame: jest.fn().mockResolvedValue({ images: [], total: 0 }),
    },
  },
}));

import { useGameStore } from '@/stores/useGameStore';
import api from '@/lib/api';

describe('useSessionStore (Session Management)', () => {
  beforeEach(() => {
    act(() => {
      useGameStore.getState().resetGame();
      useGameStore.getState().resetCreation();
    });
    jest.clearAllMocks();
  });

  // ==================== Initial State Tests ====================
  describe('Initial State', () => {
    it('should have null gameId initially', () => {
      const state = useGameStore.getState();
      expect(state.gameId).toBeNull();
    });

    it('should have null sessionId initially', () => {
      const state = useGameStore.getState();
      expect(state.sessionId).toBeNull();
    });

    it('should have null playerState initially', () => {
      const state = useGameStore.getState();
      expect(state.playerState).toBeNull();
    });

    it('should have null progress initially', () => {
      const state = useGameStore.getState();
      expect(state.progress).toBeNull();
    });

    it('should have null roundInfo initially', () => {
      const state = useGameStore.getState();
      expect(state.roundInfo).toBeNull();
    });

    it('should have isGameOver as false initially', () => {
      const state = useGameStore.getState();
      expect(state.isGameOver).toBe(false);
    });
  });

  // ==================== setGameId Tests ====================
  describe('setGameId', () => {
    it('should set gameId correctly', () => {
      act(() => {
        useGameStore.getState().setGameId(42);
      });
      expect(useGameStore.getState().gameId).toBe(42);
    });

    it('should update gameId when called multiple times', () => {
      act(() => {
        useGameStore.getState().setGameId(1);
      });
      expect(useGameStore.getState().gameId).toBe(1);

      act(() => {
        useGameStore.getState().setGameId(2);
      });
      expect(useGameStore.getState().gameId).toBe(2);
    });
  });

  // ==================== setGameSession Tests ====================
  describe('setGameSession', () => {
    it('should set both gameId and sessionId', () => {
      act(() => {
        useGameStore.getState().setGameSession(123, 'session-abc');
      });
      const state = useGameStore.getState();
      expect(state.gameId).toBe(123);
      expect(state.sessionId).toBe('session-abc');
    });

    it('should overwrite previous session values', () => {
      act(() => {
        useGameStore.getState().setGameSession(1, 'old-session');
        useGameStore.getState().setGameSession(2, 'new-session');
      });
      const state = useGameStore.getState();
      expect(state.gameId).toBe(2);
      expect(state.sessionId).toBe('new-session');
    });
  });

  // ==================== loadGameState Tests ====================
  describe('loadGameState', () => {
    it('should load game state from API', async () => {
      const mockResponse = {
        game_id: 42,
        player_state: { player_name: 'TestPlayer', age: 20 },
        progress: { week: 5 },
        round_info: { current_round: 3 },
        current_event: null,
      };
      (api.games.load as jest.Mock).mockResolvedValue(mockResponse);

      await act(async () => {
        await useGameStore.getState().loadGameState(42);
      });

      const state = useGameStore.getState();
      expect(state.gameId).toBe(42);
      expect(state.playerState).toEqual(mockResponse.player_state);
      expect(state.progress).toEqual(mockResponse.progress);
      expect(state.roundInfo).toEqual(mockResponse.round_info);
    });

    it('should set isGameOver to false on load', async () => {
      act(() => {
        useGameStore.setState({ isGameOver: true });
      });

      (api.games.load as jest.Mock).mockResolvedValue({
        game_id: 1,
        player_state: {},
        progress: {},
        round_info: {},
        current_event: null,
      });

      await act(async () => {
        await useGameStore.getState().loadGameState(1);
      });

      expect(useGameStore.getState().isGameOver).toBe(false);
    });

    it('should handle current_event with event_description', async () => {
      (api.games.load as jest.Mock).mockResolvedValue({
        game_id: 1,
        player_state: {},
        progress: {},
        round_info: {},
        current_event: {
          event_description: 'Test event description',
          options: [{ text: 'Option 1' }],
        },
      });

      await act(async () => {
        await useGameStore.getState().loadGameState(1);
      });

      const state = useGameStore.getState();
      expect(state.currentEvent?.story).toBe('Test event description');
      expect(state.currentEvent?.options).toHaveLength(1);
    });

    it('should restore storyText from last_round_full_story when no event', async () => {
      (api.games.load as jest.Mock).mockResolvedValue({
        game_id: 1,
        player_state: { last_round_full_story: 'Previous story text' },
        progress: {},
        round_info: {},
        current_event: null,
      });

      await act(async () => {
        await useGameStore.getState().loadGameState(1);
      });

      expect(useGameStore.getState().storyText).toBe('Previous story text');
    });

    it('should restore storyText from round_history when no last_round_full_story', async () => {
      (api.games.load as jest.Mock).mockResolvedValue({
        game_id: 1,
        player_state: {
          round_history: [
            { event_description: 'Event 1', story_continuation: 'Cont 1' },
          ],
        },
        progress: {},
        round_info: {},
        current_event: null,
      });

      await act(async () => {
        await useGameStore.getState().loadGameState(1);
      });

      expect(useGameStore.getState().storyText).toContain('Event 1');
      expect(useGameStore.getState().storyText).toContain('Cont 1');
    });
  });

  // ==================== syncState Tests ====================
  describe('syncState', () => {
    it('should not sync when gameId is null', async () => {
      await act(async () => {
        await useGameStore.getState().syncState();
      });
      expect(api.gameplay.getState).not.toHaveBeenCalled();
    });

    it('should call API with correct gameId', async () => {
      act(() => {
        useGameStore.getState().setGameSession(42, 'session-42');
      });

      (api.gameplay.getState as jest.Mock).mockResolvedValue({
        player_state: {},
        progress: {},
        round_info: {},
        current_event: null,
      });

      await act(async () => {
        await useGameStore.getState().syncState();
      });

      expect(api.gameplay.getState).toHaveBeenCalledWith(42);
    });

    it('should update playerState when changed', async () => {
      act(() => {
        useGameStore.getState().setGameSession(42, 'session-42');
        useGameStore.setState({ playerState: { player_name: 'Test', life_vision: '', energy: 50, mood: 100, knowledge: 0, wealth: 0, age: 18, week: 1, current_round: 1, rounds_per_week: 3, character_settings: {} } });
      });

      (api.gameplay.getState as jest.Mock).mockResolvedValue({
        player_state: { energy: 100 },
        progress: {},
        round_info: {},
        current_event: null,
      });

      await act(async () => {
        await useGameStore.getState().syncState();
      });

      expect(useGameStore.getState().playerState?.energy).toBe(100);
    });

    it('should recover from 404 by reloading game', async () => {
      act(() => {
        useGameStore.getState().setGameSession(42, 'session-42');
      });

      (api.gameplay.getState as jest.Mock).mockRejectedValueOnce({ status: 404 });
      (api.games.load as jest.Mock).mockResolvedValue({
        game_id: 42,
        player_state: { player_name: 'Recovered' },
        progress: {},
        round_info: {},
        current_event: null,
      });

      await act(async () => {
        await useGameStore.getState().syncState();
      });

      expect(api.games.load).toHaveBeenCalledWith(42);
    });

    it('should clear state when game no longer exists', async () => {
      act(() => {
        useGameStore.getState().setGameSession(42, 'session-42');
        useGameStore.setState({ storyText: 'Some text' });
      });

      (api.gameplay.getState as jest.Mock).mockRejectedValueOnce({ status: 404 });
      (api.games.load as jest.Mock).mockRejectedValue({ status: 404 });

      await act(async () => {
        try {
          await useGameStore.getState().syncState();
        } catch (e) {
          // Expected
        }
      });

      expect(useGameStore.getState().gameId).toBeNull();
    });
  });

  // ==================== syncPlayerState Tests ====================
  describe('syncPlayerState', () => {
    it('should not sync when gameId is null', async () => {
      const result = await act(async () => {
        return await useGameStore.getState().syncPlayerState();
      });

      expect(result).toBeUndefined();
      expect(api.gameplay.getState).not.toHaveBeenCalled();
    });

    it('should sync player state correctly', async () => {
      act(() => {
        useGameStore.getState().setGameSession(42, 'session-42');
      });

      const mockState = {
        player_state: { energy: 80 },
        progress: { week: 3 },
        round_info: { current_round: 5 },
        current_event: null,
      };
      (api.gameplay.getState as jest.Mock).mockResolvedValue(mockState);

      await act(async () => {
        await useGameStore.getState().syncPlayerState();
      });

      expect(api.gameplay.getState).toHaveBeenCalledWith(42);
    });
  });

  // ==================== saveGame Tests ====================
  describe('saveGame', () => {
    it('should not save when gameId is null', async () => {
      await act(async () => {
        await useGameStore.getState().saveGame();
      });
      expect(api.games.save).not.toHaveBeenCalled();
    });

    it('should call API with gameId', async () => {
      act(() => {
        useGameStore.getState().setGameSession(42, 'session-42');
      });

      await act(async () => {
        await useGameStore.getState().saveGame();
      });

      expect(api.games.save).toHaveBeenCalledWith(42);
    });
  });

  // ==================== resetGame Tests ====================
  describe('resetGame', () => {
    it('should reset all session state', () => {
      act(() => {
        useGameStore.setState({
          gameId: 42,
          sessionId: 'session-42',
          playerState: { player_name: 'Test', life_vision: '', energy: 100, mood: 100, knowledge: 0, wealth: 0, age: 18, week: 5, current_round: 3, rounds_per_week: 3, character_settings: {} },
          progress: { week: 5, current_round: 3, rounds_per_week: 3 },
          roundInfo: { current_round: 3, week: 5 },
          storyText: 'Some story',
          isGameOver: true,
        });
        useGameStore.getState().resetGame();
      });

      const state = useGameStore.getState();
      expect(state.gameId).toBeNull();
      expect(state.sessionId).toBeNull();
      expect(state.playerState).toBeNull();
      expect(state.progress).toBeNull();
      expect(state.roundInfo).toBeNull();
      expect(state.storyText).toBe('');
      expect(state.isGameOver).toBe(false);
    });

    it('should also reset creation state', () => {
      act(() => {
        useGameStore.setState({
          gameId: 42,
          creationStep: 5,
          characterSettings: { era: { era: 'modern' } },
          playerName: 'TestName',
        });
        useGameStore.getState().resetGame();
      });

      const state = useGameStore.getState();
      expect(state.creationStep).toBe(0);
      expect(state.characterSettings).toEqual({});
      expect(state.playerName).toBe('');
    });
  });

  // ==================== Cross-cutting concerns ====================
  describe('Session consistency', () => {
    it('should maintain consistency between gameId and session operations', async () => {
      act(() => {
        useGameStore.getState().setGameSession(100, 'session-100');
      });

      expect(useGameStore.getState().gameId).toBe(100);

      (api.games.load as jest.Mock).mockResolvedValue({
        game_id: 100,
        player_state: { player_name: 'Loaded' },
        progress: { week: 1 },
        round_info: { current_round: 1 },
        current_event: null,
      });

      await act(async () => {
        await useGameStore.getState().loadGameState(100);
      });

      // gameId should remain consistent
      expect(useGameStore.getState().gameId).toBe(100);
      expect(useGameStore.getState().playerState?.player_name).toBe('Loaded');
    });

    it('should handle rapid session changes', () => {
      act(() => {
        useGameStore.getState().setGameSession(1, 'session-1');
        useGameStore.getState().setGameSession(2, 'session-2');
        useGameStore.getState().setGameSession(3, 'session-3');
      });

      expect(useGameStore.getState().gameId).toBe(3);
      expect(useGameStore.getState().sessionId).toBe('session-3');
    });
  });
});
