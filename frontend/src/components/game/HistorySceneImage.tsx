"use client";

import { useEffect, useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2, ImageIcon, RefreshCw, Wand2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { FormField } from "@/components/story101";
import type { SceneImageInfo } from "./RoundHistoryDrawer";
import { useGameStore } from "@/stores/useGameStore";

interface HistorySceneImageProps {
  sceneImage: SceneImageInfo | null;
  isLoading: boolean;
  isGenerating?: boolean;
  isRegenerating?: boolean;
  week: number;
  round: number;
  storyText: string;
  onGenerate: (week: number, round: number, storyText: string) => Promise<void>;
  onRegenerate?: (week: number, round: number, storyText: string, userPrompt: string, sceneId: number) => Promise<void>;
}

export function HistorySceneImage({
  sceneImage,
  isLoading,
  isGenerating = false,
  isRegenerating = false,
  week,
  round,
  storyText,
  onGenerate,
  onRegenerate,
}: HistorySceneImageProps) {
  const [imageLoaded, setImageLoaded] = useState(false);
  const [showRegenerateInput, setShowRegenerateInput] = useState(false);
  const [regeneratePrompt, setRegeneratePrompt] = useState("");
  const [retryCount, setRetryCount] = useState(0);
  const [imageError, setImageError] = useState(false);

  const enableSceneImage = useGameStore((s) => s.enableSceneImage);
  const clearImageCache = useGameStore((s) => s.clearImageCache);

  // 当场景变化时重置加载状态
  useEffect(() => {
    setImageLoaded(false);
    setImageError(false);
    setRetryCount(0);
  }, [sceneImage?.scene_id]);

  // 图片加载失败时的处理
  const handleImageError = useCallback(() => {
    console.warn("[HistorySceneImage] Image load failed:", sceneImage?.image_url);
    setImageError(true);
    setImageLoaded(true);

    // 如果是第一次失败，尝试清理缓存并重试
    if (retryCount === 0) {
      console.log("[HistorySceneImage] Clearing cache and retrying...");
      clearImageCache();
      setRetryCount(1);
    }
  }, [retryCount, clearImageCache, sceneImage?.image_url]);

  // 如果禁用自动生成，不显示组件
  if (!enableSceneImage) {
    return null;
  }

  // 生成中状态
  if (isGenerating) {
    return (
      <section
        data-slot="history-scene-state"
        className="mb-6 border-y border-[var(--border-default)] bg-transparent px-0 py-4 shadow-none"
      >
        <div
          className="flex items-center justify-center gap-3 py-8 text-[var(--text-secondary)]"
          role="status"
        >
          <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
          <div className="space-y-1">
            <p className="text-sm">正在绘制历史场景插画</p>
            <p className="text-xs text-[var(--text-secondary)]">
              正在从历史故事中选取一个重要场景
            </p>
          </div>
        </div>
      </section>
    );
  }

  // 加载中状态
  if (isLoading && !sceneImage) {
    return (
      <section
        data-slot="history-scene-state"
        className="mb-6 border-y border-[var(--border-default)] bg-transparent px-0 py-4 shadow-none"
      >
        <div className="flex items-center justify-center gap-2 text-muted-foreground py-8">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span className="text-sm">正在加载场景插画...</span>
        </div>
      </section>
    );
  }

  // 无图片状态 - 显示生成按钮
  if (!sceneImage) {
    return (
      <section
        data-slot="history-scene-state"
        className="mb-6 border-y border-[var(--border-default)] bg-transparent px-0 py-4 shadow-none"
      >
        <div className="flex flex-col items-center justify-center gap-3 text-muted-foreground py-6">
          <ImageIcon className="w-8 h-8 opacity-50" />
          <span className="text-sm">该轮次暂无场景插画</span>
          <Button
            variant="narrative"
            size="touch"
            onClick={() => onGenerate(week, round, storyText)}
            disabled={isLoading || isGenerating}
          >
            <Wand2 className="w-4 h-4 mr-2" />
            生成场景插画
          </Button>
        </div>
      </section>
    );
  }

  // 处理重新生成
  const handleRegenerate = async () => {
    if (!onRegenerate || !regeneratePrompt.trim() || !sceneImage) return;
    await onRegenerate(week, round, storyText, regeneratePrompt.trim(), sceneImage.scene_id);
    setShowRegenerateInput(false);
    setRegeneratePrompt("");
  };

  const weekDisplay = week + 1;
  const roundDisplay = round + 1;

  return (
    <figure
      data-slot="history-scene-figure"
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

        {/* 图片加载错误提示 */}
        {imageError && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-[var(--surface-reading)] gap-2">
            <ImageIcon className="w-8 h-8 text-muted-foreground opacity-50" />
            <span className="text-xs text-muted-foreground">图片加载失败</span>
            <Button
              variant="narrative"
              size="touch"
              onClick={() => {
                clearImageCache();
                setRetryCount((c) => c + 1);
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
          <span>历史场景插画</span>
          <span>第 {weekDisplay} 周 · 第 {roundDisplay} 轮</span>
        </div>
        <p className="whitespace-normal break-words text-sm text-muted-foreground">
          {sceneImage.scene_description}
        </p>

        {/* 重新生成输入框 */}
        {showRegenerateInput && (
          <div className="mt-3 space-y-2 border-t border-border/50 pt-3">
            <FormField
              id={`history-scene-regenerate-${sceneImage.scene_id}`}
              label="插画修改要求"
              description="说明想保留和调整的画面内容。"
            >
              {({ describedBy }) => (
                <Input
                  id={`history-scene-regenerate-${sceneImage.scene_id}`}
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
                修改图片
              </Button>
            )}
          </div>
        </div>
      </figcaption>
    </figure>
  );
}
