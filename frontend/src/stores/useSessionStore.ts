/**
 * useSessionStore — 游戏会话状态管理
 *
 * 管理游戏会话的核心状态：gameId, sessionId, playerState, progress, roundInfo
 *
 * ★ 注意：此 store 不再持久化到 localStorage
 * - 游戏状态通过 Cookie 认证从服务器获取
 */
import { create } from "zustand";
import type {
  GameStateResponse,
  EventOption,
  PlayerState,
  GameProgress,
  RoundInfo,
  CharacterSettings,
  CurrentEventData,
} from "@/lib/types";
import api from "@/lib/api";

// 浅比较辅助函数
const KEY_FIELDS = ["energy", "mood", "knowledge", "wealth", "age", "week", "current_round"];

function shallowChanged(
  newVal: PlayerState | GameProgress | RoundInfo | null,
  oldVal: PlayerState | GameProgress | RoundInfo | null,
  keyFields: string[] = KEY_FIELDS
): boolean {
  if (newVal === oldVal) return false;
  if (!newVal || !oldVal) return true;
  return keyFields.some((key) => (newVal as Record<string, unknown>)[key] !== (oldVal as Record<string, unknown>)[key]);
}

export interface SessionState {
  // Game session
  gameId: number | null;
  sessionId: string | null;
  playerState: PlayerState | null;
  progress: GameProgress | null;
  roundInfo: RoundInfo | null;
  isGameOver: boolean;

  // ★ 游戏设置
  enableSceneImage: boolean;
  constraintLevel: "fast" | "expert" | "master";

  // Actions
  setGameId: (gameId: number) => void;
  setGameSession: (gameId: number, sessionId: string) => void;
  loadGameState: (gameId: number) => Promise<{
    event: { story: string; options: EventOption[] } | null;
    storyText: string;
    characterSettings?: CharacterSettings;
    playerName?: string;
    constraintLevel?: "fast" | "expert" | "master";
  }>;
  syncState: () => Promise<{
    event: { story: string; options: EventOption[] } | null;
    hasNewOptions: boolean;
    eventStory?: string;
  } | void>;
  syncPlayerState: () => Promise<unknown>;
  saveGame: () => Promise<void>;
  resetSession: () => void;
  setGameOver: (over: boolean) => void;
  setEnableSceneImage: (enabled: boolean) => void;
  setConstraintLevel: (level: "fast" | "expert" | "master") => void;
}

