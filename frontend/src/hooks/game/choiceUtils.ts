"use client";

import { useGameStore } from "@/stores/useGameStore";
import { gameplay } from "@/lib/api";
import type { EventOption } from "@/lib/types";
import type { Phase } from "./usePhaseManager";
import type { NarrativeTransportState } from "@/components/narrative-loading/NarrativeLoadingState";
import {
  fetchGameplayStateSnapshot,
  fetchPersistedEventSnapshot,
} from "./eventRecovery";
import { isAbortError } from "./gameplayRun";

// ==================== Types ====================

export interface ChoiceErrorContext {
  optionIndex?: number;
  customText?: string;
  isRetry: boolean;
  sseSucceeded: boolean;
  baseStoryText?: string;
  retryChoice?: () => Promise<void>;
  signal?: AbortSignal;
  allowSyncFallback?: boolean;
}

export interface ChoiceHandlers {
  setProcessing: (processing: boolean, message?: string) => void;
  setConnectionStatus: (status: "connecting" | "connected" | "reconnecting" | "error" | null) => void;
  setReconnectAttempt: (attempt: { current: number; max: number } | null) => void;
  setRoundSummary: (summary: string | null) => void;
  setSummaryText: (text: string) => void;
  setCurrentEvent: (event: { story: string; options: EventOption[] } | null) => void;
  setGameOver: (gameOver: boolean) => void;
  setOptions: (options: EventOption[]) => void;
  setStoryText: (text: string) => void;
  setPhase: (phase: Phase | ((prev: Phase) => Phase)) => void;
  generatingRef: React.MutableRefObject<boolean>;
  hadRetryRef?: React.MutableRefObject<boolean>;
  isCurrentRun?: () => boolean;
  setTransport?: (transport: NarrativeTransportState) => void;
  gameId?: number;
  signal?: AbortSignal;
}

function isCurrentChoiceRun(handlers: ChoiceHandlers): boolean {
  return handlers.isCurrentRun?.() ?? true;
}

// ==================== Error Parsing ====================

/**
 * 解析 SSE 错误为消息字符串
 */
export function parseSSEError(err: unknown): string {
  if (err instanceof Error && err.message) {
    return err.message;
  }
  const isEmptyObject = err && typeof err === 'object' && Object.keys(err as object).length === 0;
  if (isEmptyObject) {
    return "Unknown error";
  }
  const errAsRecord = err as Record<string, unknown>;
  return String(
    (err as { message?: string })?.message ||
    errAsRecord?.error ||
    err ||
    "Unknown error"
  );
}

export function isRecoverableChoiceStreamError(errorMsg: string): boolean {
  const normalized = errorMsg.toLowerCase();
  const httpStatus = Number.parseInt(normalized.match(/status:\s*(\d{3})/)?.[1] ?? "", 10);
  return (
    (Number.isFinite(httpStatus) && httpStatus >= 500) ||
    errorMsg === "Unknown error" ||
    normalized.includes("network error") ||
    normalized.includes("failed to fetch") ||
    normalized.includes("timeout processing choice") ||
    normalized.includes("empty_response") ||
    normalized.includes("err_empty_response") ||
    normalized.includes("incomplete_chunked_encoding") ||
    normalized.includes("err_incomplete_chunked_encoding") ||
    normalized.includes("terminated") ||
    normalized.includes("stream")
  );
}

function formatResourceWarnings(result: Record<string, unknown>): string {
  const warnings = result.resource_warnings;
  if (!Array.isArray(warnings) || warnings.length === 0) {
    return "";
  }

  const lines = warnings
    .map((warning) => {
      if (!warning || typeof warning !== "object") {
        return "";
      }
      const warningRecord = warning as Record<string, unknown>;
      const message = warningRecord.message;
      if (typeof message === "string" && message.trim()) {
        return `- ${message.trim()}`;
      }

      const displayName =
        typeof warningRecord.display_name === "string" ? warningRecord.display_name : "资源";
      const appliedDelta =
        typeof warningRecord.applied_delta === "number"
          ? `${warningRecord.applied_delta >= 0 ? "+" : ""}${warningRecord.applied_delta}`
          : "受限";
      return `- ${displayName}受限，实际变化为 ${appliedDelta}`;
    })
    .filter((line): line is string => Boolean(line));

  return lines.length ? `\n\n**资源提示**\n${lines.join("\n")}` : "";
}

