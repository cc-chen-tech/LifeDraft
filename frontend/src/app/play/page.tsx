"use client";

import { useState, useEffect, Suspense, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
} from "@/components/ui/dropdown-menu";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { StreamingText } from "@/components/game/StreamingText";
import { OptionCards } from "@/components/game/OptionCards";
import { StatusBar } from "@/components/game/StatusBar";
import { SkeletonStory } from "@/components/game/SkeletonStory";
import { ChatBar } from "@/components/game/ChatBar";
import { RoundHistoryDrawer } from "@/components/game/RoundHistoryDrawer";
import { RoundSceneImageDisplay } from "@/components/game/RoundSceneImage";
import { HistorySceneImage } from "@/components/game/HistorySceneImage";
import { CollectionPanel } from "@/components/game/CollectionPanel";

import { usePlayGame, STATUS_MESSAGES } from "@/hooks/usePlayGame";
import { useGameIdFromUrl } from "@/hooks/useGameIdFromUrl";
import { useGameStore } from "@/stores/useGameStore";
import { useMusicStore } from "@/stores/useMusicStore";
import { useStoryVoiceStore } from "@/stores/useStoryVoiceStore";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Save,
  Loader2,
  Home,
  CheckCircle2,
  XCircle,
  History,
  Settings,
  BookOpen,
  Users,
  ArrowRight,
  Palette,
  RotateCcw,
} from "lucide-react";

