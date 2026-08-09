"use client";

import { useEffect, useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { FormField } from "@/components/story101";
import { cn } from "@/lib/utils";
import { Loader2, RefreshCw, RotateCcw, User } from "lucide-react";
import { LengthIndicator } from "@/components/ui/length-indicator";
import { INPUT_LIMITS } from "@/types/input-limits.generated";
import { isWithinInputLimit } from "@/lib/inputLimits";

interface StepPortraitProps {
  playerImages: Array<{ image_id: number; image_url: string }>;
  selectedImageIndex: number;
  isGeneratingImage: boolean;
  imageGenerationError?: string | null;
  playerName: string;
  imageFeedback: string;
  gameId: number | null;
  isBackgroundGenerating: boolean;
  onSelectImage: (index: number) => void;
  onFeedbackChange: (feedback: string) => void;
  onRegenerate: () => Promise<void>;
  onRegenerateFresh: () => Promise<void>;
  onRetryGeneration?: () => Promise<void>;
  onRecover?: () => void;
  showToast: (type: "success" | "error", message: string) => void;
}

export function StepPortrait({
  playerImages,
  selectedImageIndex,
  isGeneratingImage,
  imageGenerationError,
  playerName,
  imageFeedback,
  gameId,
  isBackgroundGenerating,
  onSelectImage,
  onFeedbackChange,
  onRegenerate,
  onRegenerateFresh,
  onRetryGeneration,
  onRecover,
  showToast,
}: StepPortraitProps) {
  const playerImage = playerImages[selectedImageIndex] || playerImages[0] || null;
  const [mainImageError, setMainImageError] = useState(false);
  const [thumbErrors, setThumbErrors] = useState<Set<number>>(new Set());
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const isLongRunning = isGeneratingImage && elapsedSeconds >= 60;
  const isFeedbackOverLimit = !isWithinInputLimit(
    imageFeedback,
    INPUT_LIMITS.feedback,
  );

  useEffect(() => {
    if (!isGeneratingImage) {
      setElapsedSeconds(0);
      return;
    }

    setElapsedSeconds(0);
    const interval = window.setInterval(() => {
      setElapsedSeconds((seconds) => seconds + 1);
    }, 1000);

    return () => window.clearInterval(interval);
  }, [isGeneratingImage]);

  const handleMainImageError = useCallback(() => {
    setMainImageError(true);
  }, []);

  const handleThumbError = useCallback((imageId: number) => {
    setThumbErrors((prev) => new Set(prev).add(imageId));
  }, []);

  return (
    <div className="space-y-4">
      {/* 图片展示区 */}
      <div className="w-full">
        {isGeneratingImage ? (
          <div className="mx-auto flex aspect-[9/17] w-full max-w-sm items-center justify-center overflow-hidden rounded-[var(--radius-surface)] border border-[var(--border-default)] bg-[var(--surface-subtle)] px-4">
            <div className="flex flex-col items-center gap-2 text-[var(--text-secondary)]">
              <Loader2 className="w-8 h-8 animate-spin" />
              <span className="text-sm">正在生成人物形象...</span>
              {isLongRunning && (
                <div className="mt-2 max-w-xs border-l-2 border-[var(--border-interactive)] pl-3 text-left text-xs leading-relaxed">
                  人物形象生成通常需要 1-2 分钟。你可以继续等待，或刷新状态查看是否已经生成完成。
                </div>
              )}
              {isLongRunning && onRecover && (
                <Button type="button" variant="narrative" size="touch" onClick={onRecover}>
                  刷新状态
                </Button>
              )}
            </div>
          </div>
        ) : imageGenerationError ? (
          <div className="mx-auto flex aspect-[9/17] w-full max-w-sm items-center justify-center overflow-hidden rounded-[var(--radius-surface)] border border-[var(--border-default)] bg-[var(--surface-subtle)] px-5">
            <div className="flex max-w-xs flex-col items-center gap-3 text-center text-[var(--text-secondary)]">
              <User className="h-10 w-10 opacity-60" />
              <p className="text-sm leading-relaxed">{imageGenerationError}</p>
              {onRetryGeneration && (
                <Button
                  type="button"
                  variant="narrative"
                  size="touch"
                  onClick={async () => {
                    try {
                      await onRetryGeneration();
                    } catch (err) {
                      console.error("[portrait] Failed to retry generation:", err);
                      showToast("error", err instanceof Error ? err.message : "人物形象生成失败");
                    }
                  }}
                >
                  <RefreshCw className="mr-2 h-4 w-4" />
                  重试生成人物形象
                </Button>
              )}
            </div>
          </div>
        ) : playerImages.length > 0 ? (
          <div className="space-y-3">
            {/* 主图展示 */}
            <div className="mx-auto flex aspect-[9/17] w-full max-w-sm items-center justify-center overflow-hidden rounded-[var(--radius-surface)] border border-[var(--border-default)] bg-[var(--surface-subtle)]">
              {!mainImageError ? (
                <img
                  src={playerImage?.image_url}
                  alt={playerName}
                  className="w-full h-full object-contain"
                  onError={handleMainImageError}
                />
              ) : (
                <div className="flex flex-col items-center gap-2 text-muted-foreground">
                  <User className="w-12 h-12" />
                  <span className="text-sm">图片加载失败</span>
                </div>
              )}
            </div>
            
            {/* 缩略图选择 */}
            {playerImages.length > 1 && (
              <div className="flex gap-2 justify-center">
                {playerImages.map((img, idx) => (
                  <button
                    type="button"
                    key={img.image_id}
                    aria-label={`选择人物形象 ${idx + 1}`}
                    aria-pressed={idx === selectedImageIndex}
                    className={cn(
                      "h-20 w-16 overflow-hidden rounded-[var(--radius-control)] border transition-colors outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
                      idx === selectedImageIndex
                        ? "border-[var(--border-interactive)] opacity-100"
                        : "border-[var(--border-default)] opacity-70 hover:opacity-100"
                    )}
                    onClick={() => onSelectImage(idx)}
                  >
                    {!thumbErrors.has(img.image_id) ? (
                      <img
                        src={img.image_url}
                        alt={`${playerName} - ${idx + 1}`}
                        className="w-full h-full object-contain"
                        onError={() => handleThumbError(img.image_id)}
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center bg-muted">
                        <User className="w-6 h-6 text-muted-foreground" />
                      </div>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="mx-auto flex aspect-[9/17] w-full max-w-sm items-center justify-center overflow-hidden rounded-[var(--radius-surface)] border border-[var(--border-default)] bg-[var(--surface-subtle)]">
            <div className="p-4 text-center text-[var(--text-secondary)]">
              <Loader2 className="w-6 h-6 mx-auto mb-2 animate-spin" />
              <p className="text-sm">正在准备生成...</p>
            </div>
          </div>
        )}
      </div>
      
      {/* 后台生成进度提示 */}
      {isBackgroundGenerating && playerImages.length > 0 && (
        <div className="flex items-center gap-2 border-l-2 border-[var(--border-default)] px-3 py-2 text-sm text-[var(--text-secondary)]">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span>后台正在生成家庭背景、人际关系等设定...</span>
        </div>
      )}
      
      {/* 修改意见输入 */}
      {playerImages.length > 0 && !isGeneratingImage && (
        <div className="grid gap-3 border-t border-[var(--border-default)] pt-5">
          <FormField
            id="portrait-feedback"
            label="人物形象修改意见"
            description="会保留现有角色设定，只调整人物形象。"
            error={isFeedbackOverLimit ? `修改意见不能超过 ${INPUT_LIMITS.feedback} 字` : undefined}
          >
            {({ describedBy, invalid }) => (
              <>
                <Textarea
                  id="portrait-feedback"
                  value={imageFeedback}
                  onChange={(e) => onFeedbackChange(e.target.value)}
                  placeholder="不满意？描述你想要的修改...（会保留之前的角色设定）"
                  surface="underline"
                  controlSize="touch"
                  className="min-h-24 resize-y"
                  aria-describedby={[describedBy, "portrait-feedback-count"].filter(Boolean).join(" ")}
                  aria-invalid={invalid}
                />
                <LengthIndicator
                  id="portrait-feedback-count"
                  value={imageFeedback}
                  limit={INPUT_LIMITS.feedback}
                  announce={false}
                />
              </>
            )}
          </FormField>
          <Button
            variant="narrative"
            size="touch"
            className="w-full"
            onClick={async () => {
              if (
                imageFeedback.trim() &&
                !isFeedbackOverLimit
              ) {
                try {
                  await onRegenerate();
                  onFeedbackChange("");
                } catch (err) {
                  console.error("[portrait] Failed to regenerate:", err);
                  showToast("error", String(err) || "重新生成失败");
                }
              }
            }}
            disabled={
              !imageFeedback.trim() ||
              isFeedbackOverLimit
            }
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            根据修改意见重新生成
          </Button>
          
          {/* 完全重新生成按钮 */}
          <Button
            variant="quiet"
            size="touch"
            className="w-full"
            onClick={async () => {
              try {
                await onRegenerateFresh();
              } catch (err) {
                console.error("[portrait] Failed to fresh regenerate:", err);
                showToast("error", String(err) || "完全重新生成失败");
              }
            }}
            disabled={isGeneratingImage}
          >
            <RotateCcw className="w-4 h-4 mr-2" />
            完全重新生成（抛弃历史修改）
          </Button>
        </div>
      )}
      
      {/* 等待 gameId */}
      {playerImages.length === 0 && !isGeneratingImage && !gameId && (
        <div className="flex flex-col items-center gap-2 text-muted-foreground py-4">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span className="text-sm">正在准备...</span>
        </div>
      )}
    </div>
  );
}
