import { resolveApiBase } from "@/lib/apiBase";
import type {
  EventOption,
  GameProgress,
  PlayerState,
  RoundInfo,
} from "@/lib/types";

export interface PersistedEventSnapshot {
  story: string;
  options: EventOption[];
  gameOver: boolean;
}

export interface GameplayStateSnapshot {
  event: PersistedEventSnapshot | null;
  playerState: PlayerState | null;
  progress: GameProgress | null;
  roundInfo: RoundInfo | null;
  gameOver: boolean;
}

function createRequestSignal(
  parentSignal: AbortSignal,
  timeoutMs?: number,
): {
  signal: AbortSignal;
  didTimeOut: () => boolean;
  cleanup: () => void;
} {
  if (timeoutMs === undefined) {
    return {
      signal: parentSignal,
      didTimeOut: () => false,
      cleanup: () => undefined,
    };
  }

  const controller = new AbortController();
  let timedOut = false;
  const abortFromParent = () => controller.abort();
  if (parentSignal.aborted) {
    controller.abort();
  } else {
    parentSignal.addEventListener("abort", abortFromParent, { once: true });
  }
  const timeoutId = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, Math.max(0, timeoutMs));

  return {
    signal: controller.signal,
    didTimeOut: () => timedOut,
    cleanup: () => {
      clearTimeout(timeoutId);
      parentSignal.removeEventListener("abort", abortFromParent);
    },
  };
}

export async function fetchGameplayStateSnapshot(
  gameId: number,
  parentSignal: AbortSignal,
  timeoutMs?: number,
): Promise<GameplayStateSnapshot> {
  const request = createRequestSignal(parentSignal, timeoutMs);
  try {
    const response = await fetch(`${resolveApiBase()}/games/${gameId}`, {
      method: "GET",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      signal: request.signal,
    });

    if (!response.ok) {
      throw Object.assign(new Error(`HTTP error! status: ${response.status}`), {
        status: response.status,
      });
    }

    const state = await response.json() as {
      current_event?: {
        event_description?: unknown;
        story_text?: unknown;
        story?: unknown;
        options?: unknown;
      } | null;
      player_state?: unknown;
      progress?: { week?: unknown; total_weeks?: unknown } | null;
      round_info?: unknown;
    };
    const playerState = state.player_state && typeof state.player_state === "object"
      ? state.player_state as PlayerState
      : null;
    const progress = state.progress && typeof state.progress === "object"
      ? state.progress as GameProgress
      : null;
    const roundInfo = state.round_info && typeof state.round_info === "object"
      ? state.round_info as RoundInfo
      : null;
    const resumePhase = playerState?.resume_view?.phase;
    const progressWeek = state.progress?.week;
    const totalWeeks = state.progress?.total_weeks;
    const gameOver = resumePhase === "ending" || (
      typeof progressWeek === "number" &&
      typeof totalWeeks === "number" &&
      totalWeeks > 0 &&
      progressWeek >= totalWeeks
    );
    const event = state.current_event;
    if (!event) {
      return { event: null, playerState, progress, roundInfo, gameOver };
    }

    const storyCandidates = [event.event_description, event.story_text, event.story];
    const story = storyCandidates.find(
      (value): value is string => typeof value === "string" && value.trim().length > 0,
    )?.trim() ?? "";
    const options = Array.isArray(event.options) ? event.options as EventOption[] : [];
    return {
      event: { story, options, gameOver },
      playerState,
      progress,
      roundInfo,
      gameOver,
    };
  } catch (error) {
    if (request.didTimeOut() && !parentSignal.aborted) {
      throw new Error("Persisted gameplay snapshot request timed out");
    }
    throw error;
  } finally {
    request.cleanup();
  }
}

export async function fetchPersistedEventSnapshot(
  gameId: number,
  signal: AbortSignal,
  timeoutMs?: number,
): Promise<PersistedEventSnapshot | null> {
  const snapshot = await fetchGameplayStateSnapshot(gameId, signal, timeoutMs);
  if (snapshot.event) return snapshot.event;
  if (snapshot.gameOver) {
    return { story: "", options: [], gameOver: true };
  }
  return null;
}
