/**
 * useGameListStore — 存档和预设列表状态
 * 
 * 管理游戏存档列表和角色预设列表
 */
import { create } from "zustand";
import type { GameListItem, PresetInfo } from "@/lib/types";
import api from "@/lib/api";

interface GameListState {
  // Saves & presets
  savedGames: GameListItem[];
  presets: PresetInfo[];

  // Actions
  fetchSavedGames: () => Promise<void>;
  fetchPresets: () => Promise<void>;
  deleteGame: (gameId: number) => Promise<void>;
  deletePreset: (presetId: number) => Promise<void>;
  setSavedGames: (games: GameListItem[]) => void;
  setPresets: (presets: PresetInfo[]) => void;
}

export const useGameListStore = create<GameListState>((set) => ({
  savedGames: [],
  presets: [],

  fetchSavedGames: async () => {
    const savedGames = await api.games.list();
    set({ savedGames });
  },

  fetchPresets: async () => {
    const presets = await api.presets.list();
    set({ presets });
  },

  deleteGame: async (gameId) => {
    await api.games.delete(gameId);
    set((state) => ({
      savedGames: state.savedGames.filter((g) => g.game_id !== gameId),
    }));
  },

  deletePreset: async (presetId) => {
    await api.presets.delete(presetId);
    set((state) => ({
      presets: state.presets.filter((p) => p.preset_id !== presetId),
    }));
  },

  setSavedGames: (games) => set({ savedGames: games }),
  setPresets: (presets) => set({ presets }),
}));
