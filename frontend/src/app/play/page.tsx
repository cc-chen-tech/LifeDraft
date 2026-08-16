"use client";

import { useState, useEffect, Suspense, useCallback, useMemo, useRef } from "react";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetTitle,
} from "@/components/ui/sheet";
import { PlayPhaseContent } from "@/components/game/PlayPhaseContent";
import { PlayReadingFrame } from "@/components/game/PlayReadingFrame";
import { NarrativeLoadingState, getNarrativeLoadingDelay } from "@/components/narrative-loading/NarrativeLoadingState";
import {
  ChatBar,
  type ChatBarAction,
  type ChatBarCommand,
} from "@/components/game/ChatBar";
import { RoundHistoryDrawer } from "@/components/game/RoundHistoryDrawer";
import { RoundSceneImageDisplay } from "@/components/game/RoundSceneImage";
import { HistorySceneImage } from "@/components/game/HistorySceneImage";
import { CollectionPanel } from "@/components/game/CollectionPanel";
import { StoryListeningExperience } from "@/components/game/StoryListeningExperience";
import { DailyTransitionLayer } from "@/components/game/DailyTransitionLayer";
import { getSceneImageDisplayMode } from "@/components/game/sceneImageStagePolicy";
import {
  FeedbackNotice,
} from "@/components/story101";

import { usePlayGame } from "@/hooks/usePlayGame";
import { useDelayedLoading } from "@/hooks/useDelayedLoading";
import { useGameIdFromUrl } from "@/hooks/useGameIdFromUrl";
import { useDailyTransition } from "@/hooks/game/useDailyTransition";
import { useGameStore } from "@/stores/useGameStore";
import { useEventStore } from "@/stores/useEventStore";
import { useSceneImageStore } from "@/stores/useSceneImageStore";
import { useUIStore } from "@/stores/useUIStore";
import { api } from "@/lib/api";
import type { EventOption } from "@/lib/types";
import { isWithinInputLimit } from "@/lib/inputLimits";
import { INPUT_LIMITS } from "@/types/input-limits.generated";
import {
  Loader2,
  Home,
  CheckCircle2,
  XCircle,
  X,
} from "lucide-react";

/**
 * GameIdSync - 内部组件，使用 useGameIdFromUrl 同步 URL 参数
 * 必须包裹在 Suspense 中
 */
function GameIdSync() {
  useGameIdFromUrl();
  return null;
}

type PageFeedbackState = {
  key: string;
  type: "success" | "error";
  message: string;
};

/**
 * PlayPage - Main game play page component.
 *
 * Uses usePlayGame hook for all business logic.
 * This component only handles UI rendering.
 */
