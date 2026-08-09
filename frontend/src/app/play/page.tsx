"use client";

import { useState, useEffect, Suspense, useCallback, useRef } from "react";
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
import {
  CLOSE_SOUND_PANEL_EVENT,
  OPEN_SOUND_PANEL_EVENT,
  SOUND_PANEL_STATE_EVENT,
} from "@/components/game/GlobalMusicPlayer";
import { CompletedStoryMediaGate } from "@/components/game/CompletedStoryMediaGate";
import { getSceneImageDisplayMode } from "@/components/game/sceneImageStagePolicy";
import {
  FeedbackNotice,
} from "@/components/story101";

import { usePlayGame } from "@/hooks/usePlayGame";
import { useDelayedLoading } from "@/hooks/useDelayedLoading";
import { useGameIdFromUrl } from "@/hooks/useGameIdFromUrl";
import { useGameStore } from "@/stores/useGameStore";
import { useMusicStore } from "@/stores/useMusicStore";
import { useUIStore } from "@/stores/useUIStore";
import { api } from "@/lib/api";
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
  const [soundSurfaceOpen, setSoundSurfaceOpen] = useState(false);
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
  const hasMusicSoundContext = useMusicStore((state) =>
    Boolean(
      state.activeStoryText ||
        state.recommendation ||
        state.currentSong ||
        state.queue.length > 0,
    ),
  );
  const hasCompletedReadingContext = Boolean(
    displayText.trim() &&
      Number.isFinite(Number(gameId)) &&
      (isViewingHistory ||
        phase === "options" ||
        phase === "result" ||
        phase === "summary"),
  );
  const soundAvailable = hasMusicSoundContext || hasCompletedReadingContext;

  const resultSceneRound = Math.max(0, currentRound - 1);
  const storyReadyForCompletedMedia =
    phase === "options" || phase === "result" || phase === "summary";
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
    soundSurfaceOpen ||
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
    shouldRenderGameplayLoading || hasCompetingSurfaceOpen;
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

  // ★ 音乐 store：将当前故事文本和 gameId 传递给 GlobalMusicPlayer
  const setActiveStoryText = useMusicStore((state) => state.setActiveStoryText);
  const setActiveGameId = useMusicStore((state) => state.setActiveGameId);
  useEffect(() => {
    if (gameId) {
      setActiveGameId(Number(gameId));
    }
    return () => {
      setActiveStoryText(null);
      setActiveGameId(null);
    };
  }, [gameId, setActiveStoryText, setActiveGameId]);

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

  const closeSoundPanel = useCallback(() => {
    window.dispatchEvent(new Event(CLOSE_SOUND_PANEL_EVENT));
  }, []);

  useEffect(() => {
    const handleSoundPanelState = (event: Event) => {
      const open = (event as CustomEvent<{ open?: unknown }>).detail?.open;
      if (typeof open === "boolean") setSoundSurfaceOpen(open);
    };
    window.addEventListener(SOUND_PANEL_STATE_EVENT, handleSoundPanelState);
    return () => {
      window.removeEventListener(SOUND_PANEL_STATE_EVENT, handleSoundPanelState);
    };
  }, []);

  const closeAssistantAndSound = useCallback(() => {
    requestAssistantAction("close");
    closeSoundPanel();
  }, [closeSoundPanel, requestAssistantAction]);

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

  const handleRewriteComplete = useCallback((newStory: string) => {
    setStoryText(newStory);
    const currentEvent = useGameStore.getState().currentEvent;
    if (currentEvent) {
      useGameStore.getState().setCurrentEvent({
        ...currentEvent,
        story: newStory,
      });
    }
  }, [setStoryText]);

  const handleOpenAssistantSurface = useCallback((action: ChatBarAction) => {
    closeSoundPanel();
    setShowCollection(false);
    setActiveSidePanel(null);
    if (showHistory) setShowHistory(false);
    requestAssistantAction(action);
  }, [closeSoundPanel, requestAssistantAction, setShowHistory, showHistory]);

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

  const handleOpenSound = useCallback(() => {
    requestAssistantAction("close");
    window.dispatchEvent(new Event(OPEN_SOUND_PANEL_EVENT));
  }, [requestAssistantAction]);

  const handleHome = useCallback(() => {
    closeAssistantAndSound();
    router.push("/");
  }, [closeAssistantAndSound, router]);

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
      {/* CompletedStoryMediaGate owns setActiveReadingTarget and media cancellation. */}
      <CompletedStoryMediaGate
        text={displayText}
        context={
          Number.isFinite(Number(gameId))
            ? {
                source_type: isViewingHistory ? "history_round" : "current_story",
                game_id: Number(gameId),
                week: isViewingHistory ? currentHistoryRound?.week ?? null : progress?.week ?? null,
                round_number: isViewingHistory
                  ? currentHistoryRound?.round ?? null
                  : currentRound ?? null,
                stage: "event",
                attempt_id: isViewingHistory
                  ? "history"
                  : `${progress?.week ?? 0}-${currentRound ?? 0}`,
                text_hash: "pending-client-hash",
                text: displayText,
              }
            : null
        }
        storyReady={storyReadyForCompletedMedia}
        storyBusy={isCurrentStoryBusy}
        isViewingHistory={isViewingHistory}
      />
      <PlayReadingFrame
        contentRef={storyContainerRef}
        playerState={playerState}
        progress={progress}
        isViewingHistory={isViewingHistory}
        toolsProps={{
          isSaving,
          isStoryBusy: shouldRenderGameplayLoading,
          isViewingHistory,
          constraintLevel,
          narrativeStyleId,
          narrativeStyles: narrativeStyleOptions,
          narrativeStylesLoading: styleLoading,
          rewriteDisabled: storyRewriteDisabled,
          rewriteDisabledReason: storyRewriteDisabledReason,
          soundAvailable,
          enableSceneImage,
          onSave: handleCoordinatedSave,
          onOpenHistory: handleOpenHistoryPanel,
          onOpenCollection: handleOpenCollection,
          onOpenChat: () => handleOpenAssistantSurface("chat"),
          onOpenRewrite: () => handleOpenAssistantSurface("rewrite"),
          onOpenSummary: () => handleOpenAssistantSurface("summary"),
          onRegenerate: handleCoordinatedRegenerate,
          onOpenSound: handleOpenSound,
          onHome: handleHome,
          onConstraintLevelChange: setConstraintLevel,
          onNarrativeStyleChange: handleStyleChange,
          onSceneImageChange: setEnableSceneImage,
          onRequestNarrativeStyles: loadNarrativeStyles,
          onOpenTools: handleOpenTools,
          onToolsOpenChange: setToolsSurfaceOpen,
        }}
      >
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
          onCustomChoice={handleCustomChoice}
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

      </PlayReadingFrame>

      {/* Chat bar */}
      <ChatBar
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
        className="play-chat-surface"
      />

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
