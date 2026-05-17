"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useGameStore } from "@/stores/useGameStore";
import { useEventStore } from "@/stores/useEventStore";
import { useSessionStore } from "@/stores/useSessionStore";
import { useHydration } from "@/hooks/useHydration";
import { games } from "@/lib/api";
import type { EventOption } from "@/lib/types";

// Import sub-hooks
import { usePhaseManager, Phase, ConnectionStatus } from "./game/usePhaseManager";
import { useEventGenerator } from "./game/useEventGenerator";
import { useChoiceHandler } from "./game/useChoiceHandler";
import { useGameState } from "./game/useGameState";
import { useHistoryViewer } from "./game/useHistoryViewer";

// Re-export types for backwards compatibility
export type { Phase, ConnectionStatus };
export { STATUS_MESSAGES } from "./game/usePhaseManager";

/**
 * Custom hook that manages all game logic for the play page.
 * Composes multiple sub-hooks for better maintainability.
 * External API remains unchanged for backwards compatibility.
 */
export function usePlayGame() {
  const router = useRouter();
  const {
    gameId,
    playerState,
    progress,
    roundInfo,
    storyText,
    currentEvent,
    isGameOver,
    appendStoryText,
    setStoryText,
    setCurrentEvent,
    setGameOver,
    syncState,
    syncPlayerState,
    saveGame,
    // ★ 场景插画
    roundSceneImages,
    currentRoundSceneImage,
    eventSceneImage,  // ★ 事件插画
    resultSceneImage,  // ★ 结果插画
    isLoadingRoundSceneImage,
    isRegeneratingRoundScene,
    roundSceneRegenerateError,
    fetchRoundSceneImage,
    fetchAllRoundSceneImages,
    regenerateRoundSceneImage,
    setEventSceneImage,  // ★ 设置事件插画
    setResultSceneImage,  // ★ 设置结果插画
    // ★ 历史场景插画
    historySceneImage,
    isLoadingHistoryImage,
    isGeneratingHistoryImage,
    isRegeneratingHistoryImage,
    fetchHistorySceneImage,
    generateHistorySceneImage,
    regenerateHistorySceneImage,
    setHistorySceneImage,
  } = useGameStore();

  const hydrated = useHydration();

  // Options state (local, not in sub-hooks)
  const [options, setOptions] = useState<EventOption[]>([]);
  const [isPrefetching, setIsPrefetching] = useState(false);

  // Story container ref for scrolling
  const storyContainerRef = useRef<HTMLDivElement>(null);
  
  // Refs defined once and passed to sub-hooks
  const abortRef = useRef<AbortController | null>(null);
  const generatingRef = useRef(false);
  const isRetryingRef = useRef(false);
  const pollingRef = useRef(false);
  const prefetchAbortRef = useRef<AbortController | null>(null);
  const prefetchResultRef = useRef<{
    story: string;
    options: EventOption[];
    event: { story: string; options: EventOption[] } | null;
  } | null>(null);
  const prefetchingRef = useRef(false);
  const generateEventRef = useRef<() => Promise<void>>(async () => {});

  // ===== Phase Manager =====
  const {
    phase,
    setPhase,
    phaseRef,
    connectionStatus,
    setConnectionStatus,
    reconnectAttempt,
    setReconnectAttempt,
    elapsedSeconds,
    getLoadingMessage,
    setProcessing,
  } = usePhaseManager();

  // ===== Game State (called early to get setters) =====
  const {
    isSaving,
    saveToast,
    regenerateToast,
    summaryText,
    roundSummary,
    endingData,
    setSummaryText,
    setRoundSummary,
    handleSave,
    handleContinueAfterSummary,
    handleContinueToNextRound,
    handleRegenerate,
  } = useGameState({
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
  });

  // ===== Event Generator =====
  const {
    generateEvent,
    prefetchNextEvent,
  } = useEventGenerator({
    gameId,
    phaseRef,
    setPhase,
    setConnectionStatus,
    setReconnectAttempt,
    setProcessing,
    setOptions,
    setStoryText,
    appendStoryText,
    setCurrentEvent,
    setGameOver,
    setRoundSummary,
    isGameOver,
    setIsPrefetching,
    abortRef,
    generatingRef,
    isRetryingRef,
    pollingRef,
    prefetchAbortRef,
    prefetchResultRef,
    prefetchingRef,
  });
  
  // Update generateEventRef for useGameState
  generateEventRef.current = generateEvent;

  // ===== Choice Handler =====
  const { handleChoice, handleCustomChoice } = useChoiceHandler({
    gameId,
    abortRef,
    generatingRef,
    setPhase,
    setConnectionStatus,
    setReconnectAttempt,
    setProcessing,
    appendStoryText,
    setCurrentEvent,
    setGameOver,
    setSummaryText,
    setRoundSummary,
    setOptions,
    setStoryText,
  });

  // ===== History Viewer =====
  const {
    showHistory,
    setShowHistory,
    roundHistory,
    historyRoundIndex,
    isViewingHistory,
    historyDisplayText,
    displayText,  // ★ 实际显示的文本（历史模式下显示历史，否则显示当前）
    // ★ 历史场景图片
    currentHistoryRound,
    handleOpenHistory,
    handleSelectHistoryRound,
    handleBackToCurrent,
    handleGenerateHistoryImage,
    handleRegenerateHistoryImage,
  } = useHistoryViewer({
    playerState,
    storyText,
    currentEvent,
    phaseRef,
    setPhase,
    setOptions,
    generatingRef,
    gameId,
    fetchHistorySceneImage,
    generateHistorySceneImage,
    regenerateHistorySceneImage,
    setHistorySceneImage,
  });

  // ===== Session Recovery (remains in main hook) =====
  const redirectCheckedRef = useRef(false);

  useEffect(() => {
    if (!hydrated) return;

    const attemptRecovery = async () => {
      if (!gameId) {
        console.warn("[play] No gameId in localStorage, attempting server-side recovery...");

        try {
          const state = await games.getActive();
          if (state && state.game_id) {
            console.log("[play] ✅ Recovered active game from server:", state.game_id);

            const rawEvent = state.current_event as Record<string, unknown> | null;
            const event = rawEvent
              ? {
                  story:
                    (rawEvent.event_description as string) ||
                    (rawEvent.story_text as string) ||
                    (rawEvent.story as string) ||
                    "",
                  options: ((rawEvent.options as EventOption[]) || []),
                }
              : null;

            let recoveredStoryText = event?.story || "";
            if (!recoveredStoryText) {
              const playerState = state.player_state as Record<string, unknown>;
              const lastRoundStory = playerState?.last_round_full_story as string;
              if (lastRoundStory) {
                recoveredStoryText = lastRoundStory;
                console.log(`[play] Restored story from last_round_full_story (${lastRoundStory.length} chars)`);
              } else {
                const roundHistory = playerState?.round_history as Array<{event_description?: string; story_continuation?: string}>;
                if (roundHistory && roundHistory.length > 0) {
                  const lastRound = roundHistory[roundHistory.length - 1];
                  const eventDesc = lastRound?.event_description || "";
                  const continuation = lastRound?.story_continuation || "";
                  recoveredStoryText = eventDesc + (continuation ? "\n\n" + continuation : "");
                  console.log(`[play] Restored story from round_history (${recoveredStoryText.length} chars)`);
                }
              }
            }

            useSessionStore.setState({
              gameId: state.game_id,
              playerState: state.player_state,
              progress: state.progress,
              roundInfo: state.round_info,
              constraintLevel: ((state as { constraint_level?: string }).constraint_level || "expert") as "fast" | "expert" | "master",
            });
            useEventStore.setState({
              currentEvent: event
                ? {
                    ...event,
                    story: event.story || recoveredStoryText,
                  }
                : null,
              storyText: recoveredStoryText,
            });

            console.log("[play] State restored, will continue game");
            return;
          }
        } catch (err) {
          const error = err as { status?: number };
          if (error.status === 404) {
            console.log("[play] No active game on server, redirecting to home");
          } else {
            console.error("[play] Failed to recover session:", err);
          }
        }

        router.replace("/");
      } else {
        console.log("[play] gameId exists:", gameId);
        redirectCheckedRef.current = true;
      }
    };

    attemptRecovery();
  }, [hydrated, gameId, router]);

  // ===== Initial Load =====
  const initialLoadDoneRef = useRef(false);
  const lastInitializedGameIdRef = useRef<number | null>(null);

  useEffect(() => {
    if (!hydrated) return;

    if (gameId === lastInitializedGameIdRef.current) {
      return;
    }

    if (!gameId) {
      console.warn("[play] No gameId, cannot initialize");
      return;
    }

    const currentPhase = phaseRef.current;
    if (currentPhase !== "loading" && currentPhase !== "error") {
      return;
    }

    initialLoadDoneRef.current = true;
    lastInitializedGameIdRef.current = gameId;

    const doInit = async () => {
      try {
        await useGameStore.getState().syncState();
        const state = useGameStore.getState();
        if (state.currentEvent?.options?.length) {
          // 有选项，直接展示
          setOptions(state.currentEvent.options);
          if (!state.storyText && state.currentEvent.story) {
            setStoryText(state.currentEvent.story);
          }
          setPhase("options");
        } else if (state.storyText) {
          // ★ 有故事但无选项（存档加载常见情况）：展示已有故事，然后调用 generateEvent 生成选项
          // generateEvent 内部已有保护：如果 storyText 非空则保留内容不清空
          // phase 保持在 "loading"，直接调用 generateEvent 即可
          console.log(`[play] Has story (${state.storyText.length} chars) but no options, generating options via SSE...`);
          generateEvent();
        } else {
          // 真正没有故事，生成新事件
          generateEvent();
        }
      } catch (err) {
        console.error("[play] syncState failed:", err);
        generateEvent();
      }
    };

    doInit();
  }, [hydrated, gameId, generateEvent, setStoryText, setPhase, phaseRef]);

  // ===== Fetch Ending =====
  const [localEndingData, setLocalEndingData] = useState<Record<string, unknown> | null>(null);
  
  useEffect(() => {
    if (phase === "ending" && gameId && !localEndingData) {
      import("@/lib/api").then(({ default: api }) =>
        api.gameplay.getEnding(gameId).then(setLocalEndingData).catch(console.error)
      );
    }
  }, [phase, gameId, localEndingData]);
  
  // Use local ending data if available, otherwise from useGameState
  const finalEndingData = localEndingData || endingData;

  // ===== Round Scene Images =====
  const currentRound = (roundInfo?.current_round as number) ?? 0;
  
  // 当轮次变化时，获取当前轮次的场景插画
  // ★ 根据 phase 决定获取哪个 stage 的插画
  useEffect(() => {
    const canFetchScene = phase === 'options' || phase === 'result';
    const hasRenderableStory = Boolean(storyText || currentEvent?.story);
    if (gameId && currentRound >= 0 && canFetchScene && hasRenderableStory) {
      const stage = phase === 'options' ? 'event' : 'result';
      const sceneRound = phase === 'result' ? Math.max(0, currentRound - 1) : currentRound;
      fetchRoundSceneImage(sceneRound, stage);
    }
  }, [gameId, currentRound, phase, storyText, currentEvent, fetchRoundSceneImage]);

  // 初始加载所有场景插画
  useEffect(() => {
    if (gameId) {
      fetchAllRoundSceneImages();
    }
  }, [gameId, fetchAllRoundSceneImages]);
  
  // ★ 场景插画自动生成已由后端 GET 端点处理
  // 当调用 fetchRoundSceneImage 时，如果图片不存在，后端会自动触发生成并返回 202
  // 前端只需轮询等待即可，无需主动触发生成

  // ===== Grouped Return Objects =====
  // M-04: Organized return values into logical groups
  const session = {
    gameId,
    playerState,
    progress,
    roundInfo,
    currentEvent,
    isGameOver,
    currentRound,
  };

  const events = {
    phase,
    storyText,
    options,
    displayText,
    summaryText,
    roundSummary,
    endingData: finalEndingData,
    isPrefetching,
  };

  const ui = {
    showHistory,
    isViewingHistory,
    saveToast,
    regenerateToast,
    isSaving,
    connectionStatus,
    reconnectAttempt,
    elapsedSeconds,
  };

  const actions = {
    // Phase & Options
    setPhase,
    setOptions,
    setStoryText,
    setShowHistory,
    // Game flow
    handleChoice,
    handleCustomChoice,
    handleContinueAfterSummary,
    handleContinueToNextRound,
    handleSave,
    handleRegenerate,
    generateEvent,
  };

  const history = {
    roundHistory,
    historyRoundIndex,
    historyDisplayText,
    currentHistoryRound,
    handleOpenHistory,
    handleSelectHistoryRound,
    handleBackToCurrent,
    handleGenerateHistoryImage,
    handleRegenerateHistoryImage,
  };

  const sceneImages = {
    roundSceneImages,
    currentRoundSceneImage,
    eventSceneImage,
    resultSceneImage,
    historySceneImage,
    isLoadingRoundSceneImage,
    isLoadingHistoryImage,
    isGeneratingHistoryImage,
    isRegeneratingRoundScene,
    isRegeneratingHistoryImage,
    roundSceneRegenerateError,
    fetchRoundSceneImage,
    fetchAllRoundSceneImages,
    regenerateRoundSceneImage,
    setEventSceneImage,
    setResultSceneImage,
  };

  const refs = {
    storyContainerRef,
  };

  const utils = {
    getLoadingMessage,
    hydrated,
    router,
  };

  // Return both grouped and flat APIs for flexibility
  // Flat API maintained for backwards compatibility
  return {
    // ===== Grouped API (M-04) =====
    session,
    events,
    ui,
    actions,
    history,
    sceneImages,
    refs,
    utils,

    // ===== Flat API (backwards compatibility) =====
    // State
    phase,
    options,
    summaryText,
    roundSummary,
    isSaving,
    saveToast,
    regenerateToast,
    endingData: finalEndingData,
    connectionStatus,
    reconnectAttempt,
    elapsedSeconds,
    isPrefetching,

    // Store values
    gameId,
    playerState,
    progress,
    roundInfo,
    storyText,
    currentEvent,
    isGameOver,

    // Refs
    storyContainerRef,

    // Actions
    setPhase,
    setOptions,
    setStoryText,

    // Handlers
    handleChoice,
    handleCustomChoice,
    handleContinueAfterSummary,
    handleContinueToNextRound,
    handleSave,
    handleRegenerate,
    generateEvent,

    // History
    showHistory,
    setShowHistory,
    roundHistory,
    historyRoundIndex,
    isViewingHistory,
    historyDisplayText,
    displayText,
    currentHistoryRound,
    handleOpenHistory,
    handleSelectHistoryRound,
    handleBackToCurrent,
    handleGenerateHistoryImage,
    handleRegenerateHistoryImage,

    // Scene images
    roundSceneImages,
    currentRoundSceneImage,
    eventSceneImage,
    resultSceneImage,
    isLoadingRoundSceneImage,
    isRegeneratingRoundScene,
    roundSceneRegenerateError,
    fetchRoundSceneImage,
    fetchAllRoundSceneImages,
    regenerateRoundSceneImage,
    setEventSceneImage,
    setResultSceneImage,
    historySceneImage,
    isLoadingHistoryImage,
    isGeneratingHistoryImage,
    isRegeneratingHistoryImage,
    currentRound,

    // Utilities
    getLoadingMessage,
    hydrated,
    router,
  };
}

// Export grouped return type for consumers who want to use grouped API
export type UsePlayGameReturn = ReturnType<typeof usePlayGame>;
