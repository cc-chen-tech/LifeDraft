/**
 * useGameStore — 游戏核心会话状态（向后兼容的组合 Store）
 *
 * 本文件是一个组合 store，内部委托给各专门的子 store：
 * - useSessionStore: 会话状态（gameId, sessionId, playerState, progress, roundInfo）
 * - useEventStore: 事件和故事状态
 * - useImageStore: 玩家形象和开场插画
 * - useCharacterStore: 角色创建状态
 * - useGameListStore: 存档和预设列表
 * - useSceneImageStore: 场景插画状态
 *
 * 现有消费者可以继续使用 useGameStore，但也可以直接导入子 store 获得更精细的更新控制。
 *
 * ★ 注意：此 store 不再持久化到 localStorage
 * - 游戏状态通过 Cookie 认证从服务器获取
 * - 角色创建表单在刷新后会丢失
 */
import { create } from "zustand";
import type {
  GameEvent,
  GameListItem,
  PresetInfo,
  PlayerState,
  GameProgress,
  RoundInfo,
  CharacterSettings,
} from "@/lib/types";

// Import sub-stores
import { useSessionStore } from "./useSessionStore";
import { useEventStore } from "./useEventStore";
import { useImageStore, type RoundSceneImage } from "./useImageStore";
import { useCharacterStore } from "./useCharacterStore";
import { useGameListStore } from "./useGameListStore";
import { useSceneImageStore } from "./useSceneImageStore";

// Re-export sub-stores for backward compatibility
export { useSessionStore } from "./useSessionStore";
export { useEventStore } from "./useEventStore";
export { useImageStore, type RoundSceneImage } from "./useImageStore";
export { useCharacterStore, CREATION_STEPS, MANUAL_STEPS, AUTO_ADVANCE_STEPS, type CreationStep } from "./useCharacterStore";
export { useGameListStore } from "./useGameListStore";
export { useSceneImageStore } from "./useSceneImageStore";

// ==================== Backward Compatible Combined Store ====================

interface GameState {
  // Game session
  gameId: number | null;
  sessionId: string | null;
  playerState: PlayerState | null;
  progress: GameProgress | null;
  roundInfo: RoundInfo | null;
  isGameOver: boolean;

  // Event
  currentEvent: GameEvent | null;
  storyText: string;
  lastSummary: Record<string, unknown> | null; // Summary is intentionally flexible

  // Saves & presets
  savedGames: GameListItem[];
  presets: PresetInfo[];

  // Character creation
  creationStep: number;
  characterSettings: CharacterSettings;
  playerName: string;
  lifeVision: string;
  openingStory: string;
  isPresetLoaded: boolean;

  // ★ 游戏设置
  enableSceneImage: boolean;
  constraintLevel: "fast" | "expert" | "master";

  // ★ 场景插画
  roundSceneImages: RoundSceneImage[];
  currentRoundSceneImage: RoundSceneImage | null;
  eventSceneImage: RoundSceneImage | null;
  resultSceneImage: RoundSceneImage | null;
  isLoadingRoundSceneImage: boolean;
  roundSceneError: string | null;
  isRegeneratingRoundScene: boolean;
  roundSceneRegenerateError: string | null;

  // ★ 历史场景插画状态
  historySceneImage: RoundSceneImage | null;
  isLoadingHistoryImage: boolean;
  isGeneratingHistoryImage: boolean;
  isRegeneratingHistoryImage: boolean;

  // Actions — Session
  setGameId: (gameId: number) => void;
  setGameSession: (gameId: number, sessionId: string) => void;
  loadGameState: (gameId: number) => Promise<void>;
  syncState: (options?: { gameId?: number; signal?: AbortSignal }) => Promise<void>;
  syncPlayerState: () => Promise<unknown>;
  saveGame: () => Promise<void>;
  resetGame: () => void;

  // Actions — Event
  setCurrentEvent: (event: GameEvent | null) => void;
  appendStoryText: (text: string) => void;
  setStoryText: (text: string) => void;
  clearCurrentEvent: () => void;
  setGameOver: (over: boolean) => void;
  generateSummary: (weeks?: number) => Promise<void>;
  clearSummary: () => void;

  // Actions — Lists
  fetchSavedGames: () => Promise<void>;
  fetchPresets: () => Promise<void>;
  deleteGame: (gameId: number) => Promise<void>;
  deletePreset: (presetId: number) => Promise<void>;