// ==================== Choice Completion ====================

/**
 * 处理选择完成后的状态更新
 */
export function handleChoiceComplete(
  result: Record<string, unknown>,
  handlers: ChoiceHandlers
): void {
  const { setRoundSummary, setSummaryText, setCurrentEvent, setGameOver, setOptions, setStoryText, setPhase, setProcessing, setConnectionStatus } = handlers;

  setProcessing(false);
  setConnectionStatus(null);

  const wasRetry = handlers.hadRetryRef?.current ?? false;
  if (handlers.hadRetryRef) handlers.hadRetryRef.current = false;
  if (wasRetry) {
    console.log("[handleChoiceComplete] Retry detected, keeping replacement stream text");
  }

  const _effectsApplied = result.effects_applied;
  const _bonusEffects = (result as Record<string, unknown>).bonus_effects;
  if (
    _effectsApplied &&
    typeof _effectsApplied === "object" &&
    !Array.isArray(_effectsApplied)
  ) {
    const entries = Object.entries(_effectsApplied as Record<string, unknown>);
    if (entries.length) {
      const effectSummary = entries
        .map(([key, value]) => {
          if (typeof value !== "number") {
            return `${key}:n/a`;
          }
          return `${key}:${value >= 0 ? "+" : ""}${value}`;
        })
        .join(", ");
      console.log("[handleChoiceComplete] effects_applied:", effectSummary);
    }
  }

  if (
    _bonusEffects &&
    typeof _bonusEffects === "object" &&
    !Array.isArray(_bonusEffects)
  ) {
    console.log("[handleChoiceComplete] bonus_effects:", _bonusEffects);
  }

  const resourceWarningText = formatResourceWarnings(result);
  const isDaily = Boolean(result.next_timeline);
  if (isDaily && result.effects_applied && typeof result.effects_applied === "object") {
    window.dispatchEvent(
      new CustomEvent("story2:daily-settlement", {
        detail: result.effects_applied,
      })
    );
  }
  if (result.summary && typeof result.summary === "string") {
    setRoundSummary(`${result.summary}${resourceWarningText}`);
  } else if (resourceWarningText) {
    setRoundSummary(resourceWarningText.trim());
  } else {
    setRoundSummary(null);
  }

  setCurrentEvent(null);

  // Legacy rounds have a result illustration; daily mode has one story image.
  const state = useGameStore.getState();
  const roundNumber = (state.roundInfo?.current_round as number) || 0;
  const storyText = state.storyText;
  
  if (!isDaily && roundNumber >= 0 && storyText) {
    // 异步生成，不阻塞主流程
    useGameStore.getState().generateRoundSceneImage(roundNumber, storyText, 'result').catch(err => {
      console.error('[handleChoiceComplete] Scene image generation failed:', err);
    });
  }

  // ★ 同步 player_state 以获取最新的 week/round 等状态
  // 这确保前端显示的周数与后端一致
  const syncPromise = useGameStore.getState().syncPlayerState().catch(err => {
    console.warn('[handleChoiceComplete] Failed to sync player state:', err);
  });

  if (isDaily && !result.game_over) {
    setOptions([]);
    setStoryText("");
    setPhase("loading");
    void syncPromise.then(() => {
      window.setTimeout(() => {
        window.dispatchEvent(new CustomEvent("story2:generate-next-day"));
      }, 350);
    });
    return;
  }

  if (result.need_weekly_summary && result.weekly_summary) {
    setSummaryText(result.weekly_summary as string);
    setPhase("summary");
  } else if (result.game_over) {
    setPhase("ending");
    setGameOver(true);
  } else {
    setOptions([]);
    setPhase("result");
  }
  handlers.generatingRef.current = false;
  handlers.setTransport?.("active");
  return true;
}

// ==================== Story Recovery ====================

/**
 * 从 round_history 恢复故事续写
 */
