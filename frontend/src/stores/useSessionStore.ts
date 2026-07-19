/**
 * useSessionStore — 游戏会话状态管理
 *
 * 管理游戏会话的核心状态：gameId, sessionId, playerState, progress, roundInfo
 *
 * ★ 同步持久化 gameId / playerState 到 localStorage（key: "game-store"）
 * - 初始化时同步读取，避免异步 hydration 竞态
 * - 状态变化时自动写回 localStorage
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
import { resolveRecoveredStoryText } from "@/lib/sessionRecovery";
import api from "@/lib/api";

// ★ 同步读取 localStorage 中的持久化数据
const PERSIST_KEY = "game-store";

function _readPersistedState(): { gameId: number | null; playerState: PlayerState | null } {
  if (typeof window === "undefined") return { gameId: null, playerState: null };
  try {
    const raw = window.localStorage.getItem(PERSIST_KEY);
    if (!raw) return { gameId: null, playerState: null };
    const data = JSON.parse(raw);
    return {
      gameId: data?.state?.gameId ?? null,
      playerState: data?.state?.playerState ?? null,
    };
  } catch {
    return { gameId: null, playerState: null };
  }
}

function _writePersistedState(gameId: number | null, playerState: PlayerState | null): void {
  if (typeof window === "undefined") return;
  try {
    const data = { state: { gameId, playerState }, version: 0 };
    window.localStorage.setItem(PERSIST_KEY, JSON.stringify(data));
  } catch { /* ignore quota errors */ }
}

const _persisted = _readPersistedState();

// 浅比较辅助函数
const KEY_FIELDS = ["energy", "mood", "knowledge", "wealth", "age", "week", "current_round"];

function resumeViewChanged(
  newVal: PlayerState | GameProgress | RoundInfo,
  oldVal: PlayerState | GameProgress | RoundInfo
): boolean {
  const nextResumeView = (newVal as PlayerState).resume_view ?? null;
  const previousResumeView = (oldVal as PlayerState).resume_view ?? null;
  return JSON.stringify(nextResumeView) !== JSON.stringify(previousResumeView);
}

function shallowChanged(
  newVal: PlayerState | GameProgress | RoundInfo | null,
  oldVal: PlayerState | GameProgress | RoundInfo | null,
  keyFields: string[] = KEY_FIELDS
): boolean {
  if (newVal === oldVal) return false;
  if (!newVal || !oldVal) return true;
  return (
    keyFields.some((key) => (newVal as Record<string, unknown>)[key] !== (oldVal as Record<string, unknown>)[key]) ||
    resumeViewChanged(newVal, oldVal)
  );
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
    // Initial State — 同步从 localStorage 恢复
    gameId: _persisted.gameId,
    sessionId: null,
    playerState: _persisted.playerState,
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

      const storyText = resolveRecoveredStoryText({
        eventStory: event?.story,
        playerState,
        progress: state.progress,
        roundInfo: state.round_info,
      });

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

// ★ 自动持久化：当 gameId 或 playerState 变化时写回 localStorage
useSessionStore.subscribe((state, prevState) => {
  if (state.gameId !== prevState.gameId || state.playerState !== prevState.playerState) {
    _writePersistedState(state.gameId, state.playerState);
  }
});
