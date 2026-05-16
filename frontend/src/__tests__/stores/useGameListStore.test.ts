/**
 * useGameListStore Tests
 * Tests for the game list store
 */
import { act } from '@testing-library/react';
import { useGameListStore } from '@/stores/useGameListStore';
import type { GameListItem, PresetInfo } from '@/lib/types';
import { jsonResponse } from '@/__tests__/helpers/fetch';

describe('useGameListStore', () => {
  beforeEach(() => {
    act(() => {
      useGameListStore.setState({ savedGames: [], presets: [] });
    });
    jest.clearAllMocks();
    global.fetch = jest.fn();
  });

  describe('Initial state', () => {
    it('has correct initial values', () => {
      const state = useGameListStore.getState();
      expect(state.savedGames).toEqual([]);
      expect(state.presets).toEqual([]);
    });
  });

  describe('fetchSavedGames', () => {
    it('fetches saved games from API', async () => {
      const mockGames = [
        { game_id: 1, created_at: '2024-01-01' },
        { game_id: 2, created_at: '2024-01-02' },
      ];
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockGames));

      await act(async () => {
        await useGameListStore.getState().fetchSavedGames();
      });

      const state = useGameListStore.getState();
      expect(state.savedGames).toHaveLength(2);
      expect(state.savedGames[0].game_id).toBe(1);
      expect(global.fetch).toHaveBeenCalledWith('/api/games', expect.objectContaining({ credentials: 'include' }));
    });
  });

  describe('fetchPresets', () => {
    it('fetches presets from API', async () => {
      const mockPresets = [
        { preset_id: 1, player_name: 'Character 1' },
        { preset_id: 2, player_name: 'Character 2' },
      ];
      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse(mockPresets));

      await act(async () => {
        await useGameListStore.getState().fetchPresets();
      });

      const state = useGameListStore.getState();
      expect(state.presets).toHaveLength(2);
      expect(state.presets[0].preset_id).toBe(1);
      expect(global.fetch).toHaveBeenCalledWith('/api/presets', expect.objectContaining({ credentials: 'include' }));
    });
  });

  describe('deleteGame', () => {
    it('deletes game from list', async () => {
      // Setup initial state
      act(() => {
        useGameListStore.setState({
          savedGames: [
            { game_id: 1, created_at: '2024-01-01' },
            { game_id: 2, created_at: '2024-01-02' },
          ] as GameListItem[],
        });
      });

      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ success: true }));

      await act(async () => {
        await useGameListStore.getState().deleteGame(1);
      });

      const state = useGameListStore.getState();
      expect(state.savedGames).toHaveLength(1);
      expect(state.savedGames[0].game_id).toBe(2);
      expect(global.fetch).toHaveBeenCalledWith('/api/games/1', expect.objectContaining({ method: 'DELETE' }));
    });
  });

  describe('deletePreset', () => {
    it('deletes preset from list', async () => {
      // Setup initial state
      act(() => {
        useGameListStore.setState({
          presets: [
            { preset_id: 1, player_name: 'Character 1' },
            { preset_id: 2, player_name: 'Character 2' },
          ] as PresetInfo[],
        });
      });

      (global.fetch as jest.Mock).mockResolvedValue(jsonResponse({ success: true }));

      await act(async () => {
        await useGameListStore.getState().deletePreset(1);
      });

      const state = useGameListStore.getState();
      expect(state.presets).toHaveLength(1);
      expect(state.presets[0].preset_id).toBe(2);
      expect(global.fetch).toHaveBeenCalledWith('/api/presets/1', expect.objectContaining({ method: 'DELETE' }));
    });
  });

  describe('setSavedGames', () => {
    it('sets saved games directly', () => {
      const games = [
        { game_id: 1, created_at: '2024-01-01' },
        { game_id: 2, created_at: '2024-01-02' },
      ] as GameListItem[];

      act(() => {
        useGameListStore.getState().setSavedGames(games);
      });

      expect(useGameListStore.getState().savedGames).toEqual(games);
    });
  });

  describe('setPresets', () => {
    it('sets presets directly', () => {
      const presets = [
        { preset_id: 1, player_name: 'Character 1' },
        { preset_id: 2, player_name: 'Character 2' },
      ] as PresetInfo[];

      act(() => {
        useGameListStore.getState().setPresets(presets);
      });

      expect(useGameListStore.getState().presets).toEqual(presets);
    });
  });
});