  // Actions — Character creation
  setCreationStep: (step: number) => void;
  nextCreationStep: () => void;
  prevCreationStep: () => void;
  updateCharacterSetting: (key: string, value: unknown) => void;
  setPlayerName: (name: string) => void;
  setLifeVision: (vision: string) => void;
  setOpeningStory: (story: string) => void;
  resetCreation: () => void;
  loadPreset: (preset: PresetInfo) => void;

  // Actions — Game Settings
  setEnableSceneImage: (enabled: boolean) => void;
  setConstraintLevel: (level: "fast" | "expert" | "master") => void;
  generateRoundSceneImage: (roundNumber: number, storyText: string, stage?: string) => Promise<void>;

  // Actions — Scene Images
  fetchRoundSceneImage: (
    roundNumber: number,
    stage?: string,
    options?: { retry?: boolean }
  ) => Promise<void>;
  fetchAllRoundSceneImages: () => Promise<void>;
  setCurrentRoundSceneImage: (image: RoundSceneImage | null) => void;
  setEventSceneImage: (image: RoundSceneImage | null) => void;
  setResultSceneImage: (image: RoundSceneImage | null) => void;
  addRoundSceneImage: (image: RoundSceneImage) => void;
  regenerateRoundSceneImage: (roundNumber: number, userPrompt: string) => Promise<void>;
  clearImageCache: () => void;

  // Actions — History Scene Images
  fetchHistorySceneImage: (week: number, round: number, stage?: string) => Promise<void>;
  generateHistorySceneImage: (week: number, round: number, storyText: string, stage?: string) => Promise<void>;
  regenerateHistorySceneImage: (week: number, round: number, storyText: string, userPrompt: string, sceneId: number) => Promise<void>;
  setHistorySceneImage: (image: RoundSceneImage | null) => void;

  // Internal sync method
  _syncFromSubStores: () => void;
}

