"use client";

import { useGameStore } from "@/stores/useGameStore";
import { gameplay } from "@/lib/api";
import type { EventOption } from "@/lib/types";
import type { Phase } from "./usePhaseManager";
import { checkAndClearRetry } from "./eventUtils";

// ==================== Types ====================

export interface ChoiceErrorContext {
  optionIndex?: number;
  customText?: string;
  isRetry: boolean;
  sseSucceeded: boolean;
  baseStoryText?: string;
  retryChoice?: () => Promise<void>;
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
}

// ==================== Error Parsing ====================

/**
 * 解析 SSE 错误为消息字符串
 */
export function parseSSEError(err: unknown): string {
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
  return (
    errorMsg === "Unknown error" ||
    normalized.includes("network error") ||
    normalized.includes("failed to fetch") ||
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
  const { setRoundSummary, setSummaryText, setCurrentEvent, setGameOver, setOptions, setPhase, setProcessing, setConnectionStatus } = handlers;

  setProcessing(false);
  setConnectionStatus(null);

  // ★ 检查是否发生了重试，如果重试后强制使用后端故事
  const wasRetry = checkAndClearRetry();
  if (wasRetry) {
    console.log("[handleChoiceComplete] Retry detected, keeping replacement stream text");
  }

  const resourceWarningText = formatResourceWarnings(result);
  if (result.summary && typeof result.summary === "string") {
    setRoundSummary(`${result.summary}${resourceWarningText}`);
  } else if (resourceWarningText) {
    setRoundSummary(resourceWarningText.trim());
  } else {
    setRoundSummary(null);
  }

  setCurrentEvent(null);

  // ★ 故事完成后，异步生成结果插画 (stage='result')
  const state = useGameStore.getState();
  const roundNumber = (state.roundInfo?.current_round as number) || 0;
  const storyText = state.storyText;
  
  if (roundNumber >= 0 && storyText) {
    // 异步生成，不阻塞主流程
    useGameStore.getState().generateRoundSceneImage(roundNumber, storyText, 'result').catch(err => {
      console.error('[handleChoiceComplete] Scene image generation failed:', err);
    });
  }

  // ★ 同步 player_state 以获取最新的 week/round 等状态
  // 这确保前端显示的周数与后端一致
  useGameStore.getState().syncPlayerState().catch(err => {
    console.warn('[handleChoiceComplete] Failed to sync player state:', err);
  });

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
}

// ==================== Story Recovery ====================

/**
 * 从 round_history 恢复故事续写
 */
export async function recoverStoryFromRoundHistory(
  choiceText: string,
  setStoryText: (text: string) => void,
  baseStoryText?: string
): Promise<boolean> {
  try {
    // syncPlayerState updates the store, then we read from it
    await useGameStore.getState().syncPlayerState();
    const playerState = useGameStore.getState().playerState;
    const roundHistory = playerState?.round_history as
      | Array<{ story_continuation?: string }>
      | undefined;

    if (roundHistory && roundHistory.length > 0) {
      const latestRound = roundHistory[roundHistory.length - 1];
      if (latestRound.story_continuation) {
        const currentStory = baseStoryText ?? useGameStore.getState().storyText;
        const continuation = `\n\n--- 主角选择了：${choiceText} ---\n\n${latestRound.story_continuation}`;
        setStoryText(currentStory + continuation);
        console.log(`[recoverStory] Found story continuation (${latestRound.story_continuation.length} chars)`);
        return true;
      }
    }
    return false;
  } catch (err) {
    console.error("[recoverStory] Failed:", err);
    return false;
  }
}

// ==================== Error Handlers ====================

/**
 * 进入结果阶段
 */
export function enterResultPhase(handlers: ChoiceHandlers): void {
  const { setProcessing, setOptions, setCurrentEvent, setPhase, generatingRef } = handlers;
  setProcessing(false);
  generatingRef.current = false;
  setOptions([]);
  setCurrentEvent(null);
  setPhase("result");
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
  console.log(`[${logPrefix}] Choice already processed, attempting to sync state...`);
  await recoverStoryFromRoundHistory(choiceText, handlers.setStoryText, baseStoryText);
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
  console.log(`[${logPrefix}] No current event - attempting to sync state...`);
  await recoverStoryFromRoundHistory(choiceText, handlers.setStoryText, baseStoryText);
  enterResultPhase(handlers);
}

/**
 * 处理 session 过期错误
 */
export async function handleSessionExpired(
  handlers: ChoiceHandlers,
  context: ChoiceErrorContext,
  logPrefix: string
): Promise<boolean> {
  const { setProcessing, setOptions, setCurrentEvent, setPhase } = handlers;
  
  try {
    setProcessing(true, "恢复游戏状态...");
    await useGameStore.getState().syncState();
    setProcessing(false);

    const state = useGameStore.getState();
    
    // 如果有 currentEvent，可以重试
    if (state.currentEvent?.options?.length && context.retryChoice) {
      await context.retryChoice();
      return true;
    }
    
    // 没有 currentEvent，进入结果阶段
    console.log(`[${logPrefix}] No currentEvent after restore, entering result phase...`);
    setOptions([]);
    setCurrentEvent(null);
    setPhase("result");
    return true;
  } catch (restoreErr) {
    console.error(`[${logPrefix}] Failed to restore session:`, restoreErr);
    enterResultPhase(handlers);
    return true;
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
      result = await gameplay.makeCustomChoiceSync(gameId, { custom_text: context.customText });
    } else if (context.optionIndex !== undefined) {
      result = await gameplay.makeChoiceSync(gameId, { option_index: context.optionIndex });
    } else {
      return false;
    }

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
    console.error(`[${logPrefix}] Fallback also failed:`, fallbackErr);
    const fallbackErrMsg = parseSSEError(fallbackErr);

    if (fallbackErrMsg.includes("No current event") || fallbackErrMsg.includes("choice_already_processed")) {
      console.log(`[${logPrefix}] Choice fallback found already-processed state, entering result phase...`);
      const choiceText = context.customText ??
        useGameStore.getState().currentEvent?.options?.[context.optionIndex ?? 0]?.text ??
        "";
      await recoverStoryFromRoundHistory(choiceText, handlers.setStoryText, context.baseStoryText);
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
        context.baseStoryText
      );
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
  const errorMsg = parseSSEError(err);
  console.log(`[${logPrefix}] onError: "${errorMsg}"`);

  const { setProcessing, setConnectionStatus, setPhase } = handlers;

  // 1. 选择已处理
  if (errorMsg.includes("choice_already_processed")) {
    const choiceText = context.customText ?? 
      useGameStore.getState().currentEvent?.options?.[context.optionIndex ?? 0]?.text ?? 
      "";
    await handleChoiceAlreadyProcessed(choiceText, handlers, logPrefix, context.baseStoryText);
    return;
  }

  // 2. 无当前事件
  if (errorMsg.includes("No current event")) {
    const choiceText = context.customText ?? 
      useGameStore.getState().currentEvent?.options?.[context.optionIndex ?? 0]?.text ?? 
      "";
    await handleNoCurrentEvent(choiceText, handlers, logPrefix, context.baseStoryText);
    return;
  }

  // 3. Session 过期
  const isSessionExpired = errorMsg.includes("404") || errorMsg.includes("No active game session");
  if (isSessionExpired) {
    const handled = await handleSessionExpired(handlers, context, logPrefix);
    if (handled) return;
  }

  // 4. Fallback
  if (context.sseSucceeded && isRecoverableChoiceStreamError(errorMsg)) {
    const choiceText = context.customText ??
      useGameStore.getState().currentEvent?.options?.[context.optionIndex ?? 0]?.text ??
      "";
    const recovered = await recoverStoryFromRoundHistory(
      choiceText,
      handlers.setStoryText,
      context.baseStoryText
    );
    if (recovered) {
      enterResultPhase(handlers);
      return;
    }
  }

  if (!context.sseSucceeded || isRecoverableChoiceStreamError(errorMsg)) {
    const handled = await handleFallbackChoice(gameId, context, handlers, logPrefix);
    if (handled) return;
  }

  // 5. 最终错误
  if (context.isRetry || !errorMsg.includes("404")) {
    console.error(`${logPrefix} SSE error:`, err);
  }

  setProcessing(false);
  setConnectionStatus("error");
  setPhase("error");
}