export const useSessionStore = create<SessionState>()(
  (set, get) => ({
    // Initial State
    gameId: null,
    sessionId: null,
    playerState: null,
    progress: null,
    roundInfo: null,
    isGameOver: false,
    enableSceneImage: true,
    constraintLevel: "expert",

    // Actions
    setGameId: (gameId) => set({ gameId }),
    setGameSession: (gameId, sessionId) => set({ gameId, sessionId }),

    loadGameState: async (gameId) => {
      console.log(`[loadGameState] Loading game ${gameId}...`);
      const state: GameStateResponse = await api.games.load(gameId);
      const rawEvent = state.current_event as CurrentEventData | null;
      const event = rawEvent
        ? {
            story: rawEvent.event_description || rawEvent.story_text || "",
            options: (rawEvent.options || []),
          }
        : null;

      const playerState = state.player_state;

      let storyText = event?.story || "";
      if (!storyText) {
        const lastRoundStory = playerState?.last_round_full_story;
        if (lastRoundStory) {
          storyText = lastRoundStory;
          console.log(`[loadGameState] Restored story from last_round_full_story (${lastRoundStory.length} chars)`);
        } else {
          const roundHistory = playerState?.round_history;
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

      // 提取 character_settings
      const loadedCharacterSettings = playerState?.character_settings;
      const loadedPlayerName = playerState?.player_name;

      set({
        gameId: state.game_id,
        playerState: state.player_state,
        progress: state.progress,
        roundInfo: state.round_info,
        isGameOver: false,
        constraintLevel: state.constraint_level || "expert",
      });
      console.log(`[loadGameState] Loaded game ${gameId}`);

      // 返回需要由其他 store 处理的数据
      return {
        event,
        storyText,
        characterSettings: loadedCharacterSettings,
        playerName: loadedPlayerName,
        constraintLevel: state.constraint_level || "expert",
      };
    },

    syncState: async () => {
      const { gameId } = get();
      console.log(`[syncState] Syncing game ${gameId}`);
      if (!gameId) return;

      let state;
      try {
        state = await api.gameplay.getState(gameId);
      } catch (err) {
        const error = err as { status?: number; message?: string };
        if (error.status === 404 || String(error.message || "").includes("404")) {
          console.warn("[syncState] Session expired (404), reloading game to restore session...");
          try {
            const loaded = await get().loadGameState(gameId);
            console.log("[syncState] Game reloaded successfully");
            return {
              event: loaded.event,
              hasNewOptions: (loaded.event?.options?.length ?? 0) > 0,
              eventStory: loaded.storyText,
            };
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
                isGameOver: false,
              });
            }
            throw reloadErr;
          }
        }
        throw err;
      }

      const rawEvent = state.current_event as CurrentEventData | null;
      const event = rawEvent
        ? {
            story: rawEvent.event_description || rawEvent.story_text || "",
            options: (rawEvent.options || []),
          }
        : null;

      const currentState = get();
      const updates: Partial<SessionState> = {};

      if (shallowChanged(state.player_state, currentState.playerState)) {
        updates.playerState = state.player_state;
      }
      if (shallowChanged(state.progress, currentState.progress, ["week", "current_round", "rounds_per_week"])) {
        updates.progress = state.progress;
      }
      if (shallowChanged(state.round_info, currentState.roundInfo, ["current_round", "week"])) {
        updates.roundInfo = state.round_info;
      }
      if (state.constraint_level && state.constraint_level !== currentState.constraintLevel) {
        updates.constraintLevel = state.constraint_level;
      }

      if (Object.keys(updates).length > 0) {
        console.log(`[syncState] Updating fields: ${Object.keys(updates).join(', ')}`);
        set(updates as SessionState);
      } else {
        console.log('[syncState] No updates needed');
      }

      // 返回事件数据供调用方处理
      return {
        event,
        hasNewOptions: (event?.options?.length ?? 0) > 0,
        eventStory: event?.story,
      };
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
            console.log("[syncPlayerState] Game reloaded");
            return;
          } catch (reloadErr) {
            console.error("[syncPlayerState] Failed to reload game:", reloadErr);
            throw reloadErr;
          }
        }
        throw err;
      }

      const currentState = get();
      const updates: Partial<SessionState> = {};

      if (shallowChanged(state.player_state, currentState.playerState)) {
        updates.playerState = state.player_state;
      }
      if (shallowChanged(state.progress, currentState.progress, ["week", "current_round", "rounds_per_week"])) {
        updates.progress = state.progress;
      }
      if (shallowChanged(state.round_info, currentState.roundInfo, ["current_round", "week"])) {
        updates.roundInfo = state.round_info;
      }
      if (state.constraint_level && state.constraint_level !== currentState.constraintLevel) {
        updates.constraintLevel = state.constraint_level;
      }

      if (Object.keys(updates).length > 0) {
        console.log(`[syncPlayerState] Updating fields: ${Object.keys(updates).join(', ')}`);
        set(updates as SessionState);
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

    resetSession: () =>
      set({
        gameId: null,
        sessionId: null,
        playerState: null,
        progress: null,
        roundInfo: null,
        isGameOver: false,
      }),

    setGameOver: (over) => set({ isGameOver: over }),
    setEnableSceneImage: (enabled) => set({ enableSceneImage: enabled }),
    setConstraintLevel: async (level) => {
      const { gameId } = get();
      if (gameId) {
        try {
          await api.games.updateSettings(gameId, { constraint_level: level });
        } catch (err) {
          console.error("[setConstraintLevel] Failed to update settings:", err);
        }
      }
      set({ constraintLevel: level });
    },
  })
);
