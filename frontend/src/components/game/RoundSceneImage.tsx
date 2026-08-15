"use client";

import { useEffect, useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2, ImageIcon, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { FormField } from "@/components/story101";
import type { RoundSceneImage } from "@/stores/useGameStore";
import { useGameStore } from "@/stores/useGameStore";
import { useSceneImageStore } from "@/stores/useSceneImageStore";

interface RoundSceneImageProps {
  sceneImage: RoundSceneImage | null;
  isLoading: boolean;
  error?: string | null;
  isRegenerating?: boolean;
  announceError?: boolean;
  currentRound: number;
  label?: string;  // ★ 可选标签：事件场景 | 结果场景
  onRefresh: () => void;
  onRetryGeneration?: () => void;
  onRegenerate?: (roundNumber: number, userPrompt: string) => Promise<void>;
}

export function RoundSceneImageDisplay({
  sceneImage,
  isLoading,
  error,
  isRegenerating = false,
  announceError = true,
  currentRound,
  label,
  onRefresh,
  onRetryGeneration,
  onRegenerate,
}: RoundSceneImageProps) {
  const [imageLoaded, setImageLoaded] = useState(false);
  const [showRegenerateInput, setShowRegenerateInput] = useState(false);
  const [regeneratePrompt, setRegeneratePrompt] = useState("");
  const [retryCount, setRetryCount] = useState(0);  // ★ 重试计数器
  const [imageError, setImageError] = useState(false);  // ★ 图片加载错误
  
  // ★ 从 store 获取设置和方法
  const enableSceneImage = useGameStore((s) => s.enableSceneImage);
  const clearImageCache = useGameStore((s) => s.clearImageCache);
  const invalidateSceneImage = useSceneImageStore((s) => s.invalidateSceneImage);

  // 当场景变化时重置加载状态（包括重新生成）
  useEffect(() => {
    setImageLoaded(false);
    setImageError(false);
    setRetryCount(0);
  }, [sceneImage?.scene_id, sceneImage?.created_at]);  // ★ 也监听 created_at 变化

  // ★ 图片加载失败时的处理
  const handleImageError = useCallback(() => {
    console.warn("[RoundSceneImage] Image load failed:", sceneImage?.image_url);
    setImageError(true);
    setImageLoaded(true);  // 停止加载动画
    
    // ★ 如果是第一次失败，尝试清理该场景缓存并重试（不清空全局图片缓存）
    if (retryCount === 0) {
      console.log("[RoundSceneImage] Invalidating scene cache and retrying...");
      invalidateSceneImage(
        sceneImage?.week ?? 0,
        sceneImage?.round_number ?? currentRound,
        sceneImage?.stage ?? "event",
      );
      setRetryCount(1);
      // 强制刷新图片
      setTimeout(() => {
        onRefresh();
      }, 500);
    }
  }, [retryCount, clearImageCache, onRefresh, sceneImage?.image_url]);

  // 如果禁用自动生成，不显示组件
  if (!enableSceneImage) {
    return null;
  }

  const handleExplicitGenerationRetry = onRetryGeneration || onRefresh;

  if (error && !sceneImage) {
    return (
      <section
        data-slot="round-scene-state"
        role={announceError ? "status" : undefined}
        aria-live={announceError ? "polite" : undefined}
        className="mb-6 border-y border-[var(--border-default)] bg-transparent px-0 py-4 shadow-none"
      >
        <div className="flex flex-col items-center justify-center gap-3 py-6 text-center text-muted-foreground">
          <ImageIcon className="w-8 h-8 opacity-50" />
          <span className="max-w-md text-sm leading-relaxed">{error}</span>
          <Button
            variant="narrative"
            size="touch"
            onClick={handleExplicitGenerationRetry}
            disabled={isLoading}
          >
            <RefreshCw className={cn("w-4 h-4 mr-2", isLoading && "animate-spin")} />
            重试生成场景插画
          </Button>
        </div>
      </section>
    );
  }

  // 加载中状态
  if (isLoading && !sceneImage) {
    return (
      <section
        data-slot="round-scene-state"
        className="mb-6 border-y border-[var(--border-default)] bg-transparent px-0 py-4 shadow-none"
      >
        <div className="flex items-center justify-center gap-2 text-muted-foreground py-8">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span className="text-sm">正在生成场景插画...</span>
        </div>
      </section>
    );
  }

  // 无图片状态
  if (!sceneImage) {
    return (
      <section
        data-slot="round-scene-state"
        className="mb-6 border-y border-[var(--border-default)] bg-transparent px-0 py-4 shadow-none"
      >
        <div className="flex flex-col items-center justify-center gap-3 text-muted-foreground py-6">
          <ImageIcon className="w-8 h-8 opacity-50" />
          {error ? (
            <span className="text-sm text-destructive text-center" role="status" aria-live="polite">
              {error}
            </span>
          ) : (
            <span className="text-sm">暂无场景插画</span>
          )}
          <Button
            variant="narrative"
            size="touch"
            onClick={handleExplicitGenerationRetry}
            disabled={isLoading}
          >
            <RefreshCw className={cn("w-4 h-4 mr-2", isLoading && "animate-spin")} />
            {error ? "重试生成插画" : "生成场景插画"}
          </Button>
        </div>
      </section>
    );
  }

  // 处理重新生成
  const handleRegenerate = async () => {
    if (!onRegenerate || !regeneratePrompt.trim()) return;
    await onRegenerate(currentRound, regeneratePrompt.trim());
    setShowRegenerateInput(false);
    setRegeneratePrompt("");
  };

  return (
    <figure
      data-slot="round-scene-figure"
      className="mb-6 overflow-hidden rounded-none border-y border-[var(--border-default)] bg-transparent shadow-none"
    >
      {/* 图片区域 */}
      <div className="relative aspect-video bg-[var(--surface-subtle)]">
        {!imageLoaded && (
          <div className="absolute inset-0 flex items-center justify-center">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
          </div>
        )}
        <img
          key={`${sceneImage.image_url}-${sceneImage.created_at}-${retryCount}`}
          src={sceneImage.created_at ? `${sceneImage.image_url}${sceneImage.image_url.includes('?') ? '&' : '?'}t=${new Date(sceneImage.created_at).getTime()}` : sceneImage.image_url}
          alt={sceneImage.scene_description}
          className={cn(
            "w-full h-full object-cover transition-opacity duration-300",
            imageLoaded ? "opacity-100" : "opacity-0"
          )}
          onLoad={() => {
            setImageLoaded(true);
            setImageError(false);
          }}
          onError={handleImageError}
        />

        {/* ★ 图片加载错误提示 */}
        {imageError && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-[var(--surface-reading)] gap-2">
            <ImageIcon className="w-8 h-8 text-muted-foreground opacity-50" />
            <span className="text-xs text-muted-foreground">图片加载失败</span>
            <Button
              variant="narrative"
              size="touch"
              onClick={() => {
                clearImageCache();
                onRefresh();
              }}
              disabled={isLoading}
            >
              <RefreshCw className="w-3 h-3 mr-1" />
              重新加载
            </Button>
          </div>
        )}
      </div>

      {/* 描述区域 */}
      <figcaption className="border-t border-[var(--border-default)] py-3">
        <div className="mb-2 flex items-center justify-between gap-4 text-xs text-[var(--text-secondary)]">
          <span>{label || "场景插画"}</span>
          <span>第 {sceneImage.round_number + 1} 轮</span>
        </div>
        <p className="whitespace-normal break-words text-sm text-muted-foreground">
          {sceneImage.scene_description}
        </p>

        {error && (
          <div
            className="mt-3 border-y border-destructive/30 bg-transparent py-3 text-sm text-destructive"
            role={announceError ? "status" : undefined}
            aria-live={announceError ? "polite" : undefined}
          >
            <p>{error}</p>
            <Button
              variant="narrative"
              size="touch"
              className="mt-2"
              onClick={handleExplicitGenerationRetry}
              disabled={isLoading || isRegenerating}
            >
              <RefreshCw className="mr-1 h-3 w-3" />
              重试生成场景插画
            </Button>
          </div>
        )}

        {isLoading && (
          <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2 className="w-3 h-3 animate-spin" />
            <span>正在获取或生成最新场景插画...</span>
          </div>
        )}

        {/* 重新生成输入框 */}
        {showRegenerateInput && (
          <div className="mt-3 space-y-2 border-t border-border/50 pt-3">
            <FormField
              id={`round-scene-regenerate-${sceneImage.scene_id}`}
              label="插画修改要求"
              description="说明想保留和调整的画面内容。"
            >
              {({ describedBy }) => (
                <Input
                  id={`round-scene-regenerate-${sceneImage.scene_id}`}
                  placeholder="例如：让场景更明亮一些，增加更多人物..."
                  value={regeneratePrompt}
                  onChange={(e) => setRegeneratePrompt(e.target.value)}
                  surface="underline"
                  controlSize="touch"
                  className="text-sm"
                  disabled={isRegenerating}
                  aria-describedby={describedBy}
                />
              )}
            </FormField>
            <div className="flex gap-2">
              <Button
                variant="narrative"
                size="touch"
                onClick={handleRegenerate}
                disabled={isRegenerating || !regeneratePrompt.trim()}
              >
                {isRegenerating && <Loader2 className="w-3 h-3 mr-1 animate-spin" />}
                确认生成
              </Button>
              <Button
                variant="quiet"
                size="touch"
                onClick={() => setShowRegenerateInput(false)}
                disabled={isRegenerating}
              >
                取消
              </Button>
            </div>
          </div>
        )}

        {/* 操作按钮 */}
        <div className="mt-3 flex items-center justify-end">
          <div className="flex gap-1">
            {onRegenerate && !showRegenerateInput && (
              <Button
                variant="quiet"
                size="touch"
                onClick={() => setShowRegenerateInput(true)}
                disabled={isLoading || isRegenerating}
              >
                <RefreshCw className="w-3 h-3 mr-1" />
                重新生成插画
              </Button>
            )}
            <Button
              variant="quiet"
              size="touch"
              onClick={handleExplicitGenerationRetry}
              disabled={isLoading || isRegenerating}
            >
              <RefreshCw className={cn("w-3 h-3 mr-1", isLoading && "animate-spin")} />
              刷新
            </Button>
          </div>
        </div>
      </figcaption>
    </figure>
  );
}
