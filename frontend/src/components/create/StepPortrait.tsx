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

import type { PortraitCandidateState } from "@/lib/api";

interface StepPortraitProps {
  playerImages: Array<{ image_id: number; image_url: string }>;
  selectedImageIndex?: number;
  selectedImageId?: number | null;
  portraitCandidates?: PortraitCandidateState | null;
  onRetryMissing?: (batchId: number) => Promise<void>;
  isGeneratingImage: boolean;
  imageGenerationError?: string | null;
  playerName: string;
  imageFeedback: string;
  gameId: number | null;
  isBackgroundGenerating: boolean;
  onSelectImage: (imageId: number) => void | Promise<void>;
  onFeedbackChange: (feedback: string) => void;
  onRegenerate: () => Promise<void>;
  onRegenerateFresh: () => Promise<void>;
  onRetryGeneration?: () => Promise<void>;
  onRecover?: () => void;
  showToast: (type: "success" | "error", message: string) => void;
}

export function StepPortrait({
  playerImages,
  selectedImageIndex = 0,
  selectedImageId,
  portraitCandidates,
  onRetryMissing,
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
  const selectedId = selectedImageId === undefined ? playerImages[selectedImageIndex]?.image_id ?? playerImages[0]?.image_id : selectedImageId;
  const playerImage = playerImages.find(image => image.image_id === selectedId) ?? null;
  const [isSelecting, setIsSelecting] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);
  const selectImage = async (imageId: number) => {
    setIsSelecting(true);
    try { await onSelectImage(imageId); }
    catch (error) { showToast("error", error instanceof Error ? error.message : "选择形象失败"); }
    finally { setIsSelecting(false); }
  };
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

  useEffect(() => { setMainImageError(false); }, [playerImage?.image_id]);

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
        {isGeneratingImage && playerImages.length === 0 ? (
          <div className="mx-auto flex aspect-[9/17] w-full max-w-sm items-center justify-center overflow-hidden rounded-[var(--radius-surface)] border border-[var(--border-default)] bg-[var(--surface-subtle)] px-4">
            <div className="flex flex-col items-center gap-2 text-[var(--text-secondary)]">
              <Loader2 className="w-8 h-8 animate-spin" />
              <span className="text-center text-sm">人物形象正在后台生成，你可以先继续创建。</span>
              {isLongRunning && (
                <div className="mt-2 max-w-xs border-l-2 border-[var(--border-interactive)] pl-3 text-left text-xs leading-relaxed">
                  人物形象生成通常需要 1-2 分钟。你可以继续创建，或刷新状态查看是否已经生成完成。
                </div>
              )}
              {isLongRunning && onRecover && (
                <Button type="button" variant="narrative" size="touch" onClick={onRecover}>
                  刷新状态
                </Button>
              )}
            </div>
          </div>
        ) : imageGenerationError && playerImages.length === 0 ? (
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
        ) : playerImage ? (
          <div className="space-y-3">
            <p className="text-center text-sm text-[var(--text-secondary)]">当前使用</p>
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
            {!portraitCandidates && playerImages.length > 1 && (
              <div className="flex gap-2 justify-center">
                {playerImages.map((img, idx) => (
                  <button
                    type="button"
                    key={img.image_id}
                    aria-label={`选择人物形象 ${idx + 1}`}
                    aria-pressed={img.image_id === selectedId}
                    disabled={isSelecting}
                    className={cn(
                      "h-20 w-16 overflow-hidden rounded-[var(--radius-control)] border transition-colors outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50",
                      img.image_id === selectedId
                        ? "border-[var(--border-interactive)] opacity-100"
                        : "border-[var(--border-default)] opacity-70 hover:opacity-100"
                    )}
                    onClick={() => void selectImage(img.image_id)}
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
              {!portraitCandidates && gameId && onRetryGeneration && <Button variant="narrative" size="touch" onClick={async () => {
                try { await onRetryGeneration(); }
                catch (error) { showToast("error", error instanceof Error ? error.message : "人物形象生成失败"); }
              }}>生成三张人物形象</Button>}
            </div>
          </div>
        )}
      </div>

      {portraitCandidates && (
        <div className="space-y-3">
          <p role="status" className="text-sm text-[var(--text-secondary)]">已完成 {portraitCandidates.completed_count}/3</p>
          <div className="grid grid-cols-3 gap-3">
            {[0, 1, 2].map(index => {
              const slot = portraitCandidates.slots.find(slot => slot.slot_index === index);
              const image = playerImages.find(image => image.image_id === slot?.image_id);
              const ready = slot?.status === "ready" && image;
              return (
                <button key={index} type="button" aria-label={`选择人物形象 ${index + 1}`}
                  aria-pressed={!!ready && image.image_id === selectedId}
                  disabled={!ready || isSelecting}
                  onClick={() => { if (ready) void selectImage(image.image_id); }}
                  className={cn("aspect-[9/17] overflow-hidden rounded-[var(--radius-control)] border bg-[var(--surface-subtle)] text-sm focus-visible:ring-2 focus-visible:ring-ring",
                    ready && image.image_id === selectedId ? "border-[var(--border-interactive)]" : "border-[var(--border-default)]")}>
                  {ready ? <img src={image.image_url} alt={`${playerName} - ${index + 1}`} className="h-full w-full object-contain" /> :
                    <span>{slot?.status === "failed" ? "生成失败" : slot?.status === "running" ? "正在生成" : slot?.status === "ready" ? "正在加载" : "等待生成"}</span>}
                </button>
              );
            })}
          </div>
          {!isGeneratingImage && portraitCandidates.completed_count < 3 && onRetryMissing && (
            <Button variant="narrative" size="touch" disabled={isRetrying} onClick={async () => {
              setIsRetrying(true);
              try { await onRetryMissing(portraitCandidates.batch_id); }
              catch (error) { showToast("error", error instanceof Error ? error.message : "重试失败"); }
              finally { setIsRetrying(false); }
            }}>重试未完成的形象</Button>
          )}
          {onRecover && <Button variant="quiet" size="touch" onClick={onRecover}>刷新状态</Button>}
        </div>
      )}

      {playerImages.length > 0 && isGeneratingImage && (
        <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]" role="status">
          <Loader2 className="h-4 w-4 animate-spin" />
          正在后台重新生成人物形象，完成后会自动更新。
        </div>
      )}
      {playerImages.length > 0 && imageGenerationError && !isGeneratingImage && (
        <p className="text-sm text-destructive" role="alert">{imageGenerationError}</p>
      )}
      
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
          
          <p className="text-xs text-[var(--text-secondary)]">生成一组三张新形象，约进行三次图片生成。选中新图后才会切换当前形象。</p>
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
            完全重新生成（三张新形象）
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
