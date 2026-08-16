"use client";

import { useState, useCallback, useRef } from "react";
import { useGameStore } from "@/stores/useGameStore";
import { useSceneImageStore } from "@/stores/useSceneImageStore";
import { streamRegenerate, type GenerationFailurePayload } from "@/lib/sse";
import api from "@/lib/api";
import type { EventOption, StoryDeliveryNotice } from "@/lib/types";
import type { Phase } from "./usePhaseManager";
import {
  INITIAL_DAILY_GENERATION_COMMAND,
  isCompleteClientEvent,
  type DailyGenerationCommandState,
  type DailyGenerationMode,
} from "./dailyGenerationCommand";

interface ToastState {
  type: "success" | "error" | "loading";
  message: string;
}

interface UseGameStateParams {
  gameId: number | null;
  isGameOver: boolean;
  setPhase: (phase: Phase | ((prev: Phase) => Phase)) => void;
  setStoryText: (text: string) => void;
  appendStoryText: (text: string) => void;
  setCurrentEvent: (event: { story: string; options: EventOption[]; event_id?: string; revision?: number; story_date?: string; delivery_notice?: StoryDeliveryNotice } | null) => void;
  setOptions: (options: EventOption[]) => void;
  setProcessing: (processing: boolean, message?: string) => void;
  generatingRef: React.MutableRefObject<boolean>;
  prefetchAbortRef: React.MutableRefObject<AbortController | null>;
  prefetchResultRef: React.MutableRefObject<{
    story: string;
    options: EventOption[];
    event: { story: string; options: EventOption[] } | null;
  } | null>;
  prefetchingRef: React.MutableRefObject<boolean>;
  setIsPrefetching: (prefetching: boolean) => void;
  generateEventRef: React.MutableRefObject<(
    options?: { resume?: boolean; userInitiated?: boolean }
  ) => Promise<void>>;
  syncPlayerState: () => Promise<unknown>;
  dailyGenerationFlightRef?: React.MutableRefObject<Promise<void> | null>;
  setDailyGenerationCommand?: React.Dispatch<React.SetStateAction<DailyGenerationCommandState>>;
}

/**
 * Hook for managing game state persistence and transitions.
 * Handles save, continue, and regenerate operations.
 */