export async function recoverStoryFromRoundHistory(
  choiceText: string,
  setStoryText: (text: string) => void,
  baseStoryText?: string,
  isCurrentRun: () => boolean = () => true,
  recovery?: { gameId: number; signal: AbortSignal },
): Promise<boolean> {
  if (!isCurrentRun()) return false;
  try {
    let playerState: Record<string, unknown> | null | undefined;
    if (recovery) {
      const snapshot = await fetchGameplayStateSnapshot(recovery.gameId, recovery.signal);
      playerState = snapshot.playerState;
    } else {
      // Compatibility path for standalone callers outside a gameplay run.
      await useGameStore.getState().syncPlayerState();
      playerState = useGameStore.getState().playerState as Record<string, unknown> | null;
    }
    if (!isCurrentRun()) return false;
    const roundHistory = playerState?.round_history as
      | Array<{ choice?: string; story_continuation?: string }>
      | undefined;

    if (roundHistory && roundHistory.length > 0) {
      const normalizeChoice = (value?: string) => value?.trim().replace(/\s+/g, " ") ?? "";
      const expectedChoice = normalizeChoice(choiceText);
      const entriesWithChoice = roundHistory.filter((entry) => normalizeChoice(entry.choice));
      const latestRound =
        entriesWithChoice.length > 0
          ? [...entriesWithChoice].reverse().find((entry) => normalizeChoice(entry.choice) === expectedChoice)
          : roundHistory[roundHistory.length - 1];

      if (!latestRound && entriesWithChoice.length > 0) {
        console.warn("[recoverStory] No round history entry matched current choice; skipping stale recovery");
        return false;
      }

      if (!latestRound) {
        return false;
      }

      if (latestRound.story_continuation) {
        if (!isCurrentRun()) return false;
        const currentStory = baseStoryText ?? useGameStore.getState().storyText;
        const continuation = `\n\n--- 主角选择了：${choiceText} ---\n\n${latestRound.story_continuation}`;
        setStoryText(currentStory + continuation);
        console.log(`[recoverStory] Found story continuation (${latestRound.story_continuation.length} chars)`);
        return true;
      }
    }
    return false;
  } catch (err) {
    if (!isCurrentRun() || isAbortError(err)) return false;
    console.error("[recoverStory] Failed:", err);
    return false;
  }
}

function getStoryRecoveryRequest(
  handlers: ChoiceHandlers,
): { gameId: number; signal: AbortSignal } | undefined {
  return handlers.gameId !== undefined && handlers.signal
    ? { gameId: handlers.gameId, signal: handlers.signal }
    : undefined;
}

// ==================== Error Handlers ====================

/**
 * 进入结果阶段
 */
export function enterResultPhase(handlers: ChoiceHandlers): void {
  if (!isCurrentChoiceRun(handlers)) return;
  const { setProcessing, setOptions, setCurrentEvent, setPhase, generatingRef } = handlers;
  setProcessing(false);
  generatingRef.current = false;
  setOptions([]);
  setCurrentEvent(null);
  setPhase("result");
  handlers.setTransport?.("active");
}

/**
 * 处理 "choice_already_processed" 错误
 */
export async function handleChoiceAlreadyProcessed(
  choiceText: string,
  handlers: ChoiceHandlers,
  logPrefix: string,
  baseStoryText?: string
): Promise<void> {
  if (!isCurrentChoiceRun(handlers)) return;
  console.log(`[${logPrefix}] Choice already processed, attempting to sync state...`);
  await recoverStoryFromRoundHistory(
    choiceText,
    handlers.setStoryText,
    baseStoryText,
    () => isCurrentChoiceRun(handlers),
    getStoryRecoveryRequest(handlers),
  );
  if (!isCurrentChoiceRun(handlers)) return;
  enterResultPhase(handlers);
}

/**
 * 处理 "No current event" 错误
 */
export async function handleNoCurrentEvent(
  choiceText: string,
  handlers: ChoiceHandlers,
  logPrefix: string,
  baseStoryText?: string
): Promise<void> {
  if (!isCurrentChoiceRun(handlers)) return;
  console.log(`[${logPrefix}] No current event - attempting to sync state...`);
  await recoverStoryFromRoundHistory(
    choiceText,
    handlers.setStoryText,
    baseStoryText,
    () => isCurrentChoiceRun(handlers),
    getStoryRecoveryRequest(handlers),
  );
  if (!isCurrentChoiceRun(handlers)) return;
  enterResultPhase(handlers);
}

