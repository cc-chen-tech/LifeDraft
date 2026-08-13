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
import { useSceneImageStore } from "@/stores/useSceneImageStore";
import { api } from "@/lib/api";
import type { EventOption } from "@/lib/types";
import { cn } from "@/lib/utils";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
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
  const [dailySettlement, setDailySettlement] = useState<Record<string, number> | null>(null);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | null = null;
    const showSettlement = (event: Event) => {
      const effects = (event as CustomEvent<Record<string, number>>).detail;
      setDailySettlement(effects);
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => setDailySettlement(null), 1800);
    };
    window.addEventListener("story2:daily-settlement", showSettlement);
    return () => {
      window.removeEventListener("story2:daily-settlement", showSettlement);
      if (timer) clearTimeout(timer);
    };
  }, []);

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
  const isDailyTimeline = playerState?.timeline?.version === 2;
  const dailyDateTitle = isDailyTimeline && playerState?.timeline?.current_date
    ? `公元 ${playerState.timeline.current_date.slice(0, 4)} 年 ${Number(playerState.timeline.current_date.slice(5, 7))} 月 ${Number(playerState.timeline.current_date.slice(8, 10))} 日`
    : null;
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

  const handleRewriteComplete = useCallback((newStory: string, replacement?: {
    event_id?: string;
    revision?: number;
    story_date?: string;
    options?: EventOption[];
  }) => {
    const currentEvent = useGameStore.getState().currentEvent;
    useSceneImageStore.getState().clearCurrentRoundImages();
    setStoryText(newStory);
    if (currentEvent) {
      useGameStore.getState().setCurrentEvent({
        ...currentEvent,
        ...replacement,
        story: newStory,
        options: replacement?.options || currentEvent.options,
      });
      if (replacement?.options?.length) {
        setOptions(replacement.options);
      }
    }
  }, [setOptions, setStoryText]);

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
        {!isViewingHistory && dailyDateTitle && (
          <div className="mb-5 text-center">
            <h1 className="font-serif text-xl font-semibold tracking-wide text-foreground">
              {dailyDateTitle}
            </h1>
            <p className="mt-1 text-xs text-muted-foreground">
              第 {playerState?.timeline?.day_number} 天 · 共 {playerState?.timeline?.total_days} 天
            </p>
          </div>
        )}
        {/* ★ 历史模式提示 */}
        {isViewingHistory && (
          <div className="mb-4 p-3 rounded-lg bg-muted/50 border border-muted">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                📖 正在查看历史轮次（只读模式）
              </p>
            </div>
          </div>
        )}
        
        {/* Loading skeleton - 历史模式下不显示 */}
        {!isViewingHistory && (phase === "loading" || phase === "generating" || phase === "choosing") && !storyText && (
          <SkeletonStory
            message={phase === "loading" ? "故事生成中..." : getLoadingMessage()}
            elapsedSeconds={elapsedSeconds}
            phase={phase === "generating" || phase === "choosing" ? getLoadingMessage() : undefined}
            qualityLevel={constraintLevel}
            onRecover={() => window.location.reload()}
          />
        )}

        {showEmptyGenerationRecovery && (
          <div className="mx-auto mb-6 max-w-md rounded-lg border border-border bg-card/70 px-4 py-3 text-center shadow-sm">
            <p className="mb-3 text-sm text-muted-foreground">
              如果生成时间较长，可以先恢复当前进度；恢复不会丢失已创建的角色和存档。
            </p>
            <Button
              variant="outline"
              className="touch-target"
              aria-label="恢复当前进度"
              onClick={handleRecoverGeneration}
            >
              <RotateCcw className="mr-2 h-4 w-4" />
              恢复当前进度
            </Button>
          </div>
        )}

        {/* Story text */}
        {displayText && (
          isViewingHistory ? (
            <Card
              data-testid="history-reading-surface"
              className="mb-6 border-primary/20 bg-card px-4 py-5 shadow-sm"
            >
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <p className="text-xs text-muted-foreground">历史回顾</p>
                  <h2 className="text-base font-medium text-foreground">
                    {currentHistoryRound?.story_date
                      ? `${currentHistoryRound.story_date} · 第 ${(currentHistoryRound.day_index ?? currentHistoryRound.round) + 1} 天`
                      : `第 ${(currentHistoryRound?.week ?? 0) + 1} 周 · 第 ${(currentHistoryRound?.round ?? 0) + 1} 轮`}
                  </h2>
                </div>
                <Button variant="outline" size="sm" onClick={handleBackToCurrent}>
                  返回当前
                </Button>
              </div>
              <StreamingText
                text={displayText}
                isStreaming={false}
                narrative
                className="mb-0"
              />
            </Card>
          ) : (
            <>
              <StreamingText
                text={displayText}
                isStreaming={phase === "generating" || phase === "choosing"}
                narrative
                className="mb-6"
              />
              {/* ★ 在有故事内容且正在生成时，显示小的加载提示（历史模式下不显示） */}
              {(phase === "generating" || phase === "choosing") && (
                <div className="space-y-2 py-2">
                  <div className="flex items-center justify-center gap-2 text-muted-foreground text-sm">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>{getLoadingMessage()}</span>
                  </div>
                  {elapsedSeconds >= 60 && (
                    <div className="mx-auto max-w-md rounded-md border border-border bg-card/70 px-4 py-3 text-center text-xs text-muted-foreground leading-relaxed">
                      <p>
                        已等待 {formatElapsedTime(elapsedSeconds)}，正在校验故事逻辑和生成选项；这通常是长剧情的一致性检查，不代表内容丢失。
                      </p>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="mt-3"
                        aria-label="恢复当前进度"
                        onClick={() => void recoverEventGeneration()}
                      >
                        <RotateCcw className="mr-2 h-3.5 w-3.5" />
                        恢复当前进度
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </>
          )
        )}

        {/* ★ 场景插画展示 */}
        {isViewingHistory ? (
          // ★ 历史模式下显示历史轮次的场景插画
          currentHistoryRound && (
            <HistorySceneImage
              sceneImage={historySceneImage}
              isLoading={isLoadingHistoryImage}
              isGenerating={isGeneratingHistoryImage}
              isRegenerating={isRegeneratingHistoryImage}
              week={currentHistoryRound.week}
              round={currentHistoryRound.round}
              storyText={historyDisplayText || ''}
              onGenerate={handleGenerateHistoryImage}
              onRegenerate={handleRegenerateHistoryImage}
            />
          )
        ) : (
          // ★ 当前模式下显示当前轮次的场景插画
          storyText && (
            <>
              {/* ★ 事件插画：只在 options 阶段显示 */}
              {sceneImageDisplayMode === "event" && eventSceneImage && (
                <RoundSceneImageDisplay
                  sceneImage={eventSceneImage}
                  isLoading={isLoadingRoundSceneImage && phase === "options"}
                  error={roundSceneError}
                  isRegenerating={isRegeneratingRoundScene}
                  currentRound={currentRound}
                  label="事件场景"
                  onRefresh={() => fetchRoundSceneImage(currentRound, "event")}
                  onRetryGeneration={() => fetchRoundSceneImage(currentRound, "event", { retry: true })}
                  onRegenerate={regenerateRoundSceneImage}
                />
              )}

              {/* ★ 结果插画：在 result/summary 阶段显示 */}
              {sceneImageDisplayMode === "result" && resultSceneImage && (
                <RoundSceneImageDisplay
                  sceneImage={resultSceneImage}
                  isLoading={isLoadingRoundSceneImage}
                  error={roundSceneError}
                  isRegenerating={isRegeneratingRoundScene}
                  currentRound={resultSceneRound}
                  label="结果场景"
                  onRefresh={() => fetchRoundSceneImage(resultSceneRound, "result")}
                  onRetryGeneration={() => fetchRoundSceneImage(resultSceneRound, "result", { retry: true })}
                  onRegenerate={regenerateRoundSceneImage}
                />
              )}

              {/* ★ 结果插画加载中：不要回退显示上一阶段事件插画，避免视觉内容滞后 */}
              {sceneImageDisplayMode === "result-loading" && (
                <RoundSceneImageDisplay
                  sceneImage={null}
                  isLoading={isLoadingRoundSceneImage}
                  error={roundSceneError}
                  isRegenerating={isRegeneratingRoundScene}
                  currentRound={resultSceneRound}
                  label="结果场景"
                  onRefresh={() => fetchRoundSceneImage(resultSceneRound, "result")}
                  onRetryGeneration={() => fetchRoundSceneImage(resultSceneRound, "result", { retry: true })}
                  onRegenerate={regenerateRoundSceneImage}
                />
              )}

              {/* ★ result/summary 阶段兜底：没有 result 插画时回退显示事件插画 */}
              {sceneImageDisplayMode === "event-fallback" && eventSceneImage && (
                <RoundSceneImageDisplay
                  sceneImage={eventSceneImage}
                  isLoading={isLoadingRoundSceneImage}
                  error={roundSceneError}
                  isRegenerating={isRegeneratingRoundScene}
                  currentRound={resultSceneRound}
                  label="事件场景"
                  onRefresh={() => fetchRoundSceneImage(resultSceneRound, "event")}
                  onRetryGeneration={() => fetchRoundSceneImage(resultSceneRound, "event", { retry: true })}
                  onRegenerate={regenerateRoundSceneImage}
                />
              )}

              {/* ★ 兜底：其他阶段显示当前轮次插画 */}
              {sceneImageDisplayMode === "current" && currentRoundSceneImage && (
                <RoundSceneImageDisplay
                  sceneImage={currentRoundSceneImage}
                  isLoading={isLoadingRoundSceneImage}
                  error={roundSceneError}
                  isRegenerating={isRegeneratingRoundScene}
                  currentRound={currentRound}
                  onRefresh={() => fetchRoundSceneImage(currentRound, phase === 'options' ? 'event' : (phase === 'result' || phase === 'summary') ? 'result' : undefined)}
                  onRetryGeneration={() => fetchRoundSceneImage(currentRound, phase === 'options' ? 'event' : (phase === 'result' || phase === 'summary') ? 'result' : undefined, { retry: true })}
                  onRegenerate={regenerateRoundSceneImage}
                />
              )}

              {sceneImageDisplayMode === "none" &&
                (roundSceneError || isLoadingRoundSceneImage) && (
                <RoundSceneImageDisplay
                  sceneImage={null}
                  isLoading={isLoadingRoundSceneImage}
                  error={roundSceneError}
                  isRegenerating={isRegeneratingRoundScene}
                  currentRound={phase === "options" ? currentRound : resultSceneRound}
                  label={phase === "options" ? "事件场景" : "结果场景"}
                  onRefresh={() => fetchRoundSceneImage(
                    phase === "options" ? currentRound : resultSceneRound,
                    phase === "options" ? "event" : "result"
                  )}
                  onRetryGeneration={() => fetchRoundSceneImage(
                    phase === "options" ? currentRound : resultSceneRound,
                    phase === "options" ? "event" : "result",
                    { retry: true }
                  )}
                  onRegenerate={regenerateRoundSceneImage}
                />
              )}
            </>
          )
        )}

        {/* Round summary - only in result phase */}
        {!isViewingHistory && roundSummary && phase === "result" && (
          <div
            className="mb-4 rounded-lg px-4 py-3 animate-fade-in-word"
            style={{ background: 'rgba(99, 102, 241, 0.2)' }}
          >
            <span className="text-[#818cf8] text-sm font-medium">📝 轮次小结：</span>
            <span className="text-[#e2e8f0] text-sm ml-2 prose-story-inline">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{roundSummary}</ReactMarkdown>
            </span>
          </div>
        )}

        {/* Choice impact display removed — effect tracking no longer stored */}

        {/* Options */}
        {!isViewingHistory && phase === "options" && options.length > 0 && (
          <div className="animate-fade-in-word">
            <OptionCards
              options={options}
              onSelect={handleChoice}
              onCustomChoice={isDailyTimeline ? undefined : handleCustomChoice}
              allowCustomChoice={!isDailyTimeline}
              disabled={false}
            />
          </div>
        )}

        {/* Result phase - waiting for user confirmation */}
        {!isDailyTimeline && !isViewingHistory && phase === "result" && (
          <div className="animate-fade-in-word space-y-4">
            {(() => {
              const currentRound = (roundInfo?.current_round as number) || 0;
              const roundsPerWeek = (roundInfo?.rounds_per_week as number) || 3;
              const roundNames = ["周一", "周中", "周末"];
              
              const isLastRound = currentRound >= roundsPerWeek;
              const nextName = roundNames[currentRound] || `第${currentRound + 1}轮`;

              return (
                <>
                  <Button
                    className="w-full touch-target"
                    onClick={handleContinueToNextRound}
                  >
                    {isLastRound ? (
                      <>
                        <CheckCircle2 className="w-4 h-4 mr-2" />
                        确认并继续
                      </>
                    ) : (
                      <>
                        <ArrowRight className="w-4 h-4 mr-2" />
                        进入{nextName}
                      </>
                    )}
                  </Button>
                  {/* ★ 预生成状态指示器 */}
                  {isPrefetching && (
                    <p className="text-xs text-muted-foreground text-center flex items-center justify-center gap-1">
                      <Loader2 className="w-3 h-3 animate-spin" />
                      正在预加载下一段故事...
                    </p>
                  )}
                </>
              );
            })()}
          </div>
        )}

        {/* Weekly summary */}
        {!isDailyTimeline && !isViewingHistory && phase === "summary" && (
          <div className="animate-page-enter space-y-6">
            <Card className="p-6 bg-card border-primary/20">
              <h3 className="text-lg font-bold text-primary mb-4">
                周总结
              </h3>
              <div className="prose-story text-sm">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{summaryText}</ReactMarkdown>
              </div>
            </Card>
            <Button
              className="w-full touch-target"
              onClick={handleContinueAfterSummary}
            >
              继续人生旅途
            </Button>
          </div>
        )}

        {/* Ending */}
        {!isViewingHistory && phase === "ending" && (
          <div className="animate-page-enter space-y-6 text-center py-12">
            <h2 className="text-2xl font-serif font-bold text-foreground">
              人生落幕
            </h2>
            {endingData ? (
              <Card className="p-6 bg-card border-border text-left">
                <pre className="text-sm text-foreground whitespace-pre-wrap font-sans">
                  {JSON.stringify(endingData, null, 2)}
                </pre>
              </Card>
            ) : (
              <SkeletonStory message="正在评估你的人生..." />
            )}
            <Button
              className="touch-target"
              onClick={() => router.push("/")}
            >
              返回首页
            </Button>
          </div>
        )}

        {/* Error state */}
        {!isViewingHistory && phase === "error" && (
          <div className="text-center py-12 space-y-4">
            <p className="text-destructive">出现错误，请重试</p>
            <Button
              variant="outline"
              onClick={() => {
                setPhase("loading");
                setTimeout(() => generateEvent(), 0);
              }}
              className="touch-target"
            >
              重试
            </Button>
          </div>
        )}
      </main>

      {/* Chat bar */}
      {!isViewingHistory && (
        <ChatBar
          gameId={gameId}
          onSave={handleSave}
          onRegenerate={handleRegenerate}
          storyText={storyText}
          onRewriteComplete={handleRewriteComplete}
          isSaving={isSaving}
          isStoryBusy={isCurrentStoryBusy}
          isViewingHistory={isViewingHistory}
          isDailyTimeline={isDailyTimeline}
        />
      )}

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

      {/* Regenerate toast */}
      {regenerateToast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 animate-fade-in-word">
          <div className={cn(
            "flex items-center gap-2 px-4 py-2.5 rounded-full text-sm font-medium shadow-lg backdrop-blur-sm",
            regenerateToast.type === "success"
              ? "bg-emerald-950/80 text-emerald-300 border border-emerald-800/50"
              : regenerateToast.type === "loading"
              ? "bg-blue-950/80 text-blue-300 border border-blue-800/50"
              : "bg-red-950/80 text-red-300 border border-red-800/50"
          )}>
            {regenerateToast.type === "success" ? (
              <><CheckCircle2 className="w-4 h-4" /> {regenerateToast.message}</>
            ) : regenerateToast.type === "loading" ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> {regenerateToast.message}</>
            ) : (
              <><XCircle className="w-4 h-4" /> {regenerateToast.message}</>
            )}
          </div>
        </div>
      )}
      {dailySettlement && (
        <div className="fixed bottom-20 left-1/2 z-50 -translate-x-1/2 rounded-full border border-primary/20 bg-background/95 px-4 py-2 text-sm shadow-lg backdrop-blur">
          {Object.entries(dailySettlement)
            .filter(([, value]) => typeof value === "number" && value !== 0)
            .map(([key, value]) => `${key} ${value > 0 ? "+" : ""}${value}`)
            .join(" · ") || "今日选择已结算"}
        </div>
      )}
    </div>
  );
}
