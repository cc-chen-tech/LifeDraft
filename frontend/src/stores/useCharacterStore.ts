/**
 * useCharacterStore — 角色创建状态
 *
 * 管理角色创建流程的状态
 *
 * ★ 注意：此 store 不再持久化到 localStorage
 * - 角色创建表单数据在刷新后会丢失
 * - 这是为了符合 "不使用 localStorage" 的要求
 */
import { create } from "zustand";
import type { PresetInfo } from "@/lib/types";

// Character creation step tracking
export type CreationStep =
  | "era"
  | "age"
  | "gender"
  | "world"
  | "portrait";

// 前端步骤只包含用户需要交互的 5 个步骤
export const CREATION_STEPS: CreationStep[] = [
  "era",
  "age",
  "gender",
  "world",
  "portrait",
];

// 所有步骤都是手动步骤（用户需要交互）
export const MANUAL_STEPS: CreationStep[] = ["era", "age", "gender", "world", "portrait"];

// 后台自动生成的步骤
export const AUTO_ADVANCE_STEPS: string[] = ["family", "relationships", "traits"];

interface CharacterState {
  // Character creation
  creationStep: number;
  characterSettings: Record<string, unknown>;
  playerName: string;
  lifeVision: string;
  openingStory: string;
  isPresetLoaded: boolean;

  // Actions
  setCreationStep: (step: number) => void;
  nextCreationStep: () => void;
  prevCreationStep: () => void;
  updateCharacterSetting: (key: string, value: unknown) => void;
  setPlayerName: (name: string) => void;
  setLifeVision: (vision: string) => void;
  setOpeningStory: (story: string) => void;
  resetCreation: () => void;
  loadPreset: (preset: PresetInfo) => void;
}

export const useCharacterStore = create<CharacterState>()(
  (set) => ({
    creationStep: 0,
    characterSettings: {},
    playerName: "",
    lifeVision: "",
    openingStory: "",
    isPresetLoaded: false,

    setCreationStep: (step) => set({ creationStep: step }),

    nextCreationStep: () =>
      set((state) => ({
        creationStep: Math.min(state.creationStep + 1, CREATION_STEPS.length - 1),
      })),

    prevCreationStep: () =>
      set((state) => ({
        creationStep: Math.max(state.creationStep - 1, 0),
      })),

    updateCharacterSetting: (key, value) =>
      set((state) => ({
        characterSettings: { ...state.characterSettings, [key]: value },
      })),

    setPlayerName: (name) => set({ playerName: name }),
    setLifeVision: (vision) => set({ lifeVision: vision }),
    setOpeningStory: (story) => set({ openingStory: story }),

    resetCreation: () =>
      set({
        creationStep: 0,
        characterSettings: {},
        playerName: "",
        lifeVision: "",
        openingStory: "",
        isPresetLoaded: false,
      }),

    loadPreset: (preset) =>
      set({
        playerName: preset.player_name,
        lifeVision: preset.life_vision || "",
        characterSettings: preset.character_settings,
        creationStep: MANUAL_STEPS.length,
        isPresetLoaded: true,
        openingStory: "",
      }),
  })
);