function formatElapsedTime(seconds: number): string {
  if (seconds < 60) return `${seconds}秒`;
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}分${secs}秒`;
}

/**
 * GameIdSync - 内部组件，使用 useGameIdFromUrl 同步 URL 参数
 * 必须包裹在 Suspense 中
 */
function GameIdSync() {
  useGameIdFromUrl();
  return null;
}

/**
 * PlayPage - Main game play page component.
 *
 * Uses usePlayGame hook for all business logic.
 * This component only handles UI rendering.
 */
export default function PlayPage() {
  // ★ 收集面板状态
  const [showCollection, setShowCollection] = useState(false);

  // ★ 故事风格状态
  const [narrativeStyleId, setNarrativeStyleId] = useState<string>("");
  const [narrativeStyleOptions, setNarrativeStyleOptions] = useState<Array<{ style_id: string; style_name: string; description: string }>>([]);
  const [styleLoading, setStyleLoading] = useState(false);

  const {
    // State
    phase,
    options,
    summaryText,
    roundSummary,
    isSaving,
    saveToast,
    regenerateToast,
    endingData,
    elapsedSeconds,
    isPrefetching,  // ★ 预生成状态

    // Store values
    gameId,
    playerState,
    progress,
    roundInfo,
    storyText,
    isGameOver,

    // Refs
    storyContainerRef,

    // Actions
    setPhase,
    setStoryText,
    setOptions,

    // Handlers
    handleChoice,
    handleCustomChoice,
    handleContinueAfterSummary,
    handleContinueToNextRound,
    handleSave,
    handleRegenerate,
    generateEvent,
    recoverEventGeneration,

    // Utilities
    getLoadingMessage,
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
    roundSceneImages,
    currentRoundSceneImage,
    eventSceneImage,  // ★ 事件插画
    resultSceneImage,  // ★ 结果插画
    isLoadingRoundSceneImage,
    isRegeneratingRoundScene,
    fetchRoundSceneImage,
    regenerateRoundSceneImage,
    setEventSceneImage,  // ★ 设置事件插画
    setResultSceneImage,  // ★ 设置结果插画
    // ★ 历史场景插画
    historySceneImage,
    isLoadingHistoryImage,
    isGeneratingHistoryImage,
    isRegeneratingHistoryImage,
    currentRound,
  } = usePlayGame();

  const resultSceneRound = Math.max(0, currentRound - 1);
  const storyReadyForCompletedMedia = phase === "options" || phase === "result";
  const isCurrentStoryBusy = phase === "loading" || phase === "generating" || phase === "choosing";

  // ★ 音乐 store：将当前故事文本和 gameId 传递给 GlobalMusicPlayer
  const setActiveStoryText = useMusicStore((state) => state.setActiveStoryText);
  const setActiveGameId = useMusicStore((state) => state.setActiveGameId);
  const setActiveReadingTarget = useStoryVoiceStore((state) => state.setActiveReadingTarget);
  const clearActiveReadingTarget = useStoryVoiceStore((state) => state.clearActiveReadingTarget);

  useEffect(() => {
    if (storyText && !isViewingHistory && storyReadyForCompletedMedia) {
      setActiveStoryText(storyText);
    }
  }, [storyText, isViewingHistory, storyReadyForCompletedMedia, setActiveStoryText]);

  useEffect(() => {
    const numericGameId = Number(gameId);
    if (!displayText || !Number.isFinite(numericGameId)) {
      clearActiveReadingTarget();
      return;
    }

    setActiveReadingTarget({
      context: isViewingHistory
        ? {
            source_type: "history_round",
            game_id: numericGameId,
            week: currentHistoryRound?.week ?? null,
            round_number: currentHistoryRound?.round ?? null,
            stage: "event",
            attempt_id: "history",
            text_hash: "pending-client-hash",
            text: displayText,
          }
        : {
            source_type: "current_story",
            game_id: numericGameId,
            week: progress?.week ?? null,
            round_number: currentRound ?? null,
            stage: "event",
            attempt_id: `${progress?.week ?? 0}-${currentRound ?? 0}`,
            text_hash: "pending-client-hash",
            text: displayText,
          },
      autoReadText: displayText,
      autoReadReady: !isViewingHistory && storyReadyForCompletedMedia,
    });
  }, [
    clearActiveReadingTarget,
    currentHistoryRound?.round,
    currentHistoryRound?.week,
    currentRound,
    displayText,
    gameId,
    isViewingHistory,
    progress?.week,
    setActiveReadingTarget,
    storyReadyForCompletedMedia,
  ]);

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

  const showEmptyGenerationRecovery =
    !isViewingHistory &&
    phase === "loading" &&
    !storyText &&
    !displayText &&
    options.length === 0;

  const handleRecoverGeneration = useCallback(() => {
    setOptions([]);
    setPhase("loading");
    setTimeout(() => recoverEventGeneration(), 0);
  }, [recoverEventGeneration, setOptions, setPhase]);

  const handleOpenCollection = useCallback(() => {
    setShowCollection(true);
    setShowHistory(false);
    if (isViewingHistory) {
      handleBackToCurrent();
    }
  }, [handleBackToCurrent, isViewingHistory, setShowHistory]);

  const handleOpenHistoryPanel = useCallback(() => {
    setShowCollection(false);
    handleOpenHistory();
  }, [handleOpenHistory]);

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

  // Don't render until hydrated
  if (!hydrated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
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
              如果没有可恢复的游戏，页面会返回首页。你也可以手动返回或重新加载。
            </p>
          </div>
          <div className="flex items-center justify-center gap-3">
            <Button variant="outline" onClick={() => router.replace("/")}>
              <Home className="mr-2 h-4 w-4" />
              返回首页
            </Button>
            <Button variant="secondary" onClick={() => window.location.reload()}>
              <RotateCcw className="mr-2 h-4 w-4" />
              重新加载
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex flex-col bg-background">
      {/* ★ URL 参数同步 - 必须在 Suspense 中 */}
      <Suspense fallback={null}>
        <GameIdSync />
      </Suspense>
      {/* Header */}
      <header className="sticky top-0 z-40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 border-b border-border">
        <div className="max-w-3xl mx-auto px-4 py-3 flex items-center justify-between">
          {/* Status bar */}
          <StatusBar
            playerState={playerState}
            progress={progress}
            compact
          />
          
          {/* Actions */}
          <div className="flex items-center gap-2">
            {/* ★ 收集按钮 */}
            <Button
              variant="ghost"
              size="sm"
              className="h-8 px-2"
              onClick={handleOpenCollection}
              title="收集"
              aria-label="收集"
            >
              <BookOpen className="w-4 h-4 md:mr-1.5" />
              <span className="hidden md:inline text-xs">收集</span>
            </Button>
            {/* ★ 好友按钮 */}
            <Button
              variant="ghost"
              size="sm"
              className="h-8 px-2"
              onClick={() => router.push("/profile")}
              title="好友"
              aria-label="好友"
            >
              <Users className="w-4 h-4 md:mr-1.5" />
              <span className="hidden md:inline text-xs">好友</span>
            </Button>
            {/* ★ 历史回顾按钮 */}
            <Button
              variant="ghost"
              size="sm"
              className={cn("h-8 px-2", isViewingHistory && "text-primary")}
              onClick={handleOpenHistoryPanel}
              title="历史回顾"
              aria-label="历史回顾"
            >
              <History className="w-4 h-4 md:mr-1.5" />
              <span className="hidden md:inline text-xs">历史</span>
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 px-2"
              onClick={() => router.push("/")}
              title="返回首页"
              aria-label="返回首页"
            >
              <Home className="w-4 h-4 md:mr-1.5" />
              <span className="hidden md:inline text-xs">首页</span>
            </Button>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="sm" className="h-8 px-2" title="设置" aria-label="设置">
                  <Settings className="w-4 h-4 md:mr-1.5" />
                  <span className="hidden md:inline text-xs">设置</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>设置</DropdownMenuLabel>
                <DropdownMenuSeparator />
                
                {/* 叙事质量 */}
                <DropdownMenuSub>
                  <DropdownMenuSubTrigger>叙事质量</DropdownMenuSubTrigger>
                  <DropdownMenuSubContent>
                    <DropdownMenuRadioGroup value={constraintLevel} onValueChange={(value) => setConstraintLevel(value as "fast" | "expert" | "master")}>
                      <DropdownMenuRadioItem value="fast">快速</DropdownMenuRadioItem>
                      <DropdownMenuRadioItem value="expert">专家</DropdownMenuRadioItem>
                      <DropdownMenuRadioItem value="master">大师</DropdownMenuRadioItem>
                    </DropdownMenuRadioGroup>
                  </DropdownMenuSubContent>
                </DropdownMenuSub>
                
                <DropdownMenuSeparator />
                
                {/* 故事风格 */}
                <DropdownMenuSub onOpenChange={(open: boolean) => { if (open) loadNarrativeStyles(); }}>
                  <DropdownMenuSubTrigger>
                    <Palette className="w-3.5 h-3.5 mr-1.5" />叙事风格
                  </DropdownMenuSubTrigger>
                  <DropdownMenuSubContent className="max-h-64 overflow-y-auto">
                    {styleLoading ? (
                      <DropdownMenuItem disabled>
                        <Loader2 className="w-3 h-3 animate-spin mr-1.5" />加载中...
                      </DropdownMenuItem>
                    ) : (
                      <DropdownMenuRadioGroup value={narrativeStyleId} onValueChange={handleStyleChange}>
                        {narrativeStyleOptions.map((s) => (
                          <DropdownMenuRadioItem key={s.style_id} value={s.style_id} title={s.description}>
                            {s.style_name}
                          </DropdownMenuRadioItem>
                        ))}
                      </DropdownMenuRadioGroup>
                    )}
                  </DropdownMenuSubContent>
                </DropdownMenuSub>

                <DropdownMenuSeparator />

                {/* 场景插画开关 */}
                <DropdownMenuItem onClick={() => setEnableSceneImage(!enableSceneImage)}>
                  {enableSceneImage ? "关闭场景插画" : "开启场景插画"}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>

      {/* Main content area */}
      <main
        ref={storyContainerRef}
        className="flex-1 max-w-3xl mx-auto w-full px-4 py-6 pb-28"
      >
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
                    第 {(currentHistoryRound?.week ?? 0) + 1} 周 · 第 {(currentHistoryRound?.round ?? 0) + 1} 轮
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
              {phase === "options" && eventSceneImage && (
                <RoundSceneImageDisplay
                  sceneImage={eventSceneImage}
                  isLoading={isLoadingRoundSceneImage && phase === "options"}
                  isRegenerating={isRegeneratingRoundScene}
                  currentRound={currentRound}
                  label="事件场景"
                  onRefresh={() => fetchRoundSceneImage(currentRound, "event")}
                  onRegenerate={regenerateRoundSceneImage}
                />
              )}

              {/* ★ 结果插画：只在 result 阶段显示 */}
              {phase === "result" && resultSceneImage && (
                <RoundSceneImageDisplay
                  sceneImage={resultSceneImage}
                  isLoading={isLoadingRoundSceneImage}
                  isRegenerating={isRegeneratingRoundScene}
                  currentRound={resultSceneRound}
                  label="结果场景"
                  onRefresh={() => fetchRoundSceneImage(resultSceneRound, "result")}
                  onRegenerate={regenerateRoundSceneImage}
                />
              )}

              {/* ★ result 阶段兜底：没有 result 插画时回退显示事件插画 */}
              {phase === "result" && !resultSceneImage && eventSceneImage && (
                <RoundSceneImageDisplay
                  sceneImage={eventSceneImage}
                  isLoading={isLoadingRoundSceneImage}
                  isRegenerating={isRegeneratingRoundScene}
                  currentRound={resultSceneRound}
                  label="事件场景"
                  onRefresh={() => fetchRoundSceneImage(resultSceneRound, "event")}
                  onRegenerate={regenerateRoundSceneImage}
                />
              )}

              {/* ★ 兜底：其他阶段显示当前轮次插画 */}
              {!eventSceneImage && !resultSceneImage && currentRoundSceneImage && (
                <RoundSceneImageDisplay
                  sceneImage={currentRoundSceneImage}
                  isLoading={isLoadingRoundSceneImage}
                  isRegenerating={isRegeneratingRoundScene}
                  currentRound={currentRound}
                  onRefresh={() => fetchRoundSceneImage(currentRound, phase === 'options' ? 'event' : phase === 'result' ? 'result' : undefined)}
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
              onCustomChoice={handleCustomChoice}
              disabled={false}
            />
          </div>
        )}

        {/* Result phase - waiting for user confirmation */}
        {!isViewingHistory && phase === "result" && (
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
        {!isViewingHistory && phase === "summary" && (
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
        />
      )}

      {/* ★ 历史回顾抽屉 */}
      <RoundHistoryDrawer
        open={showHistory}
        onOpenChange={setShowHistory}
        roundHistory={roundHistory}
        selectedIndex={historyRoundIndex}
        onSelect={handleSelectHistoryRound}
        onBackToCurrent={() => {
          handleBackToCurrent();
          setShowHistory(false);
        }}
        isViewingHistory={isViewingHistory}
      />

      {/* ★ 收集面板 */}
      <Sheet modal={false} open={showCollection} onOpenChange={setShowCollection}>
        <SheetContent
          side="right"
          className="w-[400px] sm:w-[540px] p-0"
          overlayClassName="pointer-events-none bg-transparent"
        >
          <SheetTitle className="sr-only">收集</SheetTitle>
          <CollectionPanel gameId={gameId || 0} />
        </SheetContent>
      </Sheet>

      {/* Save toast */}
      {saveToast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 animate-fade-in-word">
          <div className={cn(
            "flex items-center gap-2 px-4 py-2.5 rounded-full text-sm font-medium shadow-lg backdrop-blur-sm",
            saveToast === "success"
              ? "bg-emerald-950/80 text-emerald-300 border border-emerald-800/50"
              : "bg-red-950/80 text-red-300 border border-red-800/50"
          )}>
            {saveToast === "success" ? (
              <><CheckCircle2 className="w-4 h-4" /> 已保存</>
            ) : (
              <><XCircle className="w-4 h-4" /> 保存失败</>
            )}
          </div>
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
    </div>
  );
}
