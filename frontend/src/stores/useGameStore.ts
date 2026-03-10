/**
 * useGameStore — 游戏核心会话状态
 * 
 * 管理游戏会话的核心状态：gameId, sessionId, playerState, progress, roundInfo
 * 
 * 注意：此文件已拆分为多个专门的 store：
 * - useEventStore: 事件和故事状态
 * - useImageStore: 图片相关状态
 * - useCharacterStore: 角色创建状态
 * - useGameListStore: 存档和预设列表
 * 
 * 本文件保持向后兼容，组合所有子 store 的功能。
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type {
  GameEvent,
  GameStateResponse,
  GameListItem,
  PresetInfo,
  EventOption,
  ImageResponse,
  OpeningIllustrationResponse,
} from "@/lib/types";
import api from "@/lib/api";

// Import sub-stores for re-export
export { useEventStore } from "./useEventStore";
export { useImageStore, type RoundSceneImage } from "./useImageStore";
export { useCharacterStore, CREATION_STEPS, MANUAL_STEPS, AUTO_ADVANCE_STEPS, type CreationStep } from "./useCharacterStore";
export { useGameListStore } from "./useGameListStore";

// Import sub-store types
import { useEventStore } from "./useEventStore";
import { useImageStore, type RoundSceneImage } from "./useImageStore";
import { useCharacterStore, CREATION_STEPS, MANUAL_STEPS, AUTO_ADVANCE_STEPS, type CreationStep } from "./useCharacterStore";
import { useGameListStore } from "./useGameListStore";

// 浅比较辅助函数
const KEY_FIELDS = ["energy", "mood", "knowledge", "wealth", "age", "week", "current_round"];

function shallowChanged(
  newVal: Record<string, unknown> | null,
  oldVal: Record<string, unknown> | null,
  keyFields: string[] = KEY_FIELDS
): boolean {
  if (newVal === oldVal) return false;
  if (!newVal || !oldVal) return true;
  return keyFields.some((key) => newVal[key] !== oldVal[key]);
}

// ==================== Backward Compatible Combined Store ====================

interface GameState {
  // Game session
  gameId: number | null;
  sessionId: string | null;
  playerState: Record<string, unknown> | null;
  progress: Record<string, unknown> | null;
  roundInfo: Record<string, unknown> | null;
  isGameOver: boolean;

  // Event
  currentEvent: GameEvent | null;
  storyText: string;
  lastSummary: Record<string, unknown> | null;

  // Saves & presets
  savedGames: GameListItem[];
  presets: PresetInfo[];

  // Character creation
  creationStep: number;
  characterSettings: Record<string, unknown>;
  playerName: string;
  lifeVision: string;
  openingStory: string;
  isPresetLoaded: boolean;
  
  // ★ 游戏设置
  enableSceneImage: boolean;  // 是否自动生成每轮场景插画
  
  // ★ 场景插画（玩家形象和开场插画由 useImageStore 管理）
  roundSceneImages: RoundSceneImage[];
  currentRoundSceneImage: RoundSceneImage | null;
  eventSceneImage: RoundSceneImage | null;  // ★ 事件插画
  resultSceneImage: RoundSceneImage | null;  // ★ 结果插画
  isLoadingRoundSceneImage: boolean;
  isRegeneratingRoundScene: boolean;
  roundSceneRegenerateError: string | null;

  // Actions — Session
  setGameId: (gameId: number) => void;
  setGameSession: (gameId: number, sessionId: string) => void;
  loadGameState: (gameId: number) => Promise<void>;
  syncState: () => Promise<void>;
  syncPlayerState: () => Promise<GameStateResponse | undefined>;
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
  generateRoundSceneImage: (roundNumber: number, storyText: string, stage?: string) => Promise<void>;
  
  // Actions — Scene Images（玩家形象和开场插画方法由 useImageStore 提供）
  fetchRoundSceneImage: (roundNumber: number, stage?: string) => Promise<void>;  // ★ 支持 stage
  fetchAllRoundSceneImages: () => Promise<void>;
  setCurrentRoundSceneImage: (image: RoundSceneImage | null) => void;
  setEventSceneImage: (image: RoundSceneImage | null) => void;  // ★ 设置事件插画
  setResultSceneImage: (image: RoundSceneImage | null) => void;  // ★ 设置结果插画
  addRoundSceneImage: (image: RoundSceneImage) => void;
  regenerateRoundSceneImage: (roundNumber: number, userPrompt: string) => Promise<void>;
  clearImageCache: () => void;  // ★ 清理图片缓存
}

export const useGameStore = create<GameState>()(
  persist(
    (set, get) => ({
      // ==================== Initial State ====================
      // Session
      gameId: null,
      sessionId: null,
      playerState: null,
      progress: null,
      roundInfo: null,
      isGameOver: false,

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
      
      // ★ 游戏设置
      enableSceneImage: true,  // 默认开启自动生成场景插画

      // ★ 场景插画（玩家形象和开场插画由 useImageStore 管理）
      roundSceneImages: [],
      currentRoundSceneImage: null,
      eventSceneImage: null,  // ★ 事件插画
      resultSceneImage: null,  // ★ 结果插画
      isLoadingRoundSceneImage: false,
      isRegeneratingRoundScene: false,
      roundSceneRegenerateError: null,

      // ==================== Game Settings Actions ====================
      setEnableSceneImage: (enabled: boolean) => set({ enableSceneImage: enabled }),
      
      generateRoundSceneImage: async (roundNumber: number, storyText: string, stage: string = 'result') => {
        const { gameId, characterSettings, playerName, enableSceneImage, progress } = get();
        // ★ 从 useImageStore 获取玩家形象
        const { playerImages, selectedImageIndex } = useImageStore.getState();

        if (!gameId || !storyText) {
          console.error("[generateRoundSceneImage] Missing gameId or storyText");
          return;
        }

        if (!enableSceneImage) {
          console.log("[generateRoundSceneImage] Scene image generation disabled");
          return;
        }

        // ★ 获取当前周数
        const week = (progress?.week as number) ?? 0;
        console.log(`[generateRoundSceneImage] Generating scene for week ${week}, round ${roundNumber}, stage=${stage}...`);

        try {
          const selectedImage = playerImages[selectedImageIndex] || playerImages[0];
          const playerImageId = selectedImage?.image_id;

          const result = await api.images.generateRoundSceneImage({
            game_id: gameId,
            round_number: roundNumber,
            story_text: storyText,
            character_settings: characterSettings,
            player_name: playerName,
            player_image_id: playerImageId,
            stage,  // ★ 传递 stage 参数
            week,  // ★ 传递 week 参数
          });
          
          const newScene: RoundSceneImage = {
            scene_id: result.scene_id,
            week: result.week || week,  // ★ 使用返回的 week 或传入的 week
            round_number: result.round_number,
            stage: result.stage || stage,  // ★ 使用返回的 stage 或传入的 stage
            image_url: result.image_url,
            scene_description: result.scene_description,
            referenced_images: [],
            created_at: result.created_at,
          };

          set((state) => ({
            currentRoundSceneImage: newScene,
            // ★ 根据 stage 更新对应的状态
            eventSceneImage: newScene.stage === 'event' ? newScene : state.eventSceneImage,
            resultSceneImage: newScene.stage === 'result' ? newScene : state.resultSceneImage,
            // ★ 同一周同一轮次同一 stage 的插画应该唯一
            roundSceneImages: state.roundSceneImages.some(s => s.week === newScene.week && s.round_number === roundNumber && s.stage === newScene.stage)
              ? state.roundSceneImages.map(s => s.week === newScene.week && s.round_number === roundNumber && s.stage === newScene.stage ? newScene : s)
              : [...state.roundSceneImages, newScene],
          }));
          
          console.log(`[generateRoundSceneImage] Scene generated: scene_id=${result.scene_id}`);
        } catch (err) {
          console.error(`[generateRoundSceneImage] Failed:`, err);
          // 静默失败，不阻塞游戏流程
        }
      },

      // ==================== Session Actions ====================
      setGameId: (gameId) => set({ gameId }),
      setGameSession: (gameId, sessionId) => set({ gameId, sessionId }),

      loadGameState: async (gameId) => {
        console.log(`[loadGameState] Loading game ${gameId}...`);
        const state: GameStateResponse = await api.games.load(gameId);
        const rawEvent = state.current_event as Record<string, unknown> | null;
        const event = rawEvent
          ? {
              story: (rawEvent.event_description as string) || (rawEvent.story as string) || "",
              options: ((rawEvent.options as EventOption[]) || []),
            }
          : null;

        // ★ 提前定义 playerState，避免重复定义
        const playerState = state.player_state as Record<string, unknown>;

        let storyText = event?.story || "";
        if (!storyText) {
          const lastRoundStory = playerState?.last_round_full_story as string;
          if (lastRoundStory) {
            storyText = lastRoundStory;
            console.log(`[loadGameState] Restored story from last_round_full_story (${lastRoundStory.length} chars)`);
          } else {
            const roundHistory = playerState?.round_history as Array<{event_description?: string; story_continuation?: string}>;
            if (roundHistory && roundHistory.length > 0) {
              const lastRound = roundHistory[roundHistory.length - 1];
              const eventDesc = lastRound?.event_description || "";
              const continuation = lastRound?.story_continuation || "";
              storyText = eventDesc + (continuation ? "\n\n" + continuation : "");
              console.log(`[loadGameState] Restored story from round_history (${storyText.length} chars)`);
            }
          }
        }

        console.log(`[loadGameState] Backend event: hasEvent=${!!event}, storyLen=${event?.story.length || 0}`);
        console.log(`[loadGameState] Final storyText: ${storyText.length} chars`);

        // ★ 从 player_state 中提取 character_settings，确保切换游戏后角色设定正确
        const loadedCharacterSettings = playerState?.character_settings as Record<string, unknown> | undefined;
        const loadedPlayerName = playerState?.player_name as string | undefined;

        set({
          gameId: state.game_id,
          playerState: state.player_state,
          progress: state.progress,
          roundInfo: state.round_info,
          currentEvent: event,
          storyText: storyText,
          isGameOver: false,
          // ★ 更新 characterSettings 和 playerName，避免使用旧游戏的设定
          ...(loadedCharacterSettings && { characterSettings: loadedCharacterSettings }),
          ...(loadedPlayerName && { playerName: loadedPlayerName }),
          // ★ 清空旧游戏的场景插画，避免跨游戏数据泄漏
          roundSceneImages: [],
          currentRoundSceneImage: null,
          eventSceneImage: null,
          resultSceneImage: null,
        });
        console.log(`[loadGameState] Loaded game ${gameId}`);
        
        // ★ 异步加载该游戏的人物图片到 useImageStore
        try {
          const images = await api.images.listByGame(gameId, 'character');
          if (images.images && images.images.length > 0) {
            useImageStore.getState().setPlayerImages(images.images);
            console.log(`[loadGameState] Loaded ${images.images.length} player images for game ${gameId}`);
          }
        } catch (imgErr) {
          console.warn(`[loadGameState] Failed to load player images:`, imgErr);
        }
      },

      syncState: async () => {
        const { gameId, storyText: localStoryText } = get();
        console.log(`[syncState] Syncing game ${gameId}, local storyLen=${localStoryText.length}`);
        if (!gameId) return;
        
        let state;
        try {
          state = await api.gameplay.getState(gameId);
        } catch (err) {
          const error = err as { status?: number; message?: string };
          if (error.status === 404 || String(error.message || "").includes("404")) {
            console.warn("[syncState] Session expired (404), reloading game to restore session...");
            try {
              await get().loadGameState(gameId);
              console.log("[syncState] Game reloaded successfully");
              return;
            } catch (reloadErr) {
              const reloadError = reloadErr as { status?: number; message?: string };
              console.error("[syncState] Failed to reload game:", reloadError);
              if (reloadError.status === 404 || String(reloadError.message || "").includes("not found")) {
                console.warn("[syncState] Game no longer exists in database, clearing local state...");
                set({
                  gameId: null,
                  playerState: null,
                  progress: null,
                  roundInfo: null,
                  currentEvent: null,
                  storyText: "",
                  isGameOver: false,
                });
              }
              throw reloadErr;
            }
          }
          throw err;
        }

        const rawEvent = state.current_event as Record<string, unknown> | null;
        const event = rawEvent
          ? {
              story: (rawEvent.event_description as string) || (rawEvent.story as string) || "",
              options: ((rawEvent.options as EventOption[]) || []),
            }
          : null;

        const currentState = get();
        const updates: Partial<GameState> = {};
        
        if (shallowChanged(state.player_state, currentState.playerState)) {
          updates.playerState = state.player_state;
        }
        if (shallowChanged(state.progress, currentState.progress, ["week", "current_round", "rounds_per_week"])) {
          updates.progress = state.progress;
        }
        if (shallowChanged(state.round_info, currentState.roundInfo, ["current_round", "week"])) {
          updates.roundInfo = state.round_info;
        }

        if (event) {
          const currentOptions = currentState.currentEvent?.options || [];
          const newOptions = event.options || [];
          const hasNewOptions = newOptions.length > 0 && currentOptions.length === 0;
          
          if (hasNewOptions) {
            updates.currentEvent = {
              ...event,
              story: currentState.storyText || event.story,
            };
          }
          
          if (!currentState.storyText && event.story) {
            updates.storyText = event.story;
          }
        }

        if (Object.keys(updates).length > 0) {
          console.log(`[syncState] Updating fields: ${Object.keys(updates).join(', ')}`);
          set(updates as GameState);
        } else {
          console.log('[syncState] No updates needed');
        }
      },

      syncPlayerState: async () => {
        const { gameId } = get();
        console.log(`[syncPlayerState] Syncing player state for game ${gameId}`);
        if (!gameId) return;
        
        let state;
        try {
          state = await api.gameplay.getState(gameId);
        } catch (err) {
          const error = err as { status?: number; message?: string };
          if (error.status === 404 || String(error.message || "").includes("404")) {
            console.warn("[syncPlayerState] Session expired (404), reloading game to restore session...");
            try {
              await get().loadGameState(gameId);
              set({ currentEvent: null, storyText: "" });
              console.log("[syncPlayerState] Game reloaded, currentEvent cleared");
              return;
            } catch (reloadErr) {
              console.error("[syncPlayerState] Failed to reload game:", reloadErr);
              throw reloadErr;
            }
          }
          throw err;
        }

        const currentState = get();
        const updates: Partial<GameState> = {};
        
        if (shallowChanged(state.player_state, currentState.playerState)) {
          updates.playerState = state.player_state;
        }
        if (shallowChanged(state.progress, currentState.progress, ["week", "current_round", "rounds_per_week"])) {
          updates.progress = state.progress;
        }
        if (shallowChanged(state.round_info, currentState.roundInfo, ["current_round", "week"])) {
          updates.roundInfo = state.round_info;
        }

        if (Object.keys(updates).length > 0) {
          console.log(`[syncPlayerState] Updating fields: ${Object.keys(updates).join(', ')}`);
          set(updates as GameState);
        } else {
          console.log('[syncPlayerState] No updates needed');
        }
        
        return state;
      },

      saveGame: async () => {
        const { gameId } = get();
        if (!gameId) return;
        await api.games.save(gameId);
      },

      resetGame: () =>
        set({
          gameId: null,
          sessionId: null,
          playerState: null,
          progress: null,
          roundInfo: null,
          currentEvent: null,
          storyText: "",
          isGameOver: false,
          creationStep: 0,
          characterSettings: {},
          playerName: "",
          lifeVision: "",
          openingStory: "",
          isPresetLoaded: false,
          // ★ 玩家形象由 useImageStore 管理
        }),

      // ==================== Event Actions ====================
      setCurrentEvent: (event) => {
        if (event === null) {
          set({ currentEvent: null });
          return;
        }
        
        const currentStory = get().storyText;
        const newStory = currentStory || event.story || "";
        const newEvent: GameEvent = { 
          story: newStory, 
          options: event.options || [] 
        };
        
        const currentEvent = get().currentEvent;
        if (JSON.stringify(newEvent) !== JSON.stringify(currentEvent) || newStory !== currentStory) {
          set({ currentEvent: newEvent, storyText: newStory });
        }
      },

      appendStoryText: (text) => {
        const prev = get().storyText;
        const next = prev + text;
        console.log(`[STORY] append +${text.length} chars (total: ${prev.length} → ${next.length})`);
        set({ storyText: next });
      },

      setStoryText: (text) => {
        const prev = get().storyText;
        if (text !== prev) {
          const action = text.length === 0 ? 'CLEAR' : (text.length < prev.length ? 'TRUNCATE' : 'SET');
          console.log(`[STORY] ${action}: ${prev.length} → ${text.length} chars`);
          set({ storyText: text });
        }
      },

      clearCurrentEvent: () => set({ currentEvent: null, storyText: "" }),

      setGameOver: (over) => set({ isGameOver: over }),

      generateSummary: async (weeks = 52) => {
        const { gameId } = get();
        if (!gameId) return;
        try {
          const result = await api.gameplay.generateSummary(gameId, { weeks });
          set({ lastSummary: result as unknown as Record<string, unknown> });
        } catch (err) {
          console.error("[generateSummary] Failed:", err);
          throw err;
        }
      },

      clearSummary: () => set({ lastSummary: null }),

      // ==================== List Actions ====================
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

      // ==================== Character Actions ====================
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
          gameId: null,
          sessionId: null,
          storyText: "",
          currentEvent: null,
          playerState: null,
          progress: null,
          roundInfo: null,
          isGameOver: false,
          // ★ 玩家形象由 useImageStore 管理
        }),

      loadPreset: (preset) =>
        set({
          playerName: preset.player_name,
          lifeVision: preset.life_vision || "",
          characterSettings: preset.character_settings,
          creationStep: MANUAL_STEPS.length,
          isPresetLoaded: true,
          openingStory: "",
          gameId: null,
          sessionId: null,
          storyText: "",
          currentEvent: null,
          playerState: null,
          progress: null,
          roundInfo: null,
          isGameOver: false,
          // ★ 玩家形象由 useImageStore 管理
        }),

      // ==================== Scene Image Actions ====================
      setCurrentRoundSceneImage: (image) => set({ currentRoundSceneImage: image }),
      setEventSceneImage: (image) => set({ eventSceneImage: image }),  // ★ 设置事件插画
      setResultSceneImage: (image) => set({ resultSceneImage: image }),  // ★ 设置结果插画
      addRoundSceneImage: (image) => set((state) => ({
        roundSceneImages: [...state.roundSceneImages, image],
      })),
      
      fetchRoundSceneImage: async (roundNumber: number, stage?: string) => {
        const { gameId, progress } = get();
        if (!gameId) return;
        
        // ★ 获取当前周数
        const week = (progress?.week as number) ?? 0;
        
        set({ isLoadingRoundSceneImage: true });
        
        try {
          // ★ 使用支持 stage 和 week 的 API
          const scene = stage 
            ? await api.images.getRoundSceneImageByStage(gameId, roundNumber, stage, week)
            : await api.images.getRoundSceneImage(gameId, roundNumber, week);
            
          if (scene && scene.scene_id) {
            // ★ 确保 stage 和 week 字段存在
            const sceneWithStage: RoundSceneImage = {
              scene_id: scene.scene_id,
              week: scene.week || week,
              round_number: scene.round_number,
              stage: scene.stage || stage || 'result',
              image_url: scene.image_url,
              scene_description: scene.scene_description,
              referenced_images: (scene as { referenced_images?: number[] }).referenced_images || [],
              created_at: scene.created_at,
            };
            
            set((state) => ({
              currentRoundSceneImage: sceneWithStage,
              // ★ 根据 stage 更新对应的状态
              eventSceneImage: sceneWithStage.stage === 'event' ? sceneWithStage : state.eventSceneImage,
              resultSceneImage: sceneWithStage.stage === 'result' ? sceneWithStage : state.resultSceneImage,
              // ★ 同一周同一轮次同一 stage 的插画应该唯一
              roundSceneImages: state.roundSceneImages.some(s => s.week === sceneWithStage.week && s.round_number === roundNumber && s.stage === sceneWithStage.stage)
                ? state.roundSceneImages.map(s => s.week === sceneWithStage.week && s.round_number === roundNumber && s.stage === sceneWithStage.stage ? sceneWithStage : s)
                : [...state.roundSceneImages, sceneWithStage],
              isLoadingRoundSceneImage: false,
            }));
          } else {
            set({ isLoadingRoundSceneImage: false });
          }
        } catch (err) {
          const error = err as { status?: number };
          if (error.status !== 404) {
            console.error(`[fetchRoundSceneImage] Failed:`, err);
          }
          set({ isLoadingRoundSceneImage: false });
        }
      },
      
      fetchAllRoundSceneImages: async () => {
        const { gameId, roundInfo, progress } = get();
        if (!gameId) return;
        
        set({ isLoadingRoundSceneImage: true });
        
        try {
          const result = await api.images.getAllRoundSceneImages(gameId);
          // ★ 确保 stage 字段存在
          const scenes: RoundSceneImage[] = (result.scenes || []).map(s => ({
            ...s,
            stage: s.stage || 'result',
          }));
          
          // ★ 根据当前轮次和周数设置 currentRoundSceneImage、eventSceneImage、resultSceneImage
          const currentRound = (roundInfo?.current_round as number) ?? 0;
          const currentWeek = (progress?.week as number) ?? 0;
          
          // ★ 查找当前周+当前轮次的插画
          const currentEventScene = scenes.find(
            s => s.week === currentWeek && s.round_number === currentRound && s.stage === 'event'
          ) || null;
          const currentResultScene = scenes.find(
            s => s.week === currentWeek && s.round_number === currentRound && s.stage === 'result'
          ) || null;
          const currentScene = currentEventScene || currentResultScene || 
            scenes.find(s => s.round_number === currentRound) || null;
          
          set({ 
            roundSceneImages: scenes, 
            currentRoundSceneImage: currentScene,
            eventSceneImage: currentEventScene,
            resultSceneImage: currentResultScene,
            isLoadingRoundSceneImage: false 
          });
        } catch (err) {
          console.error("[fetchAllRoundSceneImages] Failed:", err);
          set({ isLoadingRoundSceneImage: false });
        }
      },
      
      regenerateRoundSceneImage: async (roundNumber: number, userPrompt: string) => {
        const { gameId, storyText, characterSettings, playerName, currentRoundSceneImage, fetchRoundSceneImage } = get();
        // ★ 从 useImageStore 获取玩家形象
        const { playerImages, selectedImageIndex } = useImageStore.getState();
        
        if (!gameId || !currentRoundSceneImage) {
          console.error("[regenerateRoundSceneImage] Missing required data");
          return;
        }
        
        set({ isRegeneratingRoundScene: true, roundSceneRegenerateError: null });
        
        try {
          const selectedImage = playerImages[selectedImageIndex] || playerImages[0];
          const playerImageId = selectedImage?.image_id;
          
          const result = await api.images.regenerateRoundSceneImage({
            game_id: gameId,
            round_number: roundNumber,
            story_text: storyText,
            character_settings: characterSettings,
            player_name: playerName,
            user_prompt: userPrompt,
            current_scene_id: currentRoundSceneImage.scene_id,
            player_image_id: playerImageId,
          });

          // ★ 使用响应中的数据，添加时间戳确保 URL 唯一
          const timestamp = Date.now();
          const updatedScene: RoundSceneImage = {
            scene_id: result.scene_id,
            week: result.week ?? currentRoundSceneImage.week ?? 0,
            round_number: result.round_number,
            stage: result.stage ?? currentRoundSceneImage.stage ?? 'result',
            image_url: result.image_url,
            scene_description: result.scene_description,
            referenced_images: [],
            created_at: result.created_at || new Date(timestamp).toISOString(),
          };

          console.log("[regenerateRoundSceneImage] Success:", {
            new_url: result.image_url,
            old_url: currentRoundSceneImage.image_url,
            created_at: updatedScene.created_at,
          });

          set((state) => ({
            currentRoundSceneImage: updatedScene,
            roundSceneImages: state.roundSceneImages.map(s =>
              s.scene_id === currentRoundSceneImage.scene_id ? updatedScene : s
            ),
            isRegeneratingRoundScene: false,
          }));
        } catch (err) {
          const errorMsg = err instanceof Error ? err.message : "场景插画重新生成失败";
          console.error("[regenerateRoundSceneImage] Error:", errorMsg);
          set({ isRegeneratingRoundScene: false, roundSceneRegenerateError: errorMsg });
        }
      },

      // ★ 清理图片缓存
      clearImageCache: () => {
        console.log("[clearImageCache] Clearing image cache...");
        set({
          roundSceneImages: [],
          currentRoundSceneImage: null,
          eventSceneImage: null,
          resultSceneImage: null,
          isLoadingRoundSceneImage: false,
          isRegeneratingRoundScene: false,
          roundSceneRegenerateError: null,
        });
        // ★ 同时清理 useImageStore 的缓存
        useImageStore.getState().clearCache?.();
        console.log("[clearImageCache] Image cache cleared");
      },
    }),
    {
      name: "game-storage",
      partialize: (state) => ({
        // ★ gameId 不再持久化，每次从服务器获取当前活跃游戏
        sessionId: state.sessionId,
        characterSettings: state.characterSettings,
        playerName: state.playerName,
        lifeVision: state.lifeVision,
        openingStory: state.openingStory,
        creationStep: state.creationStep,
        isPresetLoaded: state.isPresetLoaded,
        // ★ 持久化 roundInfo 和 progress，确保刷新后能正确加载图片
        roundInfo: state.roundInfo,
        progress: state.progress,
        // ★ 玩家形象由 useImageStore 持久化
      }),
    }
  )
);
