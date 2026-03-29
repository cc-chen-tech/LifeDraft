"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useGameStore } from "@/stores/useGameStore";
import { useSceneImageStore } from "@/stores/useSceneImageStore";
import { streamRegenerate } from "@/lib/sse";
import type { EventOption } from "@/lib/types";
import type { Phase } from "./usePhaseManager";

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
  setCurrentEvent: (event: { story: string; options: EventOption[] } | null) => void;
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
  generateEventRef: React.MutableRefObject<() => Promise<void>>;
  syncPlayerState: () => Promise<unknown>;
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
}: UseGameStateParams) {
  // Save state
  const [isSaving, setIsSaving] = useState(false);
  const [saveToast, setSaveToast] = useState<"success" | "error" | null>(null);

  // Regenerate toast state
  const [regenerateToast, setRegenerateToast] = useState<ToastState | null>(null);

  // Summary state
  const [summaryText, setSummaryText] = useState("");
  const [roundSummary, setRoundSummary] = useState<string | null>(null);

  // Adjuster state
  const [showAdjuster, setShowAdjuster] = useState(false);

  // Ending data
  const [endingData, setEndingData] = useState<Record<string, unknown> | null>(null);

  // Regenerate abort controller
  const regenerateAbortRef = useRef<AbortController | null>(null);

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
      syncPlayerState().then(() => generateEventRef.current());
    }
  }, [isGameOver, setPhase, setCurrentEvent, setStoryText, generatingRef, syncPlayerState, generateEventRef]);

  // Continue to next round
  const handleContinueToNextRound = useCallback(() => {
    console.log(`[handleContinueToNextRound] User clicked continue button`);
    setRoundSummary(null);

    // Check for prefetched result
    const prefetchResult = prefetchResultRef.current;
    if (prefetchResult?.event?.options?.length) {
      console.log("[handleContinueToNextRound] Using prefetched result!");
      prefetchResultRef.current = null;

      setStoryText(prefetchResult.story);
      setOptions(prefetchResult.options);
      setCurrentEvent({
        story: prefetchResult.story,
        options: prefetchResult.options,
      });
      setPhase("options");
      return;
    }

    // No prefetch result, generate normally
    console.log("[handleContinueToNextRound] No prefetch result, generating normally...");
    setCurrentEvent(null);
    setStoryText("");
    generatingRef.current = false;

    // Cancel ongoing prefetch
    if (prefetchingRef.current) {
      prefetchAbortRef.current?.abort();
      prefetchingRef.current = false;
    }

    setPhase("loading");
    syncPlayerState().then(() => generateEventRef.current());
  }, [setRoundSummary, prefetchResultRef, setStoryText, setOptions, setCurrentEvent, setPhase, generatingRef, prefetchingRef, prefetchAbortRef, syncPlayerState, generateEventRef]);

  // Handle story adjust
  const handleAdjustStory = useCallback(() => {
    setShowAdjuster(true);
  }, []);

  // Regenerate - now uses SSE streaming
  const handleRegenerate = useCallback(async () => {
    console.log("[handleRegenerate] Starting SSE regeneration...");

    // Show loading toast
    setRegenerateToast({ type: "loading", message: "正在重新生成..." });

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

    // Clear current state
    setStoryText("");
    setOptions([]);
    setCurrentEvent(null);
    generatingRef.current = true;
    setPhase("generating");
    setProcessing(true, "regenerating");

    // ★ 清除当前轮次的场景图片状态，确保重新生成后显示新图片
    useSceneImageStore.getState().clearCurrentRoundImages();
    console.log("[handleRegenerate] Cleared current round scene images");

    // ★ 定义重试逻辑
    const attemptRegenerate = async (isRetry: boolean = false) => {
      return new Promise<void>((resolve, reject) => {
        streamRegenerate(
          gameId!,
          {
            onStory: (text) => {
              appendStoryText(text);
            },
            onStatus: (status) => {
              setProcessing(true, status.phase);
              // ★ 当后端因一致性校验失败触发 retry 时，清空已累积的故事文本
              // 否则旧故事和新故事会被拼接在一起
              if (status.phase === 'retry') {
                console.log('[handleRegenerate] Retry detected, clearing accumulated story text');
                setStoryText('');
              }
            },
            onComplete: (data) => {
              setProcessing(false);
              generatingRef.current = false;

              const eventData = data as {
                event_description?: string;
                story?: string;
                options?: EventOption[];
              };

              const receivedOptions = eventData.options || [];
              if (receivedOptions.length > 0) {
                const backendStory = eventData.event_description || eventData.story || "";
                const frontendStory = useGameStore.getState().storyText;
                const finalStory = backendStory.length > frontendStory.length ? backendStory : frontendStory;

                setStoryText(finalStory);
                setOptions(receivedOptions);
                setCurrentEvent({
                  story: finalStory,
                  options: receivedOptions,
                });
                setPhase("options");
                setRoundSummary(null);
                console.log("[handleRegenerate] Regeneration complete!");
                
                // Show success toast (auto-hide after 2s)
                setRegenerateToast({ type: "success", message: "已生成新故事" });
                setTimeout(() => setRegenerateToast(null), 2000);
                resolve();
              } else {
                console.error("[handleRegenerate] No options in complete event");
                setRegenerateToast({ type: "error", message: "生成失败，请重试" });
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
                  reject(restoreErr);
                }
                return;
              }
              
              setProcessing(false);
              generatingRef.current = false;
              setPhase("error");
              
              // 显示简化的错误消息
              const displayMsg = errorMsg.includes("404") 
                ? "会话已过期，请刷新页面" 
                : errorMsg.length > 50 
                  ? "重新生成失败，请重试"
                  : errorMsg;
              setRegenerateToast({ type: "error", message: displayMsg });
              reject(new Error(errorMsg));
            },
          },
          { signal: regenerateAbortRef.current?.signal }
        ).catch((err) => {
          if (err?.name !== "AbortError") {
            console.error("[handleRegenerate] Failed:", err);
            setProcessing(false);
            generatingRef.current = false;
            setPhase("error");
            setRegenerateToast({ type: "error", message: "重新生成失败" });
            reject(err);
          }
        });
      });
    };

    // 执行重新生成
    try {
      await attemptRegenerate();
    } catch (err) {
      // 错误已在 attemptRegenerate 中处理
    }
  }, [gameId, prefetchingRef, prefetchAbortRef, prefetchResultRef, setIsPrefetching, setStoryText, appendStoryText, setOptions, setCurrentEvent, setPhase, setProcessing, generatingRef, setRoundSummary, syncPlayerState]);

  // Fetch ending when game ends
  // Note: ending fetch is handled by the main hook based on phase

  return {
    // State
    isSaving,
    saveToast,
    regenerateToast,
    summaryText,
    roundSummary,
    showAdjuster,
    endingData,
    // Setters
    setSummaryText,
    setRoundSummary,
    setShowAdjuster,
    setRegenerateToast,
    // Handlers
    handleSave,
    handleContinueAfterSummary,
    handleContinueToNextRound,
    handleAdjustStory,
    handleRegenerate,
  };
}
