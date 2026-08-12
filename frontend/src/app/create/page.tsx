"use client";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { LengthIndicator } from "@/components/ui/length-indicator";
import {
  FormField,
  PageEdgeBookmark,
  PageTransition,
  Surface,
} from "@/components/story101";
import { INPUT_LIMITS } from "@/types/input-limits.generated";
import { isWithinInputLimit } from "@/lib/inputLimits";
import {
  NarrativeLoadingState,
  getNarrativeLoadingDelay,
} from "@/components/narrative-loading/NarrativeLoadingState";
import { SettingDisplay } from "@/components/game/SettingDisplay";
import { useCharacterCreation } from "@/hooks/useCharacterCreation";
import { useDelayedLoading } from "@/hooks/useDelayedLoading";
import {
  StepPlayerInfo,
  StepPortrait,
  CompletionScreen,
  CreateFeedbackToast,
  PresetSaveSheet,
} from "@/components/create";
import {
  ArrowLeft,
  ArrowRight,
  RefreshCw,
  Loader2,
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
    refreshPortraitImageJob,
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

  const isStepLoadingDelayed = useDelayedLoading({
    isLoading: isGenerating,
    delay: getNarrativeLoadingDelay("character-step"),
    loadingIdentity: isGenerating ? currentStepKey : null,
  });
  const isAutoLoadingDelayed = useDelayedLoading({
    isLoading: autoGenPhase === "generating",
    delay: getNarrativeLoadingDelay("character-auto"),
    loadingIdentity: autoGenPhase === "generating" ? "character-auto" : null,
  });

  const canContinuePortrait = isPortraitStep && hasBasicInfo && gameId != null;
  const isContinueDisabled =
    isGenerating ||
    (isPortraitStep
      ? !canContinuePortrait
      : !generatedContent && characterSettings[currentStepKey] == null);
  const isFeedbackOverLimit = !isWithinInputLimit(
    feedback,
    INPUT_LIMITS.feedback,
  );
  const visibleStepDescription =
    currentStepKey === "world"
      ? "根据已有设定构建你的世界观"
      : currentStepKey === "portrait"
        ? "根据已有设定生成人物形象"
        : STEP_DESCRIPTIONS[currentStepKey];

  // ==================== Auto-generation full-screen UI ====================
  if (autoGenPhase === "generating") {
    return (
      <NarrativeLoadingState
        context="character-auto"
        layout="screen"
        phase="generating"
        stepLabel={autoGenLabel || "剩余角色背景"}
        delayed={isAutoLoadingDelayed}
      />
    );
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
        toast={toast}
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
    <>
      <PageTransition className="min-h-screen bg-[var(--surface-canvas)]">
      <header className="sticky top-0 z-40 border-b border-[var(--border-default)] bg-[var(--surface-canvas)]/95 backdrop-blur-sm">
        <div className="mx-auto flex min-h-16 max-w-5xl items-center gap-3 px-4">
          <Button
            variant="quiet"
            size="touch"
            onClick={() => {
              resetCreation();
              router.push("/");
            }}
          >
            <ArrowLeft />
            返回
          </Button>
          <div className="min-w-0 flex-1 text-center">
            <p className="truncate text-sm font-medium text-[var(--text-primary)]">
              story101
            </p>
            <p className="hidden text-xs text-[var(--text-secondary)] sm:block">
              人生草稿本
            </p>
          </div>
          <span className="min-w-11 text-right text-xs text-[var(--text-secondary)]">
            {creationStep + 1}/{CREATION_STEPS.length}
          </span>
        </div>
      </header>

      <div className="mx-auto grid w-full max-w-5xl gap-5 px-4 py-6 md:grid-cols-[9rem_minmax(0,1fr)] md:gap-8 md:py-10">
        <PageEdgeBookmark
          label={STEP_LABELS[currentStepKey]}
          detail={`第 ${creationStep + 1} 步，共 ${CREATION_STEPS.length} 步`}
        />

        <Surface variant="reading" className="min-w-0 p-5 sm:p-8">
          <nav
            aria-label="角色创建步骤"
            className="mb-8 border-b border-[var(--border-default)] pb-5"
          >
            <ol className="grid grid-cols-2 gap-2 sm:grid-cols-5">
              {CREATION_STEPS.map((step, index) => {
                const isCurrent = index === creationStep;
                const isPrevious = index < creationStep;
                const label = STEP_LABELS[step];

                return (
                  <li key={step} className="min-w-0">
                    <Button
                      type="button"
                      variant={isCurrent ? "narrative" : "quiet"}
                      size="touch"
                      className={`w-full min-w-0 justify-start text-sm sm:justify-center ${
                        isCurrent ? "disabled:opacity-100" : ""
                      }`}
                      aria-label={`前往${label}`}
                      aria-current={isCurrent ? "step" : undefined}
                      disabled={!isPrevious}
                      onClick={() => setCreationStep(index)}
                    >
                      <span className="truncate">{label}</span>
                    </Button>
                  </li>
                );
              })}
            </ol>
          </nav>

          {isFirstStep && (
            <StepPlayerInfo
              playerName={playerName}
              lifeVision={lifeVision}
              onPlayerNameChange={setPlayerName}
              onLifeVisionChange={setLifeVision}
            />
          )}

          <section className="min-w-0" aria-labelledby="creation-step-title">
            {!isGenerating && (
              <div className="mb-6 min-w-0">
                <h2
                  id="creation-step-title"
                  className="break-words font-serif text-2xl font-semibold text-[var(--text-primary)]"
                >
                  {STEP_LABELS[currentStepKey]}
                </h2>
                <p className="mt-2 break-words text-sm leading-relaxed text-[var(--text-secondary)]">
                  {visibleStepDescription}
                </p>
              </div>
            )}

            {characterSettings[currentStepKey] != null &&
              !generatedContent &&
              currentStepKey !== "portrait" && (
                <SettingDisplay
                  stepKey={currentStepKey}
                  data={characterSettings[currentStepKey] as Record<string, unknown>}
                />
              )}

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
                onRecover={() => {
                  if (gameId) void refreshPortraitImageJob(gameId);
                }}
                showToast={showToast}
              />
            )}

            {generatedContent && (
              <SettingDisplay
                stepKey={currentStepKey}
                data={generatedContent}
                isNew
              />
            )}

            {isGenerating && (
              <NarrativeLoadingState
                context="character-step"
                layout="section"
                phase="generating"
                stepLabel={STEP_LABELS[currentStepKey]}
                delayed={isStepLoadingDelayed}
              />
            )}

            {!isPortraitStep &&
              !isGenerating &&
              !generatedContent &&
              characterSettings[currentStepKey] == null &&
              !hasBasicInfo && (
                <p className="border-l-2 border-[var(--border-default)] py-2 pl-3 text-sm text-[var(--text-secondary)]">
                  请先输入角色姓名
                </p>
              )}

            {(generatedContent || characterSettings[currentStepKey] != null) &&
              !isGenerating &&
              !isPortraitStep && (
                <div className="mt-6 border-t border-[var(--border-default)] pt-5">
                  <FormField
                    id="setting-feedback"
                    label={`${STEP_LABELS[currentStepKey]}修改意见`}
                    description="写下需要保留和调整的方向。"
                    error={isFeedbackOverLimit ? `修改意见不能超过 ${INPUT_LIMITS.feedback} 字` : undefined}
                  >
                    {({ describedBy, invalid }) => (
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
                        <div className="min-w-0 flex-1">
                          <Textarea
                            id="setting-feedback"
                            value={feedback}
                            onChange={(event) => setFeedback(event.target.value)}
                            placeholder="写下你想调整的方向"
                            surface="underline"
                            controlSize="touch"
                            className="min-h-24 resize-y text-sm"
                            aria-describedby={[describedBy, "setting-feedback-count"].filter(Boolean).join(" ")}
                            aria-invalid={invalid}
                          />
                          <LengthIndicator
                            id="setting-feedback-count"
                            value={feedback}
                            limit={INPUT_LIMITS.feedback}
                            announce={false}
                          />
                        </div>
                        <Button
                          type="button"
                          variant="narrative"
                          size="icon-touch"
                          onClick={handleRegenerate}
                          disabled={isGenerating || isFeedbackOverLimit}
                          aria-label={`重新生成${STEP_LABELS[currentStepKey]}`}
                          title={`重新生成${STEP_LABELS[currentStepKey]}`}
                        >
                          <RefreshCw />
                        </Button>
                      </div>
                    )}
                  </FormField>
                </div>
              )}
          </section>

          <div className="mt-8 flex flex-col-reverse gap-3 border-t border-[var(--border-default)] pt-6 sm:flex-row sm:justify-between">
            {!isFirstStep ? (
              <Button
                type="button"
                variant="narrative"
                size="touch"
                onClick={() => {
                  setFeedback("");
                  prevCreationStep();
                }}
              >
                <ArrowLeft />
                上一步
              </Button>
            ) : (
              <span aria-hidden="true" />
            )}

            <Button
              type="button"
              size="touch"
              onClick={handleAcceptAndNext}
              disabled={isContinueDisabled}
            >
              {isPortraitStep && !canContinuePortrait ? (
                <>
                  <Loader2 className="animate-spin" />
                  正在准备
                </>
              ) : isPortraitStep && playerImages.length === 0 ? (
                <>
                  继续生成角色
                  <ArrowRight />
                </>
              ) : isPortraitStep ? (
                <>
                  下一步
                  <ArrowRight />
                </>
              ) : isLastStep ? (
                <>生成角色</>
              ) : (
                <>
                  下一步
                  <ArrowRight />
                </>
              )}
            </Button>
          </div>
        </Surface>
      </div>

      <PresetSaveSheet
        open={showPresetSheet}
        onOpenChange={setShowPresetSheet}
        presetName={presetName}
        onPresetNameChange={setPresetName}
        isSaving={isSavingPreset}
        status={presetSaveStatus}
        message={presetSaveMessage}
        onSave={handleSavePreset}
      />
      </PageTransition>

      <CreateFeedbackToast
        toast={toast}
        suppressed={showPresetSheet && presetSaveStatus === "error"}
      />
    </>
  );
}