/**
 * 处理 session 过期错误
 */
export async function handleSessionExpired(
  gameId: number,
  handlers: ChoiceHandlers,
  context: ChoiceErrorContext,
  logPrefix: string
): Promise<boolean> {
  const { setProcessing, setOptions, setCurrentEvent, setPhase } = handlers;

  if (!isCurrentChoiceRun(handlers)) return true;
  try {
    setProcessing(true, "恢复游戏状态...");
    if (!context.signal) return false;
    const snapshot = await fetchPersistedEventSnapshot(gameId, context.signal);
    if (!isCurrentChoiceRun(handlers)) return true;
    setProcessing(false);

    if (snapshot?.gameOver) {
      setProcessing(false);
      handlers.generatingRef.current = false;
      setOptions([]);
      setCurrentEvent(null);
      handlers.setGameOver(true);
      setPhase("ending");
      handlers.setTransport?.("active");
      return true;
    }

    // 如果有 currentEvent，可以重试
    if (snapshot?.options.length) {
      if (!context.retryChoice) return false;
      await context.retryChoice();
      if (!isCurrentChoiceRun(handlers)) return true;
      return true;
    }
    
    // 没有 currentEvent，进入结果阶段
    console.log(`[${logPrefix}] No currentEvent after restore, entering result phase...`);
    setOptions([]);
    setCurrentEvent(null);
    setPhase("result");
    handlers.setTransport?.("active");
    return true;
  } catch (restoreErr) {
    if (!isCurrentChoiceRun(handlers) || isAbortError(restoreErr)) return true;
    console.error(`[${logPrefix}] Failed to restore session:`, restoreErr);
    setProcessing(false);
    return false;
  }
}

/**
 * Fallback 到同步 API
 */
export async function handleFallbackChoice(
  gameId: number,
  context: ChoiceErrorContext,
  handlers: ChoiceHandlers,
  logPrefix: string
): Promise<boolean> {
  const { setProcessing, setConnectionStatus } = handlers;

  if (!isCurrentChoiceRun(handlers)) return true;
  handlers.setTransport?.("polling");
  setProcessing(true, "fallback");
  setConnectionStatus(null);

  try {
    let result: {
      story_continuation?: string;
      summary?: string;
      need_weekly_summary?: boolean;
      weekly_summary?: string;
      game_over?: boolean;
    };

    if (context.customText !== undefined) {
      result = await gameplay.makeCustomChoiceSync(
        gameId,
        { custom_text: context.customText },
        context.signal,
      );
    } else if (context.optionIndex !== undefined) {
      const currentEvent = useGameStore.getState().currentEvent;
      result = await gameplay.makeChoiceSync(gameId, {
        option_index: context.optionIndex,
        event_id: currentEvent?.event_id,
        revision: currentEvent?.revision,
      });
    } else {
      return false;
    }

    if (!isCurrentChoiceRun(handlers)) return true;

    if (result.story_continuation) {
      const choiceText = context.customText ??
        useGameStore.getState().currentEvent?.options?.[context.optionIndex ?? 0]?.text ??
        "";
      const baseStory = context.baseStoryText ?? useGameStore.getState().storyText;
      handlers.setStoryText(
        `${baseStory}\n\n--- 主角选择了：${choiceText} ---\n\n${result.story_continuation}`
      );
    }

    handleChoiceComplete(result as Record<string, unknown>, handlers);
    return true;
  } catch (fallbackErr) {
    if (!isCurrentChoiceRun(handlers) || isAbortError(fallbackErr)) return true;
    console.error(`[${logPrefix}] Fallback also failed:`, fallbackErr);
    const fallbackErrMsg = parseSSEError(fallbackErr);

    if (fallbackErrMsg.includes("No current event") || fallbackErrMsg.includes("choice_already_processed")) {
      console.log(`[${logPrefix}] Choice fallback found already-processed state, entering result phase...`);
      const choiceText = context.customText ??
        useGameStore.getState().currentEvent?.options?.[context.optionIndex ?? 0]?.text ??
        "";
      await recoverStoryFromRoundHistory(
        choiceText,
        handlers.setStoryText,
        context.baseStoryText,
        () => isCurrentChoiceRun(handlers),
        getStoryRecoveryRequest(handlers),
      );
      if (!isCurrentChoiceRun(handlers)) return true;
      enterResultPhase(handlers);
      return true;
    }
    if (isRecoverableChoiceStreamError(fallbackErrMsg)) {
      console.log(`[${logPrefix}] Choice fallback had a transient network failure, attempting history recovery...`);
      const choiceText = context.customText ??
        useGameStore.getState().currentEvent?.options?.[context.optionIndex ?? 0]?.text ??
        "";
      const recovered = await recoverStoryFromRoundHistory(
        choiceText,
        handlers.setStoryText,
        context.baseStoryText,
        () => isCurrentChoiceRun(handlers),
        getStoryRecoveryRequest(handlers),
      );
      if (!isCurrentChoiceRun(handlers)) return true;
      if (recovered) {
        enterResultPhase(handlers);
        return true;
      }
    }
    return false;
  }
}

