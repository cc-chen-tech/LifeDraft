"use client";

import { useEffect, useState, useCallback } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2, ImageIcon, RefreshCw, Wand2 } from "lucide-react";
import { cn } from "@/lib/utils";
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
      <Card className="p-4 mb-4 bg-card/50 border-dashed">
        <div className="flex flex-col items-center justify-center gap-3 text-muted-foreground py-8">
          <div className="relative">
            <div className="w-12 h-12 rounded-full border-4 border-primary/20 border-t-primary animate-spin" />
            <Wand2 className="absolute inset-0 m-auto w-5 h-5 text-primary" />
          </div>
          <div className="text-center space-y-1">
            <p className="text-sm animate-pulse">AI正在为你绘制场景插画...</p>
            <p className="text-xs text-muted-foreground/60">
              从历史故事中选择一个重要场景进行创作
            </p>
          </div>
        </div>
      </Card>
    );
  }

  // 加载中状态
  if (isLoading && !sceneImage) {
    return (
      <Card className="p-4 mb-4 bg-card/50 border-dashed">
        <div className="flex items-center justify-center gap-2 text-muted-foreground py-8">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span className="text-sm">正在加载场景插画...</span>
        </div>
      </Card>
    );
  }

  // 无图片状态 - 显示生成按钮
  if (!sceneImage) {
    return (
      <Card className="p-4 mb-4 bg-card/50 border-dashed">
        <div className="flex flex-col items-center justify-center gap-3 text-muted-foreground py-6">
          <ImageIcon className="w-8 h-8 opacity-50" />
          <span className="text-sm">该轮次暂无场景插画</span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onGenerate(week, round, storyText)}
            disabled={isLoading || isGenerating}
          >
            <Wand2 className="w-4 h-4 mr-2" />
            生成场景插画
          </Button>
        </div>
      </Card>
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
    <Card className="mb-4 overflow-hidden bg-card/50">
      {/* 图片区域 */}
      <div className="relative aspect-video bg-muted">
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

        {/* 周/轮次标签 */}
        <div className="absolute top-2 left-2 px-2 py-1 rounded bg-black/50 text-white text-xs">
          第 {weekDisplay} 周 · 第 {roundDisplay} 轮
        </div>

        {/* 图片加载错误提示 */}
        {imageError && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-muted/90 gap-2">
            <ImageIcon className="w-8 h-8 text-muted-foreground opacity-50" />
            <span className="text-xs text-muted-foreground">图片加载失败</span>
            <Button
              variant="outline"
              size="sm"
              className="h-7 text-xs"
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
      <div className="p-3">
        <p className="text-sm text-muted-foreground line-clamp-2">
          {sceneImage.scene_description}
        </p>

        {/* 重新生成输入框 */}
        {showRegenerateInput && (
          <div className="mt-3 pt-3 border-t border-border/50 space-y-2">
            <p className="text-xs text-muted-foreground">描述你想要的修改：</p>
            <Input
              placeholder="例如：让场景更明亮一些，增加更多人物..."
              value={regeneratePrompt}
              onChange={(e) => setRegeneratePrompt(e.target.value)}
              className="text-sm h-8"
              disabled={isRegenerating}
            />
            <div className="flex gap-2">
              <Button
                size="sm"
                className="h-7 text-xs"
                onClick={handleRegenerate}
                disabled={isRegenerating || !regeneratePrompt.trim()}
              >
                {isRegenerating && <Loader2 className="w-3 h-3 mr-1 animate-spin" />}
                确认生成
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-7 text-xs"
                onClick={() => setShowRegenerateInput(false)}
                disabled={isRegenerating}
              >
                取消
              </Button>
            </div>
          </div>
        )}

        {/* 操作按钮 */}
        <div className="mt-3 flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            历史场景插画
          </span>
          <div className="flex gap-1">
            {onRegenerate && !showRegenerateInput && (
              <Button
                variant="ghost"
                size="sm"
                className="h-7 text-xs"
                onClick={() => setShowRegenerateInput(true)}
                disabled={isLoading || isRegenerating}
              >
                <RefreshCw className="w-3 h-3 mr-1" />
                修改图片
              </Button>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}
