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
export const SESSION_PERSIST_VERSION = 1;
const RETIRED_WEALTH_KEYS = new Set([
  "wealth",
  "wealth_ledger",
  "_active_wealth_transaction_id",
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stripRetiredWealthKeys(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(stripRetiredWealthKeys);
  if (!isRecord(value)) return value;
  return Object.fromEntries(
    Object.entries(value)
      .filter(([key]) => !RETIRED_WEALTH_KEYS.has(key))
      .map(([key, nested]) => [key, stripRetiredWealthKeys(nested)])
  );
}

function hasRetiredWealthKeys(value: unknown): boolean {
  if (Array.isArray(value)) return value.some(hasRetiredWealthKeys);
  if (!isRecord(value)) return false;
  return Object.entries(value).some(
    ([key, nested]) => RETIRED_WEALTH_KEYS.has(key) || hasRetiredWealthKeys(nested)
  );
}

interface PersistedSessionState {
  state: { gameId: number | null; playerState: PlayerState | null };
  version: number;
}

export function migratePersistedSessionState(value: unknown): PersistedSessionState {
  const root = isRecord(value) ? value : {};
  const state = isRecord(root.state) ? root.state : {};
  const gameId = typeof state.gameId === "number" ? state.gameId : null;
  const cleanedPlayerState = stripRetiredWealthKeys(state.playerState);
  return {
    state: {
      gameId,
      playerState: isRecord(cleanedPlayerState) ? cleanedPlayerState as PlayerState : null,
    },
    version: SESSION_PERSIST_VERSION,
  };
}

function _readPersistedState(): { gameId: number | null; playerState: PlayerState | null } {
  if (typeof window === "undefined") return { gameId: null, playerState: null };
  try {
    const raw = window.localStorage.getItem(PERSIST_KEY);
    if (!raw) return { gameId: null, playerState: null };
    const migrated = migratePersistedSessionState(JSON.parse(raw));
    window.localStorage.setItem(PERSIST_KEY, JSON.stringify(migrated));
    return migrated.state;
  } catch {
    return { gameId: null, playerState: null };
  }
}

function _writePersistedState(gameId: number | null, playerState: PlayerState | null): void {
  if (typeof window === "undefined") return;
  try {
    const data = migratePersistedSessionState({ state: { gameId, playerState } });
    window.localStorage.setItem(PERSIST_KEY, JSON.stringify(data));
  } catch { /* ignore quota errors */ }
}

const _persisted = _readPersistedState();

type RecoveredCurrentEvent = {
  story: string;
  options: EventOption[];
  event_id?: string;
  revision?: number;
  story_date?: string;
};

function recoverCurrentEvent(rawEvent: CurrentEventData | null): RecoveredCurrentEvent | null {
  if (!rawEvent) return null;
  return {
    story: rawEvent.event_description || rawEvent.story_text || "",
    options: rawEvent.options || [],
    ...(rawEvent.event_id ? { event_id: rawEvent.event_id } : {}),
    ...(typeof rawEvent.revision === "number" ? { revision: rawEvent.revision } : {}),
    ...(rawEvent.story_date ? { story_date: rawEvent.story_date } : {}),
  };
}

// 浅比较辅助函数
const KEY_FIELDS = [
  "energy", "mood", "knowledge", "wealth", "age", "week", "current_round",
  "timeline_version", "timeline", "day_history",
];

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
    event: RecoveredCurrentEvent | null;
    storyText: string;
    characterSettings?: CharacterSettings;
    playerName?: string;
    constraintLevel?: "fast" | "expert" | "master";
  }>;
  syncState: (options?: { gameId?: number; signal?: AbortSignal }) => Promise<{
    event: RecoveredCurrentEvent | null;
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
      const event = recoverCurrentEvent(rawEvent);

      const playerState = stripRetiredWealthKeys(state.player_state) as PlayerState;

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
        playerState,
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

    syncState: async (options) => {
      const gameId = options?.gameId ?? get().gameId;
      const isCurrentRequest = () =>
        !options?.signal?.aborted && get().gameId === gameId;
      console.log(`[syncState] Syncing game ${gameId}`);
      if (!gameId) return;

      let state;
      try {
        state = await api.gameplay.getState(gameId, options?.signal);
        if (!isCurrentRequest()) return;
      } catch (err) {
        if (!isCurrentRequest()) return;
        const error = err as { status?: number; message?: string };
        if (error.status === 404 || String(error.message || "").includes("404")) {
          // A run-owned initialization must never enter the legacy mutating
          // reload path. Its caller decides how to recover after rechecking
          // the captured game/run identity.
          if (options?.gameId !== undefined || options?.signal) {
            throw err;
          }
          console.warn("[syncState] Session expired (404), reloading game to restore session...");
          try {
            const loaded = await get().loadGameState(gameId);
            if (!isCurrentRequest()) return;
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
      const event = recoverCurrentEvent(rawEvent);

      const currentState = get();
      const updates: Partial<SessionState> = {};

      const playerState = stripRetiredWealthKeys(state.player_state) as PlayerState;
      if (
        hasRetiredWealthKeys(currentState.playerState) ||
        shallowChanged(playerState, currentState.playerState)
      ) {
        updates.playerState = playerState;
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

      if (!isCurrentRequest()) return;
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

      const playerState = stripRetiredWealthKeys(state.player_state) as PlayerState;
      if (
        hasRetiredWealthKeys(currentState.playerState) ||
        shallowChanged(playerState, currentState.playerState)
      ) {
        updates.playerState = playerState;
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
