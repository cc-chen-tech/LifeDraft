"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useGameStore } from "@/stores/useGameStore";
import { useEventStore } from "@/stores/useEventStore";
import { useSessionStore } from "@/stores/useSessionStore";
import { useHydration } from "@/hooks/useHydration";
import { games } from "@/lib/api";
import type { CurrentEventData, EventOption } from "@/lib/types";
import {
  resolveRecoveredGenerationFailure,
  resolveRecoveredStoryText,
  resolveRecoveredView,
} from "@/lib/sessionRecovery";

// Import sub-hooks
import { usePhaseManager, Phase, ConnectionStatus } from "./game/usePhaseManager";
import { useEventGenerator } from "./game/useEventGenerator";
import { useChoiceHandler } from "./game/useChoiceHandler";
import { useGameState } from "./game/useGameState";
import { useHistoryViewer } from "./game/useHistoryViewer";
import { isAbortError } from "./game/gameplayRun";
import type { NarrativeLoadingOperation } from "@/components/narrative-loading/NarrativeLoadingState";
import {
  INITIAL_DAILY_GENERATION_COMMAND,
  type DailyGenerationCommandState,
} from "./game/dailyGenerationCommand";

// Re-export types for backwards compatibility
export type { Phase, ConnectionStatus };

function isNotFoundError(err: unknown): boolean {
  const error = err as { status?: number; message?: string } | null;
  const message = String(error?.message || "");
  return error?.status === 404 || message.includes("404") || message.toLowerCase().includes("not found");
}

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
    syncPlayerState,
    // ★ 场景插画
    roundSceneImages,
    currentRoundSceneImage,
    eventSceneImage,  // ★ 事件插画
    resultSceneImage,  // ★ 结果插画
    isLoadingRoundSceneImage,
    roundSceneError,
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
  const [loadingOperation, setLoadingOperation] = useState<NarrativeLoadingOperation>("event");
  const [loadingIdentity, setLoadingIdentity] = useState(0);
  const [dailyGenerationCommand, setDailyGenerationCommand] =
    useState<DailyGenerationCommandState>(INITIAL_DAILY_GENERATION_COMMAND);

  // Story container ref for scrolling
  const storyContainerRef = useRef<HTMLDivElement>(null);
  
  // Refs defined once and passed to sub-hooks
  const abortRef = useRef<AbortController | null>(null);
  const runTokenRef = useRef(0);
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
  const generateEventRef = useRef<(
    options?: { resume?: boolean; userInitiated?: boolean }
  ) => Promise<void>>(async () => {});
  const dailyGenerationFlightRef = useRef<Promise<void> | null>(null);

  // ===== Phase Manager =====
  const {
    phase,
    setPhase,
    phaseRef,
    connectionStatus,
    setConnectionStatus,
    reconnectAttempt,
    setReconnectAttempt,
    transport,
    setTransport,
    setProcessing,
  } = usePhaseManager();

  // ===== Game State (called early to get setters) =====
  const {
    isSaving,
    saveToast,
    regenerateToast,
    regenerationFailure,
    summaryText,
    roundSummary,
    endingData,
    setSummaryText,
    setRoundSummary,
    setRegenerationFailure,
    handleSave,
    handleContinueAfterSummary,
    handleContinueToNextRound,
    handleRegenerate,
    handleDailyStoryAction,
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
    dailyGenerationFlightRef,
    setDailyGenerationCommand,
  });

  useEffect(() => {
    if (phase !== "options" && phase !== "generating" && phase !== "error") {
      setRegenerationFailure(null);
    }
  }, [phase, setRegenerationFailure]);

  useEffect(() => {
    const persistedFailure = resolveRecoveredGenerationFailure(playerState);
    if (persistedFailure) setRegenerationFailure(persistedFailure);
  }, [playerState, setRegenerationFailure]);

  // ===== Event Generator =====
  const {
    generateEvent,
    recoverEventGeneration,
  } = useEventGenerator({
    gameId,
    phaseRef,
    setPhase,
    setConnectionStatus,
    setReconnectAttempt,
    setTransport,
    setLoadingOperation,
    setLoadingIdentity,
    setProcessing,
    setOptions,
    setStoryText,
    appendStoryText,
    setCurrentEvent,
    setGameOver,
    setRoundSummary,
    setRegenerationFailure,
    setIsPrefetching,
    runTokenRef,
    abortRef,
    generatingRef,
    isRetryingRef,
    setDailyGenerationCommand,
    pollingRef,
    prefetchAbortRef,
    prefetchResultRef,
    prefetchingRef,
  });
  
  // Keep the late-bound callback current without mutating refs during render.
  useEffect(() => {
    generateEventRef.current = generateEvent;
  }, [generateEvent]);

  useEffect(() => {
    const generateNextDay = () => {
      generatingRef.current = false;
      phaseRef.current = "loading";
      void generateEvent();
    };
    window.addEventListener("story2:generate-next-day", generateNextDay);
    return () => window.removeEventListener("story2:generate-next-day", generateNextDay);
  }, [generateEvent, phaseRef]);

  // ===== Choice Handler =====
  const {
    handleChoice,
    handleCustomChoice,
    recoverChoiceGeneration,
  } = useChoiceHandler({
    gameId,
    runTokenRef,
    abortRef,
    generatingRef,
    setPhase,
    setConnectionStatus,
    setReconnectAttempt,
    setTransport,
    setLoadingOperation,
    setLoadingIdentity,
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
  const activeRecoveryEpochRef = useRef(0);

  useEffect(() => {
    if (!hydrated) return;

    const recoveryEpoch = activeRecoveryEpochRef.current + 1;
    activeRecoveryEpochRef.current = recoveryEpoch;
    const recoveryController = new AbortController();
    const recoveryStartGameId = gameId;
    const isCurrentRecovery = () =>
      !recoveryController.signal.aborted &&
      activeRecoveryEpochRef.current === recoveryEpoch &&
      useGameStore.getState().gameId === recoveryStartGameId;

    const attemptRecovery = async () => {
      if (!gameId) {
        if (redirectCheckedRef.current) {
          console.warn("[play] No gameId after a checked session, skipping active recovery");
          return;
        }
        console.warn("[play] No gameId in localStorage, attempting server-side recovery...");

        try {
          const state = await games.getActive(recoveryController.signal);
          if (!isCurrentRecovery()) return;
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
                  ...(typeof rawEvent.event_id === "string" ? { event_id: rawEvent.event_id } : {}),
                  ...(typeof rawEvent.revision === "number" ? { revision: rawEvent.revision } : {}),
                  ...(typeof rawEvent.story_date === "string" ? { story_date: rawEvent.story_date } : {}),
                  ...(rawEvent.delivery_notice && typeof rawEvent.delivery_notice === "object"
                    ? { delivery_notice: rawEvent.delivery_notice as NonNullable<CurrentEventData["delivery_notice"]> }
                    : {}),
                }
              : null;

            let recoveredStoryText = event?.story || "";
            if (!recoveredStoryText) {
              recoveredStoryText = resolveRecoveredStoryText({
                eventStory: event?.story,
                playerState: state.player_state,
                progress: state.progress,
                roundInfo: state.round_info,
              });
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
          if (isAbortError(err) || !isCurrentRecovery()) return;
          const error = err as { status?: number };
          if (error.status === 404) {
            console.log("[play] No active game on server, redirecting to home");
          } else {
            console.error("[play] Failed to recover session:", err);
          }
        }

        if (isCurrentRecovery()) router.replace("/");
      } else {
        console.log("[play] gameId exists:", gameId);
        redirectCheckedRef.current = true;
      }
    };

    void attemptRecovery();
    return () => {
      recoveryController.abort();
      if (activeRecoveryEpochRef.current === recoveryEpoch) {
        activeRecoveryEpochRef.current += 1;
      }
    };
  }, [hydrated, gameId, router]);

  // ===== Initial Load =====
  const lastInitializedGameIdRef = useRef<number | null>(null);
  const initializationEpochRef = useRef(0);

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

    lastInitializedGameIdRef.current = gameId;
    const initializationEpoch = initializationEpochRef.current + 1;
    initializationEpochRef.current = initializationEpoch;
    const initialRunToken = runTokenRef.current;
    const initializedGameId = gameId;
    abortRef.current?.abort();
    const initializationController = new AbortController();
    abortRef.current = initializationController;
    const isCurrentInitialization = () =>
      !initializationController.signal.aborted &&
      abortRef.current === initializationController &&
      initializationEpochRef.current === initializationEpoch &&
      runTokenRef.current === initialRunToken &&
      useGameStore.getState().gameId === initializedGameId;

    const doInit = async () => {
      try {
        await useGameStore.getState().syncState({
          gameId: initializedGameId,
          signal: initializationController.signal,
        });
        if (!isCurrentInitialization()) return;
        const state = useGameStore.getState();
        const recoveredView = resolveRecoveredView({
          eventStory: state.currentEvent?.story,
          eventOptions: state.currentEvent?.options,
          playerState: state.playerState,
          progress: state.progress,
          roundInfo: state.roundInfo,
        });

        if (recoveredView.phase === "options" && state.currentEvent?.options?.length) {
          // 有选项，直接展示
          setOptions(state.currentEvent.options);
          if (!state.storyText && state.currentEvent.story) {
            setStoryText(state.currentEvent.story);
          }
          setPhase("options");
        } else if (
          recoveredView.phase === "result" ||
          recoveredView.phase === "summary" ||
          recoveredView.phase === "ending"
        ) {
          setStoryText(recoveredView.story);
          setRoundSummary(recoveredView.roundSummary || null);
          setSummaryText(recoveredView.summaryText);
          setOptions([]);
          setPhase(recoveredView.phase);
        } else if (recoveredView.phase === "generating") {
          if (recoveredView.story) {
            setStoryText(recoveredView.story);
          }
          phaseRef.current = "generating";
          setPhase("generating");
          if (!isCurrentInitialization()) return;
          await generateEvent({ resume: true });
        } else if (recoveredView.phase === "failed") {
          if (recoveredView.story) {
            setStoryText(recoveredView.story);
          }
          setOptions([]);
          setProcessing(false);
          setTransport("failed");
          setPhase("error");
        } else {
          if (!isCurrentInitialization()) return;
          await generateEvent();
        }
      } catch (err) {
        if (isAbortError(err) || initializationController.signal.aborted) return;
        if (!isCurrentInitialization()) return;
        if (isNotFoundError(err)) {
          console.warn("[play] Stored game no longer exists, clearing session; retry recovery remains available");
          useGameStore.getState().resetGame();
          setProcessing(false);
          setTransport("failed");
          setPhase("error");
          return;
        }
        console.error("[play] syncState failed:", err);
        if (!isCurrentInitialization()) return;
        await generateEvent();
      }
    };

    void doInit();
    return () => {
      if (abortRef.current === initializationController) {
        initializationController.abort();
        abortRef.current = null;
      }
      if (initializationEpochRef.current === initializationEpoch) {
        initializationEpochRef.current += 1;
      }
    };
  }, [
    hydrated,
    gameId,
    generateEvent,
    setStoryText,
    setPhase,
    phaseRef,
    runTokenRef,
    setProcessing,
    setRoundSummary,
    setSummaryText,
    setTransport,
  ]);

  // ===== Round Scene Images =====
  const currentRound = (roundInfo?.current_round as number) ?? 0;
  
  // 当轮次变化时，获取当前轮次的场景插画
  // ★ 根据 phase 决定获取哪个 stage 的插画
  useEffect(() => {
    const canFetchScene = phase === 'options' || phase === 'result' || phase === 'summary';
    const hasRenderableStory = Boolean(storyText || currentEvent?.story);
    if (gameId && currentRound >= 0 && canFetchScene && hasRenderableStory) {
      const stage = phase === 'options' ? 'event' : 'result';
      const sceneRound = phase === 'result' || phase === 'summary' ? Math.max(0, currentRound - 1) : currentRound;
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
    endingData,
    isPrefetching,
  };

  const ui = {
    showHistory,
    isViewingHistory,
    saveToast,
    regenerateToast,
    regenerationFailure,
    dailyGenerationCommand,
    isSaving,
    connectionStatus,
    reconnectAttempt,
    transport,
    loadingOperation,
    loadingIdentity,
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
    handleDailyStoryAction,
    generateEvent,
    recoverEventGeneration,
    recoverChoiceGeneration,
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
    roundSceneError,
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

  const utils = { hydrated, router };

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
    regenerationFailure,
    dailyGenerationCommand,
    endingData,
    connectionStatus,
    reconnectAttempt,
    transport,
    loadingOperation,
    loadingIdentity,
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
    handleDailyStoryAction,
    generateEvent,
    recoverEventGeneration,
    recoverChoiceGeneration,

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
    roundSceneError,
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
    hydrated,
    router,
  };
}

// Export grouped return type for consumers who want to use grouped API
export type UsePlayGameReturn = ReturnType<typeof usePlayGame>;
