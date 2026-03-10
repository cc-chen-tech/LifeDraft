"use client";

import { useState, Suspense } from "react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
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
import { StoryAdjuster } from "@/components/game/StoryAdjuster";
import { RoundHistoryDrawer } from "@/components/game/RoundHistoryDrawer";
import { RoundSceneImageDisplay } from "@/components/game/RoundSceneImage";
import { CollectionPanel } from "@/components/game/CollectionPanel";
import { usePlayGame, STATUS_MESSAGES } from "@/hooks/usePlayGame";
import { useGameIdFromUrl } from "@/hooks/useGameIdFromUrl";
import { useGameStore } from "@/stores/useGameStore";
import { cn } from "@/lib/utils";
import {
  Save,
  Loader2,
  Home,
  CheckCircle2,
  XCircle,
  History,
  Settings,
  BookOpen,
} from "lucide-react";

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

  const {
    // State
    phase,
    options,
    summaryText,
    roundSummary,
    isSaving,
    saveToast,
    regenerateToast,
    showAdjuster,
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
    setShowAdjuster,
    setStoryText,
    setOptions,

    // Handlers
    handleChoice,
    handleCustomChoice,
    handleContinueAfterSummary,
    handleContinueToNextRound,
    handleSave,
    handleAdjustStory,
    handleRegenerate,
    generateEvent,

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
    handleOpenHistory,
    handleSelectHistoryRound,
    handleBackToCurrent,
    
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
    currentRound,
  } = usePlayGame();

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
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
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
              size="icon"
              className="h-8 w-8"
              onClick={() => setShowCollection(true)}
              title="收集"
            >
              <BookOpen className="w-4 h-4" />
            </Button>
            {/* ★ 历史回顾按钮 */}
            <Button
              variant="ghost"
              size="icon"
              className={cn("h-8 w-8", isViewingHistory && "text-primary")}
              onClick={handleOpenHistory}
              title="历史回顾"
            >
              <History className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => router.push("/")}
            >
              <Home className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className={cn("h-8 w-8", isSaving && "animate-pulse")}
              onClick={handleSave}
              disabled={isSaving}
            >
              {isSaving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
            </Button>
            <Button 
              variant="ghost" 
              size="icon" 
              className="h-8 w-8"
              onClick={() => {
                const current = useGameStore.getState().enableSceneImage;
                useGameStore.getState().setEnableSceneImage(!current);
              }}
              title="场景插画设置"
            >
              <Settings className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </header>

      {/* Main content area */}
      <main
        ref={storyContainerRef}
        className="flex-1 max-w-3xl mx-auto w-full px-4 py-6 pb-20"
      >
        {/* ★ 历史模式提示 */}
        {isViewingHistory && (
          <div className="mb-4 p-3 rounded-lg bg-muted/50 border border-muted">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                📖 正在查看历史轮次（只读模式）
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={handleBackToCurrent}
              >
                返回当前
              </Button>
            </div>
          </div>
        )}
        
        {/* Loading skeleton - 历史模式下不显示 */}
        {!isViewingHistory && (phase === "loading" || phase === "generating" || phase === "choosing") && !storyText && (
          <SkeletonStory
            message={phase === "loading" ? "故事生成中..." : getLoadingMessage()}
            elapsedSeconds={elapsedSeconds}
          />
        )}

        {/* Story text */}
        {displayText && (
          <>
            <StreamingText
              text={displayText}
              isStreaming={!isViewingHistory && (phase === "generating" || phase === "choosing")}
              narrative
              className="mb-6"
            />
            {/* ★ 在有故事内容且正在生成时，显示小的加载提示（历史模式下不显示） */}
            {!isViewingHistory && (phase === "generating" || phase === "choosing") && (
              <div className="flex items-center justify-center gap-2 text-muted-foreground text-sm py-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>{getLoadingMessage()}</span>
              </div>
            )}
          </>
        )}

        {/* ★ 场景插画展示 */}
        {!isViewingHistory && storyText && (
          <>
            {/* ★ 事件插画：options 阶段和 result 阶段都显示 */}
            {(phase === "options" || phase === "result") && eventSceneImage && (
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
                currentRound={currentRound}
                label="结果场景"
                onRefresh={() => fetchRoundSceneImage(currentRound, "result")}
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
        )}

        {/* Round summary - only in result phase */}
        {roundSummary && phase === "result" && (
          <div 
            className="mb-4 rounded-lg px-4 py-3 animate-fade-in-word" 
            style={{ background: 'rgba(99, 102, 241, 0.2)' }}
          >
            <span className="text-[#818cf8] text-sm font-medium">📝 轮次小结：</span>
            <span className="text-[#e2e8f0] text-sm ml-2">{roundSummary}</span>
          </div>
        )}

        {/* Options */}
        {phase === "options" && options.length > 0 && (
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
        {phase === "result" && (
          <div className="animate-fade-in-word space-y-4">
            {(() => {
              const currentRound = (roundInfo?.current_round as number) || 0;
              const roundsPerWeek = (roundInfo?.rounds_per_week as number) || 3;
              const roundNames = ["周一", "周中", "周末"];
              
              let buttonText = "✅ 确认并继续";
              if (currentRound < roundsPerWeek) {
                const nextName = roundNames[currentRound] || `第${currentRound + 1}轮`;
                buttonText = `➡️ 进入${nextName}`;
              }
              
              return (
                <>
                  <Button
                    className="w-full touch-target"
                    onClick={handleContinueToNextRound}
                  >
                    {buttonText}
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
        {phase === "summary" && (
          <div className="animate-page-enter space-y-6">
            <Card className="p-6 bg-card border-primary/20">
              <h3 className="text-lg font-bold text-primary mb-4">
                周总结
              </h3>
              <div className="prose-story text-sm">
                {summaryText.split("\n").map((line, i) => (
                  <p key={i}>{line}</p>
                ))}
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
        {phase === "ending" && (
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
        {phase === "error" && (
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
      <ChatBar
        gameId={gameId}
        onSave={handleSave}
        onAdjustStory={handleAdjustStory}
        onRegenerate={handleRegenerate}
        isSaving={isSaving}
        isViewingHistory={isViewingHistory}
      />

      {/* Story adjuster */}
      <StoryAdjuster
        open={showAdjuster}
        onOpenChange={setShowAdjuster}
        gameId={gameId || 0}
        fullStory={storyText}
        onRewriteComplete={(newStory) => {
          setStoryText(newStory);
        }}
        onRegenerateComplete={handleRegenerate}
      />

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
      <Sheet open={showCollection} onOpenChange={setShowCollection}>
        <SheetContent side="right" className="w-[400px] sm:w-[540px] p-0">
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
