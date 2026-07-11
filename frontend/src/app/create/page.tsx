"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { SkeletonStory } from "@/components/game/SkeletonStory";
import { SettingDisplay } from "@/components/game/SettingDisplay";
import { useCharacterCreation } from "@/hooks/useCharacterCreation";
import {
  StepPlayerInfo,
  StepPortrait,
  AutoGenScreen,
  CompletionScreen,
} from "@/components/create";
import { PresetSaveInlineStatus } from "@/components/create/PresetSaveInlineStatus";
import { cn } from "@/lib/utils";
import {
  ArrowLeft,
  ArrowRight,
  RefreshCw,
  Loader2,
  Sparkles,
} from "lucide-react";

export default function CreatePage() {
  const {
    // Router
    router,
    
    // Game store values
    creationStep,
    characterSettings,
    playerName,
    lifeVision,
    isPresetLoaded,
    gameId,
    
    // Game store actions
    setCreationStep,
    prevCreationStep,
    setPlayerName,
    setLifeVision,
    resetCreation,
    
    // Image store values
    playerImages,
    selectedImageIndex,
    isGeneratingImage,
    imageGenerationError,
    imageFeedback,
    
    // Image store actions
    setSelectedImageIndex,
    setImageFeedback,
    generatePlayerImage,
    regeneratePlayerImage,
    regenerateFreshPlayerImage,
    regenerateSetting,

    // Local state
    isGenerating,
    feedback,
    setFeedback,
    showPresetSheet,
    setShowPresetSheet,
    presetName,
    setPresetName,
    isSavingPreset,
    presetSaveStatus,
    presetSaveMessage,
    generatedContent,
    toast,
    showToast,
    
    // Auto-gen state
    autoGenPhase,
    setAutoGenPhase,
    autoGenLabel,
    autoGenProgress,
    showDetails,
    setShowDetails,
    isBackgroundGenerating,
    
    // Computed values
    currentStepKey,
    isFirstStep,
    isLastStep,
    isPortraitStep,
    hasBasicInfo,
    
    // Handlers
    handleRegenerate,
    handleAcceptAndNext,
    handleSavePreset,
    handleStartGame,
    
    // Constants
    STEP_LABELS,
    STEP_DESCRIPTIONS,
    CREATION_STEPS,
  } = useCharacterCreation();

  const [showSlowGenerationHint, setShowSlowGenerationHint] = useState(false);

  useEffect(() => {
    if (!isGenerating) {
      setShowSlowGenerationHint(false);
      return;
    }

    setShowSlowGenerationHint(false);
    const timer = window.setTimeout(() => {
      setShowSlowGenerationHint(true);
    }, 15000);

    return () => window.clearTimeout(timer);
  }, [currentStepKey, isGenerating]);

  const canContinuePortrait = isPortraitStep && hasBasicInfo && gameId != null;
  const isContinueDisabled =
    isGenerating ||
    (isPortraitStep
      ? !canContinuePortrait
      : !generatedContent && characterSettings[currentStepKey] == null);

  // ==================== Auto-generation full-screen UI ====================
  if (autoGenPhase === "generating") {
    return <AutoGenScreen autoGenLabel={autoGenLabel} autoGenProgress={autoGenProgress} />;
  }

  if (autoGenPhase === "done") {
    return (
      <CompletionScreen
        playerName={playerName}
        playerImages={playerImages}
        selectedImageIndex={selectedImageIndex}
        characterSettings={characterSettings}
        isPresetLoaded={isPresetLoaded}
        isGenerating={isGenerating}
        hasBasicInfo={hasBasicInfo}
        showDetails={showDetails}
        showPresetSheet={showPresetSheet}
        presetName={presetName}
        isSavingPreset={isSavingPreset}
        presetSaveStatus={presetSaveStatus}
        presetSaveMessage={presetSaveMessage}
        isGeneratingImage={isGeneratingImage}
        imageFeedback={imageFeedback}
        onImageFeedbackChange={setImageFeedback}
        onRegenerateImage={() => regeneratePlayerImage(imageFeedback)}
        onRegenerateFreshImage={regenerateFreshPlayerImage}
        showToast={showToast}
        onSetShowDetails={setShowDetails}
        onSetShowPresetSheet={setShowPresetSheet}
        onSetPresetName={setPresetName}
        onBack={() => {
          setAutoGenPhase("idle");
          setCreationStep(CREATION_STEPS.length - 1);
        }}
        onStartGame={handleStartGame}
        onSavePreset={handleSavePreset}
        onRegenerateSetting={regenerateSetting}
      />
    );
  }

  // ==================== Interactive steps UI ====================
  return (
    <div className="min-h-screen bg-background animate-page-enter">
      {/* Header */}
      <header className="sticky top-0 z-40 bg-background/80 backdrop-blur-sm border-b border-border">
        <div className="max-w-2xl mx-auto px-4 h-14 flex items-center justify-between">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              resetCreation();
              router.push("/");
            }}
          >
            <ArrowLeft className="w-4 h-4 mr-1" />
            返回
          </Button>

          {/* Step indicator */}
          <div className="flex items-center gap-1">
            {CREATION_STEPS.map((_, i) => (
              <button
                key={i}
                aria-label={`第 ${i + 1} 步：${STEP_LABELS[CREATION_STEPS[i]]}`}
                aria-current={i === creationStep ? "step" : undefined}
                className={cn(
                  "w-2 h-2 rounded-full transition-all",
                  i === creationStep
                    ? "bg-primary w-6"
                    : i < creationStep
                    ? "bg-primary/50"
                    : "bg-muted"
                )}
                onClick={() => i < creationStep && setCreationStep(i)}
              />
            ))}
          </div>

          <span className="text-xs text-muted-foreground">
            {creationStep + 1}/{CREATION_STEPS.length}
          </span>
        </div>
      </header>

      <main className="max-w-2xl mx-auto px-4 py-8">
        {/* Player name input (shown at step 0) */}
        {isFirstStep && (
          <StepPlayerInfo
            playerName={playerName}
            lifeVision={lifeVision}
            onPlayerNameChange={setPlayerName}
            onLifeVisionChange={setLifeVision}
          />
        )}

        {/* Step content */}
        <div className="space-y-6">
          <div>
            <h2 className="text-xl font-bold text-foreground">
              {STEP_LABELS[currentStepKey]}
            </h2>
            <p className="text-sm text-muted-foreground mt-1">
              {STEP_DESCRIPTIONS[currentStepKey]}
            </p>
          </div>

          {/* Current setting display */}
          {characterSettings[currentStepKey] != null && !generatedContent && currentStepKey !== "portrait" && (
            <SettingDisplay
              stepKey={currentStepKey}
              data={characterSettings[currentStepKey] as Record<string, unknown>}
            />
          )}
          
          {/* Portrait step */}
          {isPortraitStep && (
            <StepPortrait
              playerImages={playerImages}
              selectedImageIndex={selectedImageIndex}
              isGeneratingImage={isGeneratingImage}
              imageGenerationError={imageGenerationError}
              playerName={playerName}
              imageFeedback={imageFeedback}
              gameId={gameId}
              isBackgroundGenerating={isBackgroundGenerating}
              onSelectImage={setSelectedImageIndex}
              onFeedbackChange={setImageFeedback}
              onRegenerate={() => regeneratePlayerImage(imageFeedback)}
              onRegenerateFresh={regenerateFreshPlayerImage}
              onRetryGeneration={() => {
                if (!gameId) return Promise.resolve();
                return generatePlayerImage(gameId, playerName, characterSettings);
              }}
              onRecover={() => window.location.reload()}
              showToast={showToast}
            />
          )}

          {/* Generated content preview */}
          {generatedContent && (
            <SettingDisplay
              stepKey={currentStepKey}
              data={generatedContent}
              isNew
            />
          )}

          {/* Loading state */}
          {isGenerating && (
            <div className="space-y-3">
              <SkeletonStory message={`AI正在生成${STEP_LABELS[currentStepKey]}...`} />
              {showSlowGenerationHint && (
                <p className="rounded-md border border-border bg-secondary/60 px-3 py-2 text-center text-sm text-muted-foreground">
                  生成时间较久，请继续等待，完成后会自动显示结果。
                </p>
              )}
            </div>
          )}

          {/* Prompt for name if needed */}
          {!isPortraitStep && !isGenerating && !generatedContent && characterSettings[currentStepKey] == null && !hasBasicInfo && (
            <div className="text-center py-8 text-muted-foreground">
              <p>请先输入角色姓名</p>
            </div>
          )}

          {/* Feedback + regenerate */}
          {(generatedContent || characterSettings[currentStepKey] != null) && !isGenerating && !isPortraitStep && (
            <div className="space-y-3">
              <div className="flex gap-2">
                <Input
                  value={feedback}
                  onChange={(e) => setFeedback(e.target.value)}
                  placeholder="不满意？告诉AI你的想法..."
                  className="flex-1 bg-secondary border-border text-sm h-10"
                />
                <Button
                  variant="outline"
                  size="icon"
                  className="h-10 w-10"
                  onClick={handleRegenerate}
                  disabled={isGenerating}
                  aria-label={`重新生成${STEP_LABELS[currentStepKey]}`}
                  title={`重新生成${STEP_LABELS[currentStepKey]}`}
                >
                  <RefreshCw className="w-4 h-4" />
                </Button>
              </div>
            </div>
          )}
        </div>

        {/* Navigation buttons */}
        <div className="flex gap-3 mt-8 pt-6 border-t border-border">
          {!isFirstStep && (
            <Button
              variant="outline"
              className="touch-target"
              onClick={() => {
                setFeedback("");
                prevCreationStep();
              }}
            >
              <ArrowLeft className="w-4 h-4 mr-1" />
              上一步
            </Button>
          )}

          <div className="flex-1" />

          <Button
            className="touch-target"
            onClick={handleAcceptAndNext}
            disabled={isContinueDisabled}
          >
            {isPortraitStep && !canContinuePortrait ? (
              <>
                <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                正在准备
              </>
            ) : isPortraitStep && playerImages.length === 0 ? (
              <>
                继续生成角色
                <ArrowRight className="w-4 h-4 ml-1" />
              </>
            ) : isPortraitStep ? (
              <>
                下一步
                <ArrowRight className="w-4 h-4 ml-1" />
              </>
            ) : isLastStep ? (
              <>
                <Sparkles className="w-4 h-4 mr-1" />
                生成角色
              </>
            ) : (
              <>
                下一步
                <ArrowRight className="w-4 h-4 ml-1" />
              </>
            )}
          </Button>
        </div>
      </main>

      {/* Save preset sheet */}
      <Sheet open={showPresetSheet} onOpenChange={setShowPresetSheet}>
        <SheetContent side="bottom" className="bg-card border-t border-border">
          <SheetHeader>
            <SheetTitle className="text-foreground">保存角色预设</SheetTitle>
            <SheetDescription className="text-muted-foreground">
              保存当前角色设定以便下次使用
            </SheetDescription>
          </SheetHeader>
          <div className="space-y-4 mt-4">
            <Input
              value={presetName}
              onChange={(e) => setPresetName(e.target.value)}
              placeholder="预设名称"
              className="bg-secondary border-border h-12"
              autoFocus
            />
            <PresetSaveInlineStatus
              status={presetSaveStatus}
              message={presetSaveMessage}
            />
            <Button
              className="w-full touch-target"
              disabled={!presetName.trim() || isSavingPreset}
              onClick={handleSavePreset}
            >
              {isSavingPreset && (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              )}
              保存
            </Button>
          </div>
        </SheetContent>
      </Sheet>

      {/* Toast */}
      {toast && (
        <div
          className={cn(
            "fixed bottom-20 left-1/2 -translate-x-1/2 px-4 py-2 rounded-lg text-sm z-50 animate-fade-in",
            toast.type === "success"
              ? "bg-green-500/90 text-white"
              : "bg-red-500/90 text-white"
          )}
        >
          {toast.message}
        </div>
      )}
    </div>
  );
}