export function useGameState({
  gameId,
  isGameOver,
  setPhase,
  setStoryText,
  appendStoryText,
  setCurrentEvent,
  setOptions,
  setProcessing,
  generatingRef,
  prefetchAbortRef,
  prefetchResultRef,
  prefetchingRef,
  setIsPrefetching,
  generateEventRef,
  syncPlayerState,
  dailyGenerationFlightRef,
  setDailyGenerationCommand,
}: UseGameStateParams) {
  // Save state
  const [isSaving, setIsSaving] = useState(false);
  const [saveToast, setSaveToast] = useState<"success" | "error" | null>(null);

  // Regenerate toast state
  const [regenerateToast, setRegenerateToast] = useState<ToastState | null>(null);
  const [regenerationFailure, setRegenerationFailure] = useState<GenerationFailurePayload | null>(null);

  // Summary state
  const [summaryText, setSummaryText] = useState("");
  const [roundSummary, setRoundSummary] = useState<string | null>(null);

  // Ending data
  const [endingData] = useState<Record<string, unknown> | null>(null);

  // Regenerate abort controller
  const regenerateAbortRef = useRef<AbortController | null>(null);
  const regenerateLastEventIdRef = useRef<number | null>(null);
  const replacementBufferRef = useRef("");
  const localDailyGenerationFlightRef = useRef<Promise<void> | null>(null);
  const [localDailyGenerationCommand, setLocalDailyGenerationCommand] = useState(
    INITIAL_DAILY_GENERATION_COMMAND,
  );
  const activeDailyGenerationFlightRef =
    dailyGenerationFlightRef || localDailyGenerationFlightRef;
  const updateDailyGenerationCommand =
    setDailyGenerationCommand || setLocalDailyGenerationCommand;

  const startGenerationAfterSync = useCallback(async () => {
    if (!gameId) return;
    try {
      await api.gameplay.acknowledgeResumeView(gameId);
      await syncPlayerState();
      await generateEventRef.current();
    } catch (err) {
      console.error("[continue] Failed to acknowledge saved view:", err);
      setProcessing(false);
      setPhase("error");
    }
  }, [gameId, syncPlayerState, generateEventRef, setProcessing, setPhase]);

  // Save game
  const handleSave = async () => {
    setIsSaving(true);
    setSaveToast(null);
    try {
      await useGameStore.getState().saveGame();
      setSaveToast("success");
      setTimeout(() => setSaveToast(null), 2000);
    } catch (err) {
      console.error("Save failed:", err);
      setSaveToast("error");
      setTimeout(() => setSaveToast(null), 3000);
    } finally {
      setIsSaving(false);
    }
  };

  // Continue after summary
  const handleContinueAfterSummary = useCallback(() => {
    setSummaryText("");
    if (isGameOver) {
      setPhase("ending");
    } else {
      setCurrentEvent(null);
      setStoryText("");
      generatingRef.current = false;
      setPhase("loading");
      void startGenerationAfterSync();
    }
  }, [isGameOver, setPhase, setCurrentEvent, setStoryText, generatingRef, startGenerationAfterSync]);

  // Continue to next round
  const handleContinueToNextRound = useCallback(() => {
    console.log(`[handleContinueToNextRound] User clicked continue button`);
    setRoundSummary(null);

    // Exact resume semantics require the user acknowledgement to reach the
    // backend before the next event can exist. Discard any legacy prefetched
    // value created by older clients.
    prefetchResultRef.current = null;
    console.log("[handleContinueToNextRound] Acknowledging result before generation...");
    setCurrentEvent(null);
    setStoryText("");
    generatingRef.current = false;

    // Cancel ongoing prefetch
    if (prefetchingRef.current) {
      prefetchAbortRef.current?.abort();
      prefetchingRef.current = false;
    }

    setPhase("loading");
    void startGenerationAfterSync();
  }, [setRoundSummary, prefetchResultRef, setStoryText, setOptions, setCurrentEvent, setPhase, generatingRef, prefetchingRef, prefetchAbortRef, startGenerationAfterSync]);

  // Regenerate - now uses SSE streaming
  const performDailyReplacement = useCallback(async () => {
    console.log("[handleRegenerate] Starting SSE regeneration...");

    // Show loading toast
    setRegenerateToast({ type: "loading", message: "正在重新生成..." });
    setRegenerationFailure(null);
    replacementBufferRef.current = "";

    const previousStory = useGameStore.getState().storyText;
    const previousEvent = useGameStore.getState().currentEvent;
    const cursorStorageKey = `story101:regenerate-cursor:${gameId}`;
    const activeStorageKey = `story101:regenerate-active:${gameId}`;
    const resumeRequested = window.sessionStorage.getItem(activeStorageKey) === "1";
    if (regenerateLastEventIdRef.current === null) {
      const stored = window.sessionStorage.getItem(cursorStorageKey);
      const parsed = stored === null ? Number.NaN : Number.parseInt(stored, 10);
      regenerateLastEventIdRef.current = Number.isFinite(parsed) ? parsed : null;
    }

    const clearRegenerationCursor = () => {
      regenerateLastEventIdRef.current = null;
      window.sessionStorage.removeItem(cursorStorageKey);
      window.sessionStorage.removeItem(activeStorageKey);
    };
    const markReplacementFailed = (summary: string) => {
      updateDailyGenerationCommand((current) => ({
        ...current,
        status: "failed",
        mode: "replace_current",
        failure: {
          message: summary,
          summary,
          retryable: true,
        },
      }));
    };
    window.sessionStorage.setItem(activeStorageKey, "1");

    // Cancel ongoing prefetch
    if (prefetchingRef.current) {
      prefetchAbortRef.current?.abort();
      prefetchingRef.current = false;
    }
    prefetchResultRef.current = null;
    setIsPrefetching(false);

    // Cancel any previous regeneration
    regenerateAbortRef.current?.abort();
    regenerateAbortRef.current = new AbortController();

    generatingRef.current = true;
    setPhase("generating");
    setProcessing(true, "regenerating");

    // ★ 定义重试逻辑
    const attemptRegenerate = async (isRetry: boolean = false) => {
      return new Promise<void>((resolve, reject) => {
        streamRegenerate(
          gameId!,
          {
            onStory: (text) => {
              replacementBufferRef.current += text;
            },
            onEventId: (eventId) => {
              regenerateLastEventIdRef.current = eventId;
              window.sessionStorage.setItem(cursorStorageKey, String(eventId));
            },
            onStatus: (status) => {
              const progressPhase = status.phase === "retry"
                && typeof status.attempt === "number"
                && typeof status.max_attempts === "number"
                ? `retry:${status.attempt}/${status.max_attempts}`
                : status.phase;
              setProcessing(true, progressPhase);
              updateDailyGenerationCommand((current) => ({
                ...current,
                status: "running",
                mode: status.resolved_mode === "generate_missing"
                  ? "generate_missing"
                  : "replace_current",
                operationId: status.operation_id || current.operationId,
                attempt: typeof status.attempt === "number" ? status.attempt : current.attempt,
                maxAttempts: typeof status.max_attempts === "number"
                  ? status.max_attempts
                  : current.maxAttempts,
                failure: null,
              }));
              // ★ 当后端因一致性校验失败触发 retry 时，清空已累积的故事文本
              // 否则旧故事和新故事会被拼接在一起
              if (status.phase === 'retry') {
                console.log('[handleRegenerate] Retry detected, clearing accumulated story text');
                replacementBufferRef.current = "";
              }
            },
            onComplete: (data) => {
              setProcessing(false);
              generatingRef.current = false;

              const eventData = data as {
                event_id?: string;
                revision?: number;
                story_date?: string;
                event_description?: string;
                story?: string;
                options?: EventOption[];
                delivery_notice?: StoryDeliveryNotice;
              };

              const receivedOptions = eventData.options || [];
              if (receivedOptions.length > 0) {
                // ★ CRITICAL: 重新生成时，优先使用后端返回的完整故事
                // 因为重新生成会创建全新的故事内容，不应该与前端累积的流式文本比较
                const backendStory = eventData.event_description || eventData.story || "";
                const frontendStory = replacementBufferRef.current;
                
                // 如果后端返回了清洗后的完整故事，直接覆盖前端流式累积文本；否则回退到前端累积文本
                const finalStory = backendStory.trim() ? backendStory : frontendStory;
                
                console.log(`[handleRegenerate] Using story: backend=${backendStory.length} chars, frontend=${frontendStory.length} chars, final=${finalStory.length} chars`);

                if (!finalStory.trim()) {
                  console.error("[handleRegenerate] Complete event contained options but no story text");
                  setPhase("error");
                  setRegenerateToast({ type: "error", message: "生成失败，请重试" });
                  markReplacementFailed("生成失败，请重试");
                  clearRegenerationCursor();
                  reject(new Error("No story text in complete event"));
                  return;
                }

                setStoryText(finalStory);
                setOptions(receivedOptions);
                setCurrentEvent({
                  story: finalStory,
                  options: receivedOptions,
                  ...(eventData.event_id ? { event_id: eventData.event_id } : {}),
                  ...(typeof eventData.revision === "number" ? { revision: eventData.revision } : {}),
                  ...(eventData.story_date ? { story_date: eventData.story_date } : {}),
                  ...(eventData.delivery_notice ? { delivery_notice: eventData.delivery_notice } : {}),
                });
                setPhase("options");
                setRoundSummary(null);
                setRegenerationFailure(null);
                updateDailyGenerationCommand((current) => ({
                  ...current,
                  status: "succeeded",
                  mode: "replace_current",
                  failure: null,
                }));
                clearRegenerationCursor();
                // 后端只会在原子替换成功后删除旧配图；此时再刷新前端图片状态。
                useSceneImageStore.getState().clearCurrentRoundImages();
                console.log("[handleRegenerate] Regeneration complete!");
                
                // Show success toast (auto-hide after 2s)
                setRegenerateToast({ type: "success", message: "已生成新故事" });
                setTimeout(() => setRegenerateToast(null), 2000);
                resolve();
              } else {
                console.error("[handleRegenerate] No options in complete event");
                setRegenerateToast({ type: "error", message: "生成失败，请重试" });
                markReplacementFailed("生成失败，请重试");
                clearRegenerationCursor();
                reject(new Error("No options in complete event"));
              }
            },
            onError: async (err) => {
              // ★ 确保错误对象有 message 属性
              const errorMsg = err?.message || "重新生成失败，请重试";
              console.error("[handleRegenerate] SSE error:", err, "message:", errorMsg);
              
              // ★ 如果是 404 错误且不是重试，尝试恢复 session
              if (errorMsg.includes("404") && errorMsg.includes("No active game session") && !isRetry) {
                console.log("[handleRegenerate] Session not found, attempting to restore...");
                setRegenerateToast({ type: "loading", message: "恢复会话中..." });
                
                try {
                  // 尝试恢复 session
                  await syncPlayerState();
                  clearRegenerationCursor();
                  console.log("[handleRegenerate] Session restored, retrying regeneration...");
                  
                  // 递归重试
                  await attemptRegenerate(true);
                  resolve();
                } catch (restoreErr) {
                  console.error("[handleRegenerate] Failed to restore session:", restoreErr);
                  setProcessing(false);
                  generatingRef.current = false;
                  setPhase("error");
                  setRegenerateToast({ type: "error", message: "会话恢复失败，请刷新页面" });
                  markReplacementFailed("会话恢复失败，请刷新页面");
                  reject(restoreErr);
                }
                return;
              }

              const recoverableTransport = err instanceof Error && (
                errorMsg.includes("Stream ended")
                || errorMsg.toLowerCase().includes("network")
                || errorMsg.toLowerCase().includes("failed to fetch")
                || errorMsg.toLowerCase().includes("terminated")
              );
              if (recoverableTransport && !isRetry) {
                await attemptRegenerate(true);
                resolve();
                return;
              }
              
              setProcessing(false);
              generatingRef.current = false;

              const structuredFailure = !(err instanceof Error) && err.code
                ? err as GenerationFailurePayload
                : null;
              if (structuredFailure) {
                setRegenerationFailure(structuredFailure);
              }
              const commandFailure: GenerationFailurePayload = structuredFailure || {
                message: errorMsg,
                summary: errorMsg,
                retryable: true,
              };
              updateDailyGenerationCommand((current) => ({
                ...current,
                status: "failed",
                mode: "replace_current",
                operationId: commandFailure.operation_id || current.operationId,
                failure: commandFailure,
              }));
              clearRegenerationCursor();

              // 后端事务失败时旧故事仍然有效。先从服务端同步；若同步失败，
              // 仍用操作开始前的本地快照恢复阅读，避免玩家面对空白页。
              try {
                await useGameStore.getState().syncState({ gameId: gameId! });
              } catch (syncErr) {
                console.warn("[handleRegenerate] Failed to refresh preserved story:", syncErr);
              }
              const refreshed = useGameStore.getState();
              const restoredEvent = refreshed.currentEvent || previousEvent;
              const restoredStory = restoredEvent?.story || refreshed.storyText || previousStory;
              const restoredOptions = restoredEvent?.options || previousEvent?.options || [];
              if (restoredStory && restoredOptions.length > 0) {
                setStoryText(restoredStory);
                setOptions(restoredOptions);
                setCurrentEvent({
                  ...(restoredEvent || {}),
                  story: restoredStory,
                  options: restoredOptions,
                });
                setPhase("options");
              } else {
                setPhase("error");
              }
              
              // 显示简化的错误消息
              const displayMsg = structuredFailure?.summary || (errorMsg.includes("404")
                ? "会话已过期，请刷新页面" 
                : errorMsg.length > 50 
                  ? "重新生成失败，请重试"
                  : errorMsg);
              setRegenerateToast({ type: "error", message: displayMsg });
              reject(new Error(errorMsg));
            },
          },
          {
            signal: regenerateAbortRef.current?.signal,
            ...(regenerateLastEventIdRef.current === null
              ? ((isRetry || resumeRequested) ? { lastEventId: -1 } : {})
              : { lastEventId: regenerateLastEventIdRef.current }),
          }
        ).catch((err) => {
          if (err?.name !== "AbortError") {
            console.error("[handleRegenerate] Failed:", err);
            setProcessing(false);
            generatingRef.current = false;
            setPhase("error");
            setRegenerateToast({ type: "error", message: "重新生成失败" });
            markReplacementFailed("重新生成失败");
            reject(err);
          }
        });
      });
    };

    // 执行重新生成
    try {
      await attemptRegenerate();
    } catch {
      // 错误已在 attemptRegenerate 中处理
    }
  }, [gameId, prefetchingRef, prefetchAbortRef, prefetchResultRef, setIsPrefetching, setStoryText, setOptions, setCurrentEvent, setPhase, setProcessing, generatingRef, setRoundSummary, syncPlayerState, updateDailyGenerationCommand]);

  const handleDailyStoryAction = useCallback((): Promise<void> => {
    if (activeDailyGenerationFlightRef.current) {
      return activeDailyGenerationFlightRef.current;
    }

    const currentEvent = useGameStore.getState().currentEvent;
    const mode: DailyGenerationMode = isCompleteClientEvent(currentEvent)
      ? "replace_current"
      : "generate_missing";
    updateDailyGenerationCommand({
      ...INITIAL_DAILY_GENERATION_COMMAND,
      status: "starting",
      mode,
    });

    const operation = mode === "replace_current"
      ? performDailyReplacement()
      : (async () => {
          setRegenerationFailure(null);
          setPhase("loading");
          await generateEventRef.current({ userInitiated: true });
        })();
    const trackedOperation = operation.finally(() => {
      if (activeDailyGenerationFlightRef.current === trackedOperation) {
        activeDailyGenerationFlightRef.current = null;
      }
    });
    activeDailyGenerationFlightRef.current = trackedOperation;
    return trackedOperation;
  }, [
    activeDailyGenerationFlightRef,
    generateEventRef,
    performDailyReplacement,
    setPhase,
    updateDailyGenerationCommand,
  ]);

  const handleRegenerate = handleDailyStoryAction;

  // Fetch ending when game ends
  // Note: ending fetch is handled by the main hook based on phase

  return {
    // State
    isSaving,
    saveToast,
    regenerateToast,
    regenerationFailure,
    dailyGenerationCommand: setDailyGenerationCommand
      ? undefined
      : localDailyGenerationCommand,
    summaryText,
    roundSummary,
    endingData,
    // Setters
    setSummaryText,
    setRoundSummary,
    setRegenerateToast,
    setRegenerationFailure,
    // Handlers
    handleSave,
    handleContinueAfterSummary,
    handleContinueToNextRound,
    handleRegenerate,
    handleDailyStoryAction,
  };
}