export default function PlayPage() {
  // ★ 收集面板状态
  const [showCollection, setShowCollection] = useState(false);
  const [activeSidePanel, setActiveSidePanel] = useState<"collection" | "history" | null>(null);

  // ★ 故事风格状态
  const [narrativeStyleId, setNarrativeStyleId] = useState<string>("");
  const [narrativeStyleOptions, setNarrativeStyleOptions] = useState<Array<{ style_id: string; style_name: string; description: string }>>([]);
  const [styleLoading, setStyleLoading] = useState(false);
  const [assistantCommand, setAssistantCommand] = useState<ChatBarCommand | null>(null);
  const [assistantSurfaceOpen, setAssistantSurfaceOpen] = useState(false);
  const [toolsSurfaceOpen, setToolsSurfaceOpen] = useState(false);
  const [queuedPageFeedback, setQueuedPageFeedback] = useState<PageFeedbackState | null>(null);
  const lastObservedFeedbackKeyRef = useRef<string | null>(null);
  const collectionReturnFocusRef = useRef<HTMLElement | null>(null);
  const historyReturnFocusRef = useRef<HTMLElement | null>(null);

  const {
    // State
    phase,
    options,
    summaryText,
    roundSummary,
    isSaving,
    saveToast,
    regenerateToast,
    regenerationFailure,
    transport: gameplayTransport,
    loadingOperation: gameplayOperation,
    loadingIdentity,
    isPrefetching,  // ★ 预生成状态

    // Store values
    gameId,
    playerState,
    progress,
    roundInfo,
    storyText,

    // Refs
    storyContainerRef,

    // Actions
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
    recoverEventGeneration,
    recoverChoiceGeneration,

    // Utilities
    hydrated,
    router,
    
    // ★ 历史回顾
    showHistory,
    setShowHistory,
    roundHistory,
    historyRoundIndex,
    isViewingHistory,
    displayText,  // ★ 实际显示的文本（历史模式下显示历史，否则显示当前）
    historyDisplayText,  // ★ 历史显示文本
    currentHistoryRound,  // ★ 当前查看的历史轮次
    handleOpenHistory,
    handleSelectHistoryRound,
    handleBackToCurrent,
    handleGenerateHistoryImage,  // ★ 生成历史图片
    handleRegenerateHistoryImage,  // ★ 重新生成历史图片
    
    // ★ 场景插画
    currentRoundSceneImage,
    eventSceneImage,  // ★ 事件插画
    resultSceneImage,  // ★ 结果插画
    isLoadingRoundSceneImage,
    roundSceneError,
    isRegeneratingRoundScene,
    fetchRoundSceneImage,
    regenerateRoundSceneImage,
    // ★ 历史场景插画
    historySceneImage,
    isLoadingHistoryImage,
    isGeneratingHistoryImage,
    isRegeneratingHistoryImage,
    currentRound,
  } = usePlayGame();

  const processingMessage = useUIStore((state) => state.processingMessage);
  const resultSceneRound = Math.max(0, currentRound - 1);
  const isDailyTimeline = playerState?.timeline?.version === 2;
  const dailyTransition = useDailyTransition({
    isDailyTimeline,
    phase,
    storyText,
    playerState,
  });
  const isCurrentStoryBusy = phase === "loading" || phase === "generating" || phase === "choosing";
  const isUnifiedGameplayFailure =
    phase === "error" && gameplayTransport === "failed";
  const hasInlineStoryError =
    phase === "error" && !isUnifiedGameplayFailure;
  const shouldRenderGameplayLoading =
    isCurrentStoryBusy || isUnifiedGameplayFailure;
  const hasCompetingSurfaceOpen =
    assistantSurfaceOpen ||
    toolsSurfaceOpen ||
    showCollection ||
    showHistory;
  const sceneImageDisplayMode = getSceneImageDisplayMode({
    phase,
    hasEventSceneImage: Boolean(eventSceneImage),
    hasResultSceneImage: Boolean(resultSceneImage),
    hasCurrentRoundSceneImage: Boolean(currentRoundSceneImage),
    isLoadingRoundSceneImage,
  });
  const storyRewriteOverLimit = !isWithinInputLimit(
    storyText,
    INPUT_LIMITS.fullStory,
  );
  const storyRewriteDisabled = !storyText.trim() || storyRewriteOverLimit;
  const storyRewriteDisabledReason = !storyText.trim()
    ? "暂无可改写的故事"
    : storyRewriteOverLimit
      ? `当前故事超过 ${INPUT_LIMITS.fullStory} 字，无法提交改写`
      : undefined;
  const terminalRegenerateToast =
    regenerateToast &&
    (regenerateToast.type === "success" || regenerateToast.type === "error")
      ? regenerateToast
      : null;
  const rawTerminalFeedbackType: PageFeedbackState["type"] | null =
    terminalRegenerateToast?.type === "success"
      ? "success"
      : terminalRegenerateToast?.type === "error"
        ? "error"
        : saveToast;
  const rawTerminalFeedbackMessage = terminalRegenerateToast
    ? terminalRegenerateToast.message
    : saveToast === "success"
      ? "已保存"
      : saveToast === "error"
        ? "保存失败"
        : null;
  const rawTerminalFeedbackKey = rawTerminalFeedbackType && rawTerminalFeedbackMessage
    ? `${rawTerminalFeedbackType}:${rawTerminalFeedbackMessage}`
    : "";

  useEffect(() => {
    if (!rawTerminalFeedbackKey || !rawTerminalFeedbackType || !rawTerminalFeedbackMessage) {
      lastObservedFeedbackKeyRef.current = null;
      return;
    }
    if (lastObservedFeedbackKeyRef.current === rawTerminalFeedbackKey) return;

    lastObservedFeedbackKeyRef.current = rawTerminalFeedbackKey;
    setQueuedPageFeedback({
      key: rawTerminalFeedbackKey,
      type: rawTerminalFeedbackType,
      message: rawTerminalFeedbackMessage,
    });
  }, [
    rawTerminalFeedbackKey,
    rawTerminalFeedbackMessage,
    rawTerminalFeedbackType,
  ]);

  const pageFeedbackBlocked =
    shouldRenderGameplayLoading || hasCompetingSurfaceOpen || Boolean(dailyTransition.active);
  const loadingPageFeedback = regenerateToast?.type === "loading"
    ? {
        key: `loading:${regenerateToast.message}`,
        type: "loading" as const,
        message: regenerateToast.message,
      }
    : null;
  const pageFeedback = pageFeedbackBlocked
    ? null
    : loadingPageFeedback ?? queuedPageFeedback;
  const pageFeedbackType = pageFeedback?.type ?? null;
  const pageFeedbackMessage = pageFeedback?.message ?? null;
  const announceSceneImageError = Boolean(
    roundSceneError &&
      !pageFeedback &&
      !hasInlineStoryError &&
      !hasCompetingSurfaceOpen &&
      !shouldRenderGameplayLoading,
  );

  useEffect(() => {
    if (!pageFeedback || pageFeedback.type === "loading") return;

    const timeout = window.setTimeout(() => {
      setQueuedPageFeedback((current) =>
        current?.key === pageFeedback.key ? null : current,
      );
    }, pageFeedback.type === "error" ? 3000 : 2000);
    return () => window.clearTimeout(timeout);
  }, [pageFeedback]);

  // ★ 游戏设置
  const constraintLevel = useGameStore((state) => state.constraintLevel);
  const setConstraintLevel = useGameStore((state) => state.setConstraintLevel);
  const enableSceneImage = useGameStore((state) => state.enableSceneImage);
  const setEnableSceneImage = useGameStore((state) => state.setEnableSceneImage);
  const isGameplayDelayed = useDelayedLoading({
    isLoading: isCurrentStoryBusy,
    delay: getNarrativeLoadingDelay("gameplay", constraintLevel),
    loadingIdentity,
  });
  const isHydrationLoadingVisible = useDelayedLoading({
    isLoading: !hydrated,
    delay: getNarrativeLoadingDelay("hydrate"),
    loadingIdentity: "play-hydration",
  });

  // ★ 加载故事风格
  const loadNarrativeStyles = useCallback(async () => {
    if (!gameId || narrativeStyleOptions.length > 0) return;
    setStyleLoading(true);
    try {
      const gid = Number(gameId);
      const [options, current] = await Promise.all([
        api.games.listNarrativeStyles(gid),
        api.games.getNarrativeStyle(gid),
      ]);
      setNarrativeStyleOptions(options);
      setNarrativeStyleId(current.style_id);
    } catch (err) {
      console.error("[loadNarrativeStyles]", err);
    } finally {
      setStyleLoading(false);
    }
  }, [gameId, narrativeStyleOptions.length]);

  const handleStyleChange = useCallback(async (styleId: string) => {
    if (!gameId) return;
    setNarrativeStyleId(styleId);
    try {
      await api.games.updateNarrativeStyle(Number(gameId), styleId);
    } catch (err) {
      console.error("[handleStyleChange]", err);
    }
  }, [gameId]);

  const handleRecoverGeneration = useCallback(() => {
    void recoverEventGeneration();
  }, [recoverEventGeneration]);

  const handleRetryGeneration = useCallback(() => {
    void generateEvent();
  }, [generateEvent]);

  const handleRecoverChoice = useCallback(() => {
    void recoverChoiceGeneration();
  }, [recoverChoiceGeneration]);

  const handleGameplayLoadingAction =
    gameplayOperation === "choice"
      ? handleRecoverChoice
      : gameplayTransport === "failed"
        ? handleRetryGeneration
        : handleRecoverGeneration;

  useEffect(() => {
    if (hydrated && gameId && phase === "ending") {
      router.push("/ending");
    }
  }, [gameId, hydrated, phase, router]);

  const requestAssistantAction = useCallback((action: ChatBarAction) => {
    setAssistantCommand((current) => ({
      id: (current?.id ?? 0) + 1,
      action,
    }));
  }, []);

  const closeAssistantAndSound = useCallback(() => {
    requestAssistantAction("close");
  }, [requestAssistantAction]);

  const rememberPanelOpener = useCallback(
    (targetRef: { current: HTMLElement | null }) => {
      const activeElement = document.activeElement;
      if (activeElement instanceof HTMLElement && activeElement !== document.body) {
        targetRef.current = activeElement;
      }
    },
    [],
  );

  const restorePanelOpener = useCallback(
    (targetRef: { current: HTMLElement | null }) => {
      const target = targetRef.current;
      targetRef.current = null;
      target?.focus();
    },
    [],
  );

  const handleOpenCollection = useCallback(() => {
    rememberPanelOpener(collectionReturnFocusRef);
    closeAssistantAndSound();
    setActiveSidePanel("collection");
    setShowCollection(true);
    setShowHistory(false);
    if (isViewingHistory) {
      handleBackToCurrent();
    }
  }, [closeAssistantAndSound, handleBackToCurrent, isViewingHistory, rememberPanelOpener, setShowHistory]);

  const handleOpenHistoryPanel = useCallback(() => {
    rememberPanelOpener(historyReturnFocusRef);
    closeAssistantAndSound();
    setActiveSidePanel("history");
    setShowCollection(false);
    handleOpenHistory();
  }, [closeAssistantAndSound, handleOpenHistory, rememberPanelOpener]);

  const handleCollectionOpenChange = useCallback((open: boolean) => {
    if (open) {
      rememberPanelOpener(collectionReturnFocusRef);
      closeAssistantAndSound();
      setActiveSidePanel("collection");
      setShowCollection(true);
      setShowHistory(false);
      return;
    }

    setShowCollection(false);
    setActiveSidePanel((current) => (current === "collection" ? null : current));
  }, [closeAssistantAndSound, rememberPanelOpener, setShowHistory]);

  const handleHistoryOpenChange = useCallback((open: boolean) => {
    if (open) {
      rememberPanelOpener(historyReturnFocusRef);
      closeAssistantAndSound();
      setActiveSidePanel("history");
      setShowCollection(false);
      setShowHistory(true);
      return;
    }

    setShowHistory(false);
    setActiveSidePanel((current) => (current === "history" ? null : current));
  }, [closeAssistantAndSound, rememberPanelOpener, setShowHistory]);

  const collectionPanelOpen =
    showCollection && (!showHistory || activeSidePanel === "collection");
  const historyPanelOpen =
    showHistory && (!showCollection || activeSidePanel === "history");

  const handleRewriteComplete = useCallback((newStory: string, replacement?: {
    event_id?: string;
    revision?: number;
    story_date?: string;
    options?: EventOption[];
  }) => {
    useSceneImageStore.getState().clearCurrentRoundImages();
    setStoryText(newStory);
    const currentEvent = useGameStore.getState().currentEvent;
    if (currentEvent) {
      // EventStore preserves its existing storyText when setting an event, so
      // update both stores before synchronizing the compatibility facade.
      useEventStore.setState({ storyText: newStory });
      const replacementEvent = {
        ...currentEvent,
        ...replacement,
        story: newStory,
        options: replacement?.options || currentEvent.options,
      };
      useEventStore.setState({ currentEvent: replacementEvent });
      useGameStore.setState((state) => ({
        ...state,
        currentEvent: replacementEvent,
        storyText: newStory,
      }));
      if (replacement?.options?.length) setOptions(replacement.options);
    } else {
      const fallbackEvent = {
        story: newStory,
        options: replacement?.options || options,
        ...replacement,
      };
      useEventStore.setState({ currentEvent: fallbackEvent, storyText: newStory });
      useGameStore.setState({ currentEvent: fallbackEvent, storyText: newStory });
    }
  }, [options, setOptions, setStoryText]);

  const handleOpenAssistantSurface = useCallback((action: ChatBarAction) => {
    setShowCollection(false);
    setActiveSidePanel(null);
    if (showHistory) setShowHistory(false);
    requestAssistantAction(action);
  }, [requestAssistantAction, setShowHistory, showHistory]);

  // P2-性能优化（前端 Step 1）：为 memo 化的 PlayReadingFrame 提供稳定回调引用，
  // 流式期间不再因内联箭头函数导致工具栏每 chunk 重渲染。
  const handleOpenChat = useCallback(
    () => handleOpenAssistantSurface("chat"),
    [handleOpenAssistantSurface],
  );
  const handleOpenRewrite = useCallback(
    () => handleOpenAssistantSurface("rewrite"),
    [handleOpenAssistantSurface],
  );
  const handleOpenSummary = useCallback(
    () => handleOpenAssistantSurface("summary"),
    [handleOpenAssistantSurface],
  );

  const handleOpenTools = useCallback(() => {
    closeAssistantAndSound();
    setShowCollection(false);
    setActiveSidePanel(null);
    if (showHistory) setShowHistory(false);
  }, [closeAssistantAndSound, setShowHistory, showHistory]);

  const handleCoordinatedSave = useCallback(() => {
    closeAssistantAndSound();
    handleSave();
  }, [closeAssistantAndSound, handleSave]);

  const handleCoordinatedRegenerate = useCallback(() => {
    closeAssistantAndSound();
    handleRegenerate();
  }, [closeAssistantAndSound, handleRegenerate]);

  const handleHome = useCallback(() => {
    closeAssistantAndSound();
    router.push("/");
  }, [closeAssistantAndSound, router]);

  // Keep the memoized reading frame stable while the story stream updates.
  const toolsProps = useMemo(
    () => ({
      isSaving,
      isStoryBusy: shouldRenderGameplayLoading || Boolean(dailyTransition.active),
      isViewingHistory,
      constraintLevel,
      narrativeStyleId,
      narrativeStyles: narrativeStyleOptions,
      narrativeStylesLoading: styleLoading,
      rewriteDisabled: storyRewriteDisabled,
      rewriteDisabledReason: storyRewriteDisabledReason,
      enableSceneImage,
      onSave: handleCoordinatedSave,
      onOpenHistory: handleOpenHistoryPanel,
      onOpenCollection: handleOpenCollection,
      onOpenChat: handleOpenChat,
      onOpenRewrite: handleOpenRewrite,
      onOpenSummary: handleOpenSummary,
      onRegenerate: handleCoordinatedRegenerate,
      onHome: handleHome,
      onConstraintLevelChange: setConstraintLevel,
      onNarrativeStyleChange: handleStyleChange,
      onSceneImageChange: setEnableSceneImage,
      onRequestNarrativeStyles: loadNarrativeStyles,
      onOpenTools: handleOpenTools,
      onToolsOpenChange: setToolsSurfaceOpen,
      isDailyTimeline,
    }),
    [
      isSaving,
      shouldRenderGameplayLoading,
      dailyTransition.active,
      isViewingHistory,
      constraintLevel,
      narrativeStyleId,
      narrativeStyleOptions,
      styleLoading,
      storyRewriteDisabled,
      storyRewriteDisabledReason,
      enableSceneImage,
      handleCoordinatedSave,
      handleOpenHistoryPanel,
      handleOpenCollection,
      handleOpenChat,
      handleOpenRewrite,
      handleOpenSummary,
      handleCoordinatedRegenerate,
      handleHome,
      setConstraintLevel,
      handleStyleChange,
      setEnableSceneImage,
      loadNarrativeStyles,
      handleOpenTools,
      setToolsSurfaceOpen,
      isDailyTimeline,
    ],
  );

  // Don't render until hydrated
  if (!hydrated) {
    return (
      <div
        className="min-h-screen bg-[#0D0C0B]"
        data-testid="play-hydration-shell"
        aria-busy="true"
      >
        {isHydrationLoadingVisible && (
          <NarrativeLoadingState context="hydrate" layout="screen" />
        )}
      </div>
    );
  }

  // Show loading if no gameId
  if (!gameId) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background px-4">
        <div className="w-full max-w-sm space-y-5 text-center">
          <Loader2 className="mx-auto h-8 w-8 animate-spin text-primary" />
          <div className="space-y-2">
            <h1 className="text-lg font-semibold text-foreground">正在恢复当前进度</h1>
            <p className="text-sm text-muted-foreground">
              如果没有可恢复的游戏，页面会返回首页。你也可以手动返回。
            </p>
          </div>
          <div className="flex items-center justify-center gap-3">
            <Button
              variant="narrative"
              size="touch"
              onClick={() => router.replace("/")}
            >
              <Home className="mr-2 h-4 w-4" />
              返回首页
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (phase === "ending") {
    return (
      <NarrativeLoadingState
        context="ending"
        layout="screen"
        phase="loading_context"
      />
    );
  }

  const sceneMedia = isViewingHistory ? (
    currentHistoryRound ? (
      <HistorySceneImage
        sceneImage={historySceneImage}
        isLoading={isLoadingHistoryImage}
        isGenerating={isGeneratingHistoryImage}
        isRegenerating={isRegeneratingHistoryImage}
        week={currentHistoryRound.week}
        round={currentHistoryRound.round}
        storyText={historyDisplayText || ""}
        onGenerate={handleGenerateHistoryImage}
        onRegenerate={handleRegenerateHistoryImage}
      />
    ) : null
  ) : storyText ? (
    <>
      {sceneImageDisplayMode === "event" && eventSceneImage && (
        <RoundSceneImageDisplay
          sceneImage={eventSceneImage}
          isLoading={isLoadingRoundSceneImage && phase === "options"}
          error={roundSceneError}
          announceError={announceSceneImageError}
          isRegenerating={isRegeneratingRoundScene}
          currentRound={currentRound}
          label="事件场景"
          onRefresh={() => fetchRoundSceneImage(currentRound, "event")}
          onRetryGeneration={() =>
            fetchRoundSceneImage(currentRound, "event", { retry: true })
          }
          onRegenerate={regenerateRoundSceneImage}
        />
      )}

      {sceneImageDisplayMode === "result" && resultSceneImage && (
        <RoundSceneImageDisplay
          sceneImage={resultSceneImage}
          isLoading={isLoadingRoundSceneImage}
          error={roundSceneError}
          announceError={announceSceneImageError}
          isRegenerating={isRegeneratingRoundScene}
          currentRound={resultSceneRound}
          label="结果场景"
          onRefresh={() => fetchRoundSceneImage(resultSceneRound, "result")}
          onRetryGeneration={() =>
            fetchRoundSceneImage(resultSceneRound, "result", { retry: true })
          }
          onRegenerate={regenerateRoundSceneImage}
        />
      )}

      {sceneImageDisplayMode === "result-loading" && (
        <RoundSceneImageDisplay
          sceneImage={null}
          isLoading={isLoadingRoundSceneImage}
          error={roundSceneError}
          announceError={announceSceneImageError}
          isRegenerating={isRegeneratingRoundScene}
          currentRound={resultSceneRound}
          label="结果场景"
          onRefresh={() => fetchRoundSceneImage(resultSceneRound, "result")}
          onRetryGeneration={() =>
            fetchRoundSceneImage(resultSceneRound, "result", { retry: true })
          }
          onRegenerate={regenerateRoundSceneImage}
        />
      )}

      {sceneImageDisplayMode === "event-fallback" && eventSceneImage && (
        <RoundSceneImageDisplay
          sceneImage={eventSceneImage}
          isLoading={isLoadingRoundSceneImage}
          error={roundSceneError}
          announceError={announceSceneImageError}
          isRegenerating={isRegeneratingRoundScene}
          currentRound={resultSceneRound}
          label="事件场景"
          onRefresh={() => fetchRoundSceneImage(resultSceneRound, "event")}
          onRetryGeneration={() =>
            fetchRoundSceneImage(resultSceneRound, "event", { retry: true })
          }
          onRegenerate={regenerateRoundSceneImage}
        />
      )}

      {sceneImageDisplayMode === "current" && currentRoundSceneImage && (
        <RoundSceneImageDisplay
          sceneImage={currentRoundSceneImage}
          isLoading={isLoadingRoundSceneImage}
          error={roundSceneError}
          announceError={announceSceneImageError}
          isRegenerating={isRegeneratingRoundScene}
          currentRound={currentRound}
          onRefresh={() =>
            fetchRoundSceneImage(
              currentRound,
              phase === "options"
                ? "event"
                : phase === "result" || phase === "summary"
                  ? "result"
                  : undefined,
            )
          }
          onRetryGeneration={() =>
            fetchRoundSceneImage(
              currentRound,
              phase === "options"
                ? "event"
                : phase === "result" || phase === "summary"
                  ? "result"
                  : undefined,
              { retry: true },
            )
          }
          onRegenerate={regenerateRoundSceneImage}
        />
      )}

      {sceneImageDisplayMode === "none" &&
        (roundSceneError || isLoadingRoundSceneImage) && (
          <RoundSceneImageDisplay
            sceneImage={null}
            isLoading={isLoadingRoundSceneImage}
            error={roundSceneError}
            announceError={announceSceneImageError}
            isRegenerating={isRegeneratingRoundScene}
            currentRound={
              phase === "options" ? currentRound : resultSceneRound
            }
            label={phase === "options" ? "事件场景" : "结果场景"}
            onRefresh={() =>
              fetchRoundSceneImage(
                phase === "options" ? currentRound : resultSceneRound,
                phase === "options" ? "event" : "result",
              )
            }
            onRetryGeneration={() =>
              fetchRoundSceneImage(
                phase === "options" ? currentRound : resultSceneRound,
                phase === "options" ? "event" : "result",
                { retry: true },
              )
            }
            onRegenerate={regenerateRoundSceneImage}
          />
        )}
    </>
  ) : null;

  return (
    <>
      {/* ★ URL 参数同步 - 必须在 Suspense 中 */}
      <Suspense fallback={null}>
        <GameIdSync />
      </Suspense>
      <PlayReadingFrame
        contentRef={storyContainerRef}
        playerState={playerState}
        progress={progress}
        isViewingHistory={isViewingHistory}
        hideProgress={Boolean(dailyTransition.active)}
        toolsProps={toolsProps}
      >
        {regenerationFailure && !isViewingHistory && (
          <section
            role="alert"
            className="mb-6 rounded-2xl border border-amber-300/50 bg-amber-50/80 p-4 text-sm text-amber-950 shadow-sm dark:border-amber-700/50 dark:bg-amber-950/30 dark:text-amber-100"
          >
            <div className="flex items-start gap-2">
              <XCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
              <div className="min-w-0 flex-1">
                <p className="font-medium">
                  {regenerationFailure.summary || regenerationFailure.message}
                </p>
                <p className="mt-1 text-xs opacity-80">
                  失败稿没有保存，也没有改动人物关系；你仍可阅读旧故事。
                </p>
                <details className="mt-3">
                  <summary className="cursor-pointer select-none text-xs font-medium">
                    查看失败详情
                  </summary>
                  <div className="mt-2 space-y-1 text-xs opacity-85">
                    {regenerationFailure.detail && <p>{regenerationFailure.detail}</p>}
                    <p>
                      {regenerationFailure.code || "RETRY_EXHAUSTED"}
                      {typeof regenerationFailure.attempts_used === "number"
                        ? ` · 已尝试 ${regenerationFailure.attempts_used} 次`
                        : ""}
                      {regenerationFailure.quality_level
                        ? ` · ${regenerationFailure.quality_level}`
                        : ""}
                    </p>
                  </div>
                </details>
                {regenerationFailure.retryable !== false && (
                  <Button
                    type="button"
                    variant="quiet"
                    size="sm"
                    className="mt-3"
                    onClick={handleCoordinatedRegenerate}
                  >
                    再次生成
                  </Button>
                )}
              </div>
            </div>
          </section>
        )}
        {dailyTransition.active && !isViewingHistory ? (
          <DailyTransitionLayer
            transitionText={dailyTransition.active.transitionText}
            nextDate={dailyTransition.active.nextDate}
            failed={dailyTransition.active.failed}
            onRetry={handleRetryGeneration}
          />
        ) : (
        <>
        {isDailyTimeline && !isViewingHistory && phase === "options" && displayText.trim() && Number.isFinite(Number(gameId)) ? (
          <StoryListeningExperience
            key={`${playerState?.timeline?.current_date}-${playerState?.timeline?.day_index}`}
            context={{
              source_type: "current_story",
              game_id: Number(gameId),
              week: progress?.week ?? null,
              round_number: currentRound ?? null,
              stage: "event",
              attempt_id: `${playerState?.timeline?.current_date}-${playerState?.timeline?.day_index}`,
              day_index: playerState?.timeline?.day_index ?? 0,
              story_date: playerState?.timeline?.current_date ?? null,
              text_hash: "pending-client-hash",
              text: displayText,
            }}
            storyText={displayText}
            options={options}
            onSelectChoice={handleChoice}
            media={sceneMedia}
          />
        ) : (
        <PlayPhaseContent
          phase={phase}
          isViewingHistory={isViewingHistory}
          displayText={displayText}
          historyPosition={
            currentHistoryRound
              ? {
                  week: currentHistoryRound.week,
                  round: currentHistoryRound.round,
                }
              : null
          }
          onBackToCurrent={handleBackToCurrent}
          loading={{
            visible: shouldRenderGameplayLoading,
            phase: processingMessage,
            operation: gameplayOperation,
            delayed: isGameplayDelayed,
            transport: gameplayTransport,
            onAction: handleGameplayLoadingAction,
          }}
          media={sceneMedia}
          roundSummary={roundSummary}
          options={options}
          onSelectChoice={handleChoice}
          onCustomChoice={isDailyTimeline ? undefined : handleCustomChoice}
          isDailyTimeline={isDailyTimeline}
          result={{
            currentRound: (roundInfo?.current_round as number) || 0,
            roundsPerWeek: (roundInfo?.rounds_per_week as number) || 3,
            isPrefetching,
            onContinue: handleContinueToNextRound,
          }}
          weeklySummary={{
            text: summaryText,
            onContinue: handleContinueAfterSummary,
          }}
          inlineError={{
            visible:
              hasInlineStoryError &&
              !pageFeedbackType &&
              !hasCompetingSurfaceOpen,
            onRetry: handleRetryGeneration,
          }}
        />
        )}
        </>
        )}

      </PlayReadingFrame>

      {/* Chat bar */}
      {!dailyTransition.active && <ChatBar
        gameId={gameId}
        onSave={handleCoordinatedSave}
        onRegenerate={handleCoordinatedRegenerate}
        storyText={storyText}
        onRewriteComplete={handleRewriteComplete}
        isSaving={isSaving}
        isStoryBusy={
          shouldRenderGameplayLoading || collectionPanelOpen || historyPanelOpen
        }
        isViewingHistory={isViewingHistory}
        showLauncher={false}
        command={assistantCommand}
        onSurfaceOpenChange={setAssistantSurfaceOpen}
        isDailyTimeline={isDailyTimeline}
        className="play-chat-surface"
      />}

      {/* ★ 历史回顾抽屉 */}
      <RoundHistoryDrawer
        open={historyPanelOpen}
        onOpenChange={handleHistoryOpenChange}
        onCloseAutoFocus={(event) => {
          event.preventDefault();
          restorePanelOpener(historyReturnFocusRef);
        }}
        roundHistory={roundHistory}
        selectedIndex={historyRoundIndex}
        onSelect={handleSelectHistoryRound}
        onBackToCurrent={() => {
          handleBackToCurrent();
          handleHistoryOpenChange(false);
        }}
        isViewingHistory={isViewingHistory}
      />

      {/* ★ 收集面板 */}
      <Sheet modal open={collectionPanelOpen} onOpenChange={handleCollectionOpenChange}>
        <SheetContent
          side="right"
          showCloseButton={false}
          onCloseAutoFocus={(event) => {
            event.preventDefault();
            restorePanelOpener(collectionReturnFocusRef);
          }}
          className="z-[70] w-full max-w-[min(100vw,34rem)] p-0 sm:w-[34rem]"
          overlayClassName="bg-transparent"
        >
          <SheetTitle className="sr-only">收集</SheetTitle>
          <SheetClose asChild>
            <Button
              type="button"
              variant="quiet"
              size="icon-touch"
              className="absolute right-3 top-3 z-10"
              aria-label="关闭收集"
            >
              <X className="h-4 w-4" />
            </Button>
          </SheetClose>
          <CollectionPanel gameId={gameId || 0} />
        </SheetContent>
      </Sheet>

      {/* A single page-level feedback owner prevents fixed notices from overlapping. */}
      {pageFeedbackType && pageFeedbackMessage && (
        <div className="play-feedback fixed left-1/2 z-[80] w-[min(28rem,calc(100vw-2rem))] -translate-x-1/2">
          <FeedbackNotice
            tone={
              pageFeedbackType === "success"
                ? "success"
                : pageFeedbackType === "loading"
                  ? "info"
                  : "danger"
            }
          >
            <span className="flex items-center gap-2">
              {pageFeedbackType === "success" ? (
                <><CheckCircle2 className="h-4 w-4" /> {pageFeedbackMessage}</>
              ) : pageFeedbackType === "loading" ? (
                <><Loader2 className="h-4 w-4 animate-spin" /> {pageFeedbackMessage}</>
              ) : (
                <><XCircle className="h-4 w-4" /> {pageFeedbackMessage}</>
              )}
            </span>
          </FeedbackNotice>
        </div>
      )}
    </>
  );
}