export const useGameStore = create<GameState>()(
  (set, get) => ({
    // ==================== Initial State ====================
    // Session
    gameId: null,
    sessionId: null,
    playerState: null,
    progress: null,
    roundInfo: null,
    isGameOver: false,
    enableSceneImage: true,
    constraintLevel: "expert",

    // Event
    currentEvent: null,
    storyText: "",
    lastSummary: null,

    // Lists
    savedGames: [],
    presets: [],

    // Character
    creationStep: 0,
    characterSettings: {},
    playerName: "",
    lifeVision: "",
    openingStory: "",
    isPresetLoaded: false,

    // Scene Images
    roundSceneImages: [],
    currentRoundSceneImage: null,
    eventSceneImage: null,
    resultSceneImage: null,
    isLoadingRoundSceneImage: false,
    roundSceneError: null,
    isRegeneratingRoundScene: false,
    roundSceneRegenerateError: null,

    // History Images
    historySceneImage: null,
    isLoadingHistoryImage: false,
    isGeneratingHistoryImage: false,
    isRegeneratingHistoryImage: false,

    // Internal sync method to pull state from sub-stores
    _syncFromSubStores: () => {
      const sessionState = useSessionStore.getState();
      const eventState = useEventStore.getState();
      const characterState = useCharacterStore.getState();
      const listState = useGameListStore.getState();
      const sceneState = useSceneImageStore.getState();

      set({
        // Session
        gameId: sessionState.gameId,
        sessionId: sessionState.sessionId,
        playerState: sessionState.playerState,
        progress: sessionState.progress,
        roundInfo: sessionState.roundInfo,
        isGameOver: sessionState.isGameOver,
        enableSceneImage: sessionState.enableSceneImage,
        constraintLevel: sessionState.constraintLevel,
        // Event
        currentEvent: eventState.currentEvent,
        storyText: eventState.storyText,
        lastSummary: eventState.lastSummary,
        // Character
        creationStep: characterState.creationStep,
        characterSettings: characterState.characterSettings,
        playerName: characterState.playerName,
        lifeVision: characterState.lifeVision,
        openingStory: characterState.openingStory,
        isPresetLoaded: characterState.isPresetLoaded,
        // Lists
        savedGames: listState.savedGames,
        presets: listState.presets,
        // Scene Images
        roundSceneImages: sceneState.roundSceneImages,
        currentRoundSceneImage: sceneState.currentRoundSceneImage,
        eventSceneImage: sceneState.eventSceneImage,
        resultSceneImage: sceneState.resultSceneImage,
        isLoadingRoundSceneImage: sceneState.isLoadingRoundSceneImage,
        roundSceneError: sceneState.roundSceneError,
        isRegeneratingRoundScene: sceneState.isRegeneratingRoundScene,
        roundSceneRegenerateError: sceneState.roundSceneRegenerateError,
        historySceneImage: sceneState.historySceneImage,
        isLoadingHistoryImage: sceneState.isLoadingHistoryImage,
        isGeneratingHistoryImage: sceneState.isGeneratingHistoryImage,
        isRegeneratingHistoryImage: sceneState.isRegeneratingHistoryImage,
      });
    },

    // ==================== Session Actions ====================
    setGameId: (gameId) => {
      useSessionStore.getState().setGameId(gameId);
      set({ gameId });
    },
    
    setGameSession: (gameId, sessionId) => {
      useSessionStore.getState().setGameSession(gameId, sessionId);
      set({ gameId, sessionId });
    },

    loadGameState: async (gameId) => {
      const result = await useSessionStore.getState().loadGameState(gameId);

      // Update event store
      if (result.event) {
        useEventStore.getState().setCurrentEvent({
          ...result.event,
          story: result.event.story || result.storyText,
        });
      } else {
        useEventStore.getState().setCurrentEvent(null);
      }
      if (result.storyText) {
        useEventStore.getState().setStoryText(result.storyText);
        if (result.event?.options?.length && !result.event.story) {
          useEventStore.getState().setCurrentEvent({
            ...result.event,
            story: result.storyText,
          });
        }
      } else {
        useEventStore.getState().setStoryText("");
      }

      // Update character store
      if (result.characterSettings) {
        Object.entries(result.characterSettings).forEach(([key, value]) => {
          useCharacterStore.getState().updateCharacterSetting(key, value);
        });
      }
      if (result.playerName) {
        useCharacterStore.getState().setPlayerName(result.playerName);
      }

      // Clear old scene images
      useSceneImageStore.getState().clearCurrentRoundImages();

      // Sync state
      get()._syncFromSubStores();

      // Load player images asynchronously
      setTimeout(() => {
        useImageStore.getState().loadPlayerImages(gameId);
      }, 0);
    },

    syncState: async (options) => {
      const expectedGameId = options?.gameId ?? get().gameId;
      const isRunOwnedRequest =
        options?.gameId !== undefined || options?.signal !== undefined;
      const isCurrentRequest = () =>
        !options?.signal?.aborted &&
        get().gameId === expectedGameId &&
        (options?.gameId === undefined || useSessionStore.getState().gameId === expectedGameId);
      try {
        const result = await useSessionStore.getState().syncState(options);
        if (!isCurrentRequest()) return;
        if (result && result.event) {
          const newOptions = result.event.options || [];
          const currentStoryText = useEventStore.getState().storyText;
          const backendStory = result.event.story || result.eventStory || "";
          const restoredStory = backendStory || currentStoryText;

          if (newOptions.length > 0) {
            if (backendStory && backendStory !== currentStoryText) {
              useEventStore.getState().setStoryText(backendStory);
            }
            useEventStore.getState().setCurrentEvent({
              ...result.event,
              story: restoredStory,
            });
          }

          if (!useEventStore.getState().storyText && restoredStory) {
            useEventStore.getState().setStoryText(restoredStory);
          }

          const currentEvent = useEventStore.getState().currentEvent;
          if (newOptions.length > 0 && restoredStory && currentEvent?.story !== restoredStory) {
            useEventStore.getState().setCurrentEvent({
              ...result.event,
              story: restoredStory,
            });
          }
        }
        if (isCurrentRequest()) get()._syncFromSubStores();
      } catch (err) {
        const sessionGameId = useSessionStore.getState().gameId;
        const legacyRequestClearedSession =
          !isRunOwnedRequest && sessionGameId === null && get().gameId === null;
        if (!legacyRequestClearedSession && !isCurrentRequest()) return;
        // On 404 error, session store clears its state - also clear event store
        if (sessionGameId === null) {
          useEventStore.getState().clearCurrentEvent();
        }
        get()._syncFromSubStores();
        throw err;
      }
    },

    syncPlayerState: async () => {
      const prevGameId = useSessionStore.getState().gameId;
      const result = await useSessionStore.getState().syncPlayerState();
      
      // If syncPlayerState recovered from 404, it calls loadGameState which
      // updates session state but not event state. We need to handle that case.
      // Check if game was reloaded (result is undefined on 404 recovery)
      if (result === undefined && prevGameId !== null) {
        // Clear event store on 404 recovery - the new state should be clean
        useEventStore.getState().clearCurrentEvent();
      }
      
      get()._syncFromSubStores();
      return result;
    },

    saveGame: () => useSessionStore.getState().saveGame(),

    resetGame: () => {
      useSessionStore.getState().resetSession();
      useEventStore.getState().clearCurrentEvent();
      useCharacterStore.getState().resetCreation();
      get()._syncFromSubStores();
    },

    // ==================== Event Actions ====================
    setCurrentEvent: (event) => {
      useEventStore.getState().setCurrentEvent(event);
      get()._syncFromSubStores();
    },

    appendStoryText: (text) => {
      useEventStore.getState().appendStoryText(text);
      set({ storyText: useEventStore.getState().storyText });
    },

    setStoryText: (text) => {
      useEventStore.getState().setStoryText(text);
      set({ storyText: text });
    },

    clearCurrentEvent: () => {
      useEventStore.getState().clearCurrentEvent();
      set({ currentEvent: null, storyText: "" });
    },

    setGameOver: (over) => {
      useSessionStore.getState().setGameOver(over);
      set({ isGameOver: over });
    },

    generateSummary: async (weeks = 52) => {
      const gameId = useSessionStore.getState().gameId;
      if (!gameId) return;
      await useEventStore.getState().generateSummary(gameId, weeks);
      set({ lastSummary: useEventStore.getState().lastSummary });
    },

    clearSummary: () => {
      useEventStore.getState().clearSummary();
      set({ lastSummary: null });
    },

    // ==================== List Actions ====================
    fetchSavedGames: async () => {
      await useGameListStore.getState().fetchSavedGames();
      set({ savedGames: useGameListStore.getState().savedGames });
    },

    fetchPresets: async () => {
      await useGameListStore.getState().fetchPresets();
      set({ presets: useGameListStore.getState().presets });
    },

    deleteGame: async (gameId) => {
      await useGameListStore.getState().deleteGame(gameId);
      set({ savedGames: useGameListStore.getState().savedGames });
    },

    deletePreset: async (presetId) => {
      await useGameListStore.getState().deletePreset(presetId);
      set({ presets: useGameListStore.getState().presets });
    },

    // ==================== Character Actions ====================
    setCreationStep: (step) => {
      useCharacterStore.getState().setCreationStep(step);
      set({ creationStep: step });
    },

    nextCreationStep: () => {
      useCharacterStore.getState().nextCreationStep();
      set({ creationStep: useCharacterStore.getState().creationStep });
    },

    prevCreationStep: () => {
      useCharacterStore.getState().prevCreationStep();
      set({ creationStep: useCharacterStore.getState().creationStep });
    },

    updateCharacterSetting: (key, value) => {
      useCharacterStore.getState().updateCharacterSetting(key, value);
      set({ characterSettings: useCharacterStore.getState().characterSettings });
    },

    setPlayerName: (name) => {
      useCharacterStore.getState().setPlayerName(name);
      set({ playerName: name });
    },

    setLifeVision: (vision) => {
      useCharacterStore.getState().setLifeVision(vision);
      set({ lifeVision: vision });
    },

    setOpeningStory: (story) => {
      useCharacterStore.getState().setOpeningStory(story);
      set({ openingStory: story });
    },

    resetCreation: () => {
      useCharacterStore.getState().resetCreation();
      useSessionStore.getState().resetSession();
      useEventStore.getState().clearCurrentEvent();
      get()._syncFromSubStores();
    },

    loadPreset: (preset) => {
      useCharacterStore.getState().loadPreset(preset);
      useSessionStore.getState().resetSession();
      useEventStore.getState().clearCurrentEvent();
      get()._syncFromSubStores();
    },

    // ==================== Game Settings Actions ====================
    setEnableSceneImage: (enabled) => {
      useSessionStore.getState().setEnableSceneImage(enabled);
      set({ enableSceneImage: enabled });
    },

    setConstraintLevel: (level) => {
      useSessionStore.getState().setConstraintLevel(level);
      set({ constraintLevel: level });
    },

    generateRoundSceneImage: async (roundNumber, storyText, stage = 'result') => {
      const { gameId, progress, enableSceneImage } = useSessionStore.getState();
      const { characterSettings, playerName } = useCharacterStore.getState();
      const week = (progress?.week as number) ?? 0;

      if (!gameId) return;

      await useSceneImageStore.getState().generateRoundSceneImage({
        gameId,
        roundNumber,
        storyText,
        characterSettings,
        playerName,
        enableSceneImage,
        week,
        stage,
      });
      get()._syncFromSubStores();
    },

    // ==================== Scene Image Actions ====================
    setCurrentRoundSceneImage: (image) => {
      useSceneImageStore.getState().setCurrentRoundSceneImage(image);
      set({ currentRoundSceneImage: image });
    },

    setEventSceneImage: (image) => {
      useSceneImageStore.getState().setEventSceneImage(image);
      set({ eventSceneImage: image });
    },

    setResultSceneImage: (image) => {
      useSceneImageStore.getState().setResultSceneImage(image);
      set({ resultSceneImage: image });
    },

    addRoundSceneImage: (image) => {
      useSceneImageStore.getState().addRoundSceneImage(image);
      set({ roundSceneImages: useSceneImageStore.getState().roundSceneImages });
    },

    fetchRoundSceneImage: async (roundNumber, stage, options) => {
      const { gameId, progress } = useSessionStore.getState();
      if (!gameId) return;
      const week = (progress?.week as number) ?? 0;
      await useSceneImageStore
        .getState()
        .fetchRoundSceneImage(gameId, roundNumber, week, stage, options);
      get()._syncFromSubStores();
    },

    fetchAllRoundSceneImages: async () => {
      const { gameId, progress, roundInfo } = useSessionStore.getState();
      if (!gameId) return;
      const currentRound = (roundInfo?.current_round as number) ?? 0;
      const currentWeek = (progress?.week as number) ?? 0;
      await useSceneImageStore.getState().fetchAllRoundSceneImages(gameId, currentRound, currentWeek);
      get()._syncFromSubStores();
    },

    regenerateRoundSceneImage: async (roundNumber, userPrompt) => {
      const { gameId } = useSessionStore.getState();
      const { characterSettings, playerName } = useCharacterStore.getState();
      const storyText = useEventStore.getState().storyText;

      if (!gameId) return;
      await useSceneImageStore.getState().regenerateRoundSceneImage({
        gameId,
        roundNumber,
        storyText,
        characterSettings,
        playerName,
        userPrompt,
      });
      get()._syncFromSubStores();
    },

    clearImageCache: () => {
      useSceneImageStore.getState().clearImageCache();
      get()._syncFromSubStores();
    },

    // ==================== History Scene Image Actions ====================
    fetchHistorySceneImage: async (week, round, stage) => {
      const gameId = useSessionStore.getState().gameId;
      if (!gameId) return;
      await useSceneImageStore.getState().fetchHistorySceneImage(gameId, week, round, stage);
      get()._syncFromSubStores();
    },

    generateHistorySceneImage: async (week, round, storyText, stage = 'result') => {
      const { gameId, enableSceneImage } = useSessionStore.getState();
      const { characterSettings, playerName } = useCharacterStore.getState();

      if (!gameId) return;
      await useSceneImageStore.getState().generateHistorySceneImage({
        gameId,
        week,
        round,
        storyText,
        characterSettings,
        playerName,
        enableSceneImage,
        stage,
      });
      get()._syncFromSubStores();
    },

    regenerateHistorySceneImage: async (week, round, storyText, userPrompt, sceneId) => {
      const gameId = useSessionStore.getState().gameId;
      const { characterSettings, playerName } = useCharacterStore.getState();

      if (!gameId) return;
      await useSceneImageStore.getState().regenerateHistorySceneImage({
        gameId,
        week,
        round,
        storyText,
        characterSettings,
        playerName,
        userPrompt,
        sceneId,
      });
      get()._syncFromSubStores();
    },

    setHistorySceneImage: (image) => {
      useSceneImageStore.getState().setHistorySceneImage(image);
      set({ historySceneImage: image });
    },
  })
);

// ==================== Subscription for State Sync ====================
// Subscribe to sub-stores to trigger re-renders when their state changes

useSessionStore.subscribe(() => {
  useGameStore.getState()._syncFromSubStores();
});

useEventStore.subscribe(() => {
  useGameStore.getState()._syncFromSubStores();
});

useCharacterStore.subscribe(() => {
  useGameStore.getState()._syncFromSubStores();
});

useGameListStore.subscribe(() => {
  useGameStore.getState()._syncFromSubStores();
});

useSceneImageStore.subscribe(() => {
  useGameStore.getState()._syncFromSubStores();
});

// ★ 立即同步一次，确保初始持久化状态被反映到 useGameStore
useGameStore.getState()._syncFromSubStores();