// ==================== Main Error Handler ====================

/**
 * 统一的错误处理入口
 */
export async function handleChoiceError(
  err: unknown,
  gameId: number,
  handlers: ChoiceHandlers,
  context: ChoiceErrorContext,
  logPrefix: string
): Promise<void> {
  if (!isCurrentChoiceRun(handlers) || isAbortError(err)) return;
  const errorMsg = parseSSEError(err);
  console.log(`[${logPrefix}] onError: "${errorMsg}"`);

  const { setProcessing, setConnectionStatus, setPhase } = handlers;

  // 1. 选择已处理
  if (errorMsg.includes("choice_already_processed")) {
    handlers.setTransport?.("polling");
    const choiceText = context.customText ?? 
      useGameStore.getState().currentEvent?.options?.[context.optionIndex ?? 0]?.text ?? 
      "";
    await handleChoiceAlreadyProcessed(choiceText, handlers, logPrefix, context.baseStoryText);
    return;
  }

  // 2. 无当前事件
  if (errorMsg.includes("No current event")) {
    handlers.setTransport?.("polling");
    const choiceText = context.customText ?? 
      useGameStore.getState().currentEvent?.options?.[context.optionIndex ?? 0]?.text ?? 
      "";
    await handleNoCurrentEvent(choiceText, handlers, logPrefix, context.baseStoryText);
    return;
  }

  // 3. Session 过期
  const isSessionExpired = errorMsg.includes("404") || errorMsg.includes("No active game session");
  if (isSessionExpired) {
    handlers.setTransport?.("polling");
    const handled = await handleSessionExpired(gameId, handlers, context, logPrefix);
    if (!isCurrentChoiceRun(handlers)) return;
    if (handled) return;
    if (context.allowSyncFallback === false) {
      setProcessing(false);
      setConnectionStatus("error");
      handlers.generatingRef.current = false;
      handlers.setTransport?.("failed");
      setPhase("error");
      return;
    }
  }

  // 4. Fallback
  if (context.sseSucceeded && isRecoverableChoiceStreamError(errorMsg)) {
    handlers.setTransport?.("polling");
    const choiceText = context.customText ??
      useGameStore.getState().currentEvent?.options?.[context.optionIndex ?? 0]?.text ??
      "";
    const recovered = await recoverStoryFromRoundHistory(
      choiceText,
      handlers.setStoryText,
      context.baseStoryText,
      () => isCurrentChoiceRun(handlers),
      getStoryRecoveryRequest(handlers),
    );
    if (!isCurrentChoiceRun(handlers)) return;
    if (recovered) {
      enterResultPhase(handlers);
      return;
    }
  }

  if (
    context.allowSyncFallback !== false &&
    (!context.sseSucceeded || isRecoverableChoiceStreamError(errorMsg))
  ) {
    const handled = await handleFallbackChoice(gameId, context, handlers, logPrefix);
    if (!isCurrentChoiceRun(handlers)) return;
    if (handled) return;
  }

  // 5. 最终错误
  if (context.isRetry || !errorMsg.includes("404")) {
    console.error(`${logPrefix} SSE error:`, err);
  }

  setProcessing(false);
  setConnectionStatus("error");
  handlers.generatingRef.current = false;
  handlers.setTransport?.("failed");
  setPhase("error");
}
