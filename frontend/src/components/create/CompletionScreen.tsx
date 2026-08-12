"use client";

import { useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { LengthIndicator } from "@/components/ui/length-indicator";
import { FormField, PageTransition, Surface } from "@/components/story101";
import { INPUT_LIMITS } from "@/types/input-limits.generated";
import { isWithinInputLimit } from "@/lib/inputLimits";
import { SettingFeedbackCard } from "./SettingFeedbackCard";
import { PresetSaveSheet } from "./PresetSaveSheet";
import { CreateFeedbackToast } from "./CreateFeedbackToast";
import type {
  PresetSaveStatus,
  ToastType,
} from "@/hooks/useCharacterCreation";
import {
  ArrowLeft,
  Loader2,
  Save,
  Play,
  ChevronDown,
  ChevronUp,
  Eye,
  RefreshCw,
  RotateCcw,
  User,
} from "lucide-react";

const STEP_LABELS: Record<string, string> = {
  era: "时代背景",
  age: "年龄阶段",
  gender: "性别",
  world: "世界观",
  portrait: "人物形象",
  family: "家庭背景",
  relationships: "人际关系",
  traits: "性格特征",
};

const AUTO_ADVANCE_STEPS = ["family", "relationships", "traits"];

interface CompletionScreenProps {
  playerName: string;
  playerImages: Array<{ image_id: number; image_url: string }>;
  selectedImageIndex: number;
  characterSettings: Record<string, unknown>;
  isPresetLoaded: boolean;
  isGenerating: boolean;
  hasBasicInfo: boolean;
  showDetails: boolean;
  showPresetSheet: boolean;
  presetName: string;
  isSavingPreset: boolean;
  presetSaveStatus: PresetSaveStatus;
  presetSaveMessage: string;
  toast: ToastType;
  // Image regeneration
  isGeneratingImage: boolean;
  imageFeedback: string;
  onImageFeedbackChange: (feedback: string) => void;
  onRegenerateImage: () => Promise<void>;
  onRegenerateFreshImage: () => Promise<void>;
  showToast: (type: "success" | "error", message: string) => void;
  onSetShowDetails: (show: boolean) => void;
  onSetShowPresetSheet: (show: boolean) => void;
  onSetPresetName: (name: string) => void;
  onBack: () => void;
  onStartGame: () => Promise<void>;
  onSavePreset: () => Promise<void>;
  onRegenerateSetting: (stepKey: string, feedback: string) => Promise<void>;
}

export function CompletionScreen({
  playerName,
  playerImages,
  selectedImageIndex,
  characterSettings,
  isPresetLoaded,
  isGenerating,
  hasBasicInfo,
  showDetails,
  showPresetSheet,
  presetName,
  isSavingPreset,
  presetSaveStatus,
  presetSaveMessage,
  toast,
  isGeneratingImage,
  imageFeedback,
  onImageFeedbackChange,
  onRegenerateImage,
  onRegenerateFreshImage,
  showToast,
  onSetShowDetails,
  onSetShowPresetSheet,
  onSetPresetName,
  onBack,
  onStartGame,
  onSavePreset,
  onRegenerateSetting,
}: CompletionScreenProps) {
  const [isGoingBack, setIsGoingBack] = useState(false);
  const [isRegeneratingFresh, setIsRegeneratingFresh] = useState(false);
  const [isRegeneratingImage, setIsRegeneratingImage] = useState(false);
  const [imageError, setImageError] = useState(false);
  const isImageFeedbackOverLimit = !isWithinInputLimit(
    imageFeedback,
    INPUT_LIMITS.feedback,
  );

  const handleImageError = useCallback(() => {
    setImageError(true);
  }, []);

  const handleBack = async () => {
    setIsGoingBack(true);
    try {
      await onBack();
    } finally {
      setIsGoingBack(false);
    }
  };

  const handleRegenerateFresh = async () => {
    setIsRegeneratingFresh(true);
    try {
      await onRegenerateFreshImage();
    } catch (err) {
      showToast("error", String(err) || "重新生成失败");
    } finally {
      setIsRegeneratingFresh(false);
    }
  };

  const handleRegenerateImage = async () => {
    if (!isWithinInputLimit(imageFeedback, INPUT_LIMITS.feedback)) return;
    setIsRegeneratingImage(true);
    try {
      await onRegenerateImage();
      onImageFeedbackChange("");
    } catch (err) {
      showToast("error", String(err) || "重新生成失败");
    } finally {
      setIsRegeneratingImage(false);
    }
  };

  return (
    <>
      <PageTransition className="min-h-screen bg-[var(--surface-canvas)]">
      <header className="sticky top-0 z-40 border-b border-[var(--border-default)] bg-[var(--surface-canvas)]/95 backdrop-blur-sm">
        <div className="mx-auto flex min-h-16 max-w-3xl items-center gap-2 px-4 sm:gap-4">
          <Button
            variant="quiet"
            size="touch"
            onClick={handleBack}
            disabled={isGoingBack}
            data-testid="back-button"
          >
            {isGoingBack ? (
              <Loader2 className="animate-spin" />
            ) : (
              <ArrowLeft />
            )}
            返回修改
          </Button>
          <div className="hidden min-w-0 flex-1 text-center sm:block">
            <p className="text-sm font-medium text-[var(--text-primary)]">story101</p>
            <p className="text-xs text-[var(--text-secondary)]">角色设定完成</p>
          </div>
          <Button
            variant="quiet"
            size="touch"
            onClick={() => onSetShowPresetSheet(true)}
          >
            <Save />
            快速保存
          </Button>
        </div>
      </header>

      <div className="mx-auto w-full max-w-3xl px-4 py-6 sm:py-10">
        <Surface variant="reading" className="min-w-0 p-5 sm:p-8">
          <section
            className={
              playerImages.length > 0
                ? "grid min-w-0 gap-8 md:grid-cols-[10rem_minmax(0,1fr)] md:items-start"
                : "min-w-0"
            }
          >
            {playerImages.length > 0 && (
              <div className="flex min-w-0 flex-col items-center">
                <>
                  {isGeneratingImage ? (
                    <div className="flex h-48 w-32 items-center justify-center rounded-[var(--radius-surface)] border border-[var(--border-default)] bg-[var(--surface-subtle)]">
                      <Loader2 className="animate-spin text-[var(--text-secondary)]" />
                    </div>
                  ) : !imageError ? (
                    <img
                      src={playerImages[selectedImageIndex]?.image_url || playerImages[0]?.image_url}
                      alt={playerName || "主角"}
                      className="h-48 w-32 rounded-[var(--radius-surface)] border border-[var(--border-default)] object-cover"
                      onError={handleImageError}
                    />
                  ) : (
                    <div className="flex h-48 w-32 flex-col items-center justify-center rounded-[var(--radius-surface)] border border-[var(--border-default)] bg-[var(--surface-subtle)]">
                      <User className="mb-2 text-[var(--text-secondary)]" />
                      <span className="text-xs text-[var(--text-secondary)]">图片加载失败</span>
                    </div>
                  )}
                  <span className="mt-3 break-words text-center text-sm font-medium text-[var(--text-primary)]">
                    {playerName}
                  </span>
                </>
              </div>
            )}

            {playerImages.length === 0 && isGeneratingImage && (
              <div className="flex items-center gap-2 border-l-2 border-[var(--border-interactive)] py-2 pl-3 text-sm text-[var(--text-secondary)]" role="status">
                <Loader2 className="h-4 w-4 animate-spin" />
                人物形象正在后台生成，完成后会自动显示。
              </div>
            )}

            <div className="min-w-0">
              <p className="text-xs text-[var(--text-secondary)]">角色创建</p>
              <h1 className="mt-2 font-serif text-2xl font-semibold text-[var(--text-primary)] sm:text-3xl">
                角色设定完成
              </h1>
              <p className="mt-3 break-words text-sm leading-relaxed text-[var(--text-secondary)]">
                {isPresetLoaded ? "已加载预设角色背景" : "已为你自动生成角色背景"}
              </p>

              {playerImages.length > 0 && !isGeneratingImage && (
                <div className="mt-8 border-t border-[var(--border-default)] pt-6">
                  <FormField
                    id="completion-portrait-feedback"
                    label="人物形象修改意见"
                    description="会保留角色设定，只调整人物形象。"
                    error={isImageFeedbackOverLimit ? `修改意见不能超过 ${INPUT_LIMITS.feedback} 字` : undefined}
                  >
                    {({ describedBy, invalid }) => (
                      <>
                        <Textarea
                          id="completion-portrait-feedback"
                          value={imageFeedback}
                          onChange={(event) => onImageFeedbackChange(event.target.value)}
                          placeholder="描述你想调整的形象细节"
                          surface="underline"
                          controlSize="touch"
                          className="min-h-24 resize-y"
                          aria-describedby={[describedBy, "completion-portrait-feedback-count"].filter(Boolean).join(" ")}
                          aria-invalid={invalid}
                        />
                        <LengthIndicator
                          id="completion-portrait-feedback-count"
                          value={imageFeedback}
                          limit={INPUT_LIMITS.feedback}
                          announce={false}
                        />
                      </>
                    )}
                  </FormField>
                  <div className="mt-4 flex flex-col gap-2 sm:flex-row">
                    <Button
                      variant="narrative"
                      size="touch"
                      className="flex-1"
                      disabled={
                        !imageFeedback.trim() ||
                        isRegeneratingImage ||
                        isImageFeedbackOverLimit
                      }
                      title={!imageFeedback.trim() ? "请先输入修改意见" : undefined}
                      onClick={handleRegenerateImage}
                    >
                      {isRegeneratingImage ? (
                        <Loader2 className="animate-spin" />
                      ) : (
                        <RefreshCw />
                      )}
                      根据意见修改
                    </Button>
                    <Button
                      variant="quiet"
                      size="touch"
                      disabled={isRegeneratingFresh}
                      onClick={handleRegenerateFresh}
                    >
                      {isRegeneratingFresh ? (
                        <Loader2 className="animate-spin" />
                      ) : (
                        <RotateCcw />
                      )}
                      完全重生成
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </section>

          <section className="mt-8 border-t border-[var(--border-default)] pt-6">
            <Button
              variant="quiet"
              size="touch"
              className="w-full justify-between sm:w-auto"
              onClick={() => onSetShowDetails(!showDetails)}
              aria-expanded={showDetails}
            >
              <span className="inline-flex items-center gap-2">
                <Eye />
                查看设定详情
              </span>
              {showDetails ? <ChevronUp /> : <ChevronDown />}
            </Button>

            {showDetails && (
              <div className="mt-4 min-w-0">
                {AUTO_ADVANCE_STEPS.map((step) => {
                  const data = characterSettings[step];
                  if (!data) return null;
                  return (
                    <SettingFeedbackCard
                      key={step}
                      stepKey={step}
                      stepLabel={STEP_LABELS[step]}
                      data={data as Record<string, unknown>}
                      onRegenerate={(feedback) => onRegenerateSetting(step, feedback)}
                    />
                  );
                })}
              </div>
            )}
          </section>

          <div className="mt-8 flex flex-col gap-3 border-t border-[var(--border-default)] pt-6 sm:flex-row">
            <Button
              size="touch"
              className="flex-1"
              onClick={onStartGame}
              disabled={isGenerating || !hasBasicInfo}
            >
              {isGenerating ? <Loader2 className="animate-spin" /> : <Play />}
              {hasBasicInfo ? "开始游戏" : "请先输入角色姓名"}
            </Button>
            <Button
              variant="narrative"
              size="touch"
              className="flex-1"
              onClick={() => onSetShowPresetSheet(true)}
            >
              <Save />
              保存为预设
            </Button>
          </div>
        </Surface>
      </div>

      <PresetSaveSheet
        open={showPresetSheet}
        onOpenChange={onSetShowPresetSheet}
        presetName={presetName}
        onPresetNameChange={onSetPresetName}
        isSaving={isSavingPreset}
        status={presetSaveStatus}
        message={presetSaveMessage}
        onSave={onSavePreset}
      />
      </PageTransition>

      <CreateFeedbackToast
        toast={toast}
        suppressed={showPresetSheet && presetSaveStatus === "error"}
      />
    </>
  );
}
