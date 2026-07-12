"use client";

import { useEffect, useState, useCallback } from "react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2, ImageIcon, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import type { RoundSceneImage } from "@/stores/useGameStore";
import { useGameStore } from "@/stores/useGameStore";

interface RoundSceneImageProps {
  sceneImage: RoundSceneImage | null;
  isLoading: boolean;
  error?: string | null;
  isRegenerating?: boolean;
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
    
    // ★ 如果是第一次失败，尝试清理缓存并重试
    if (retryCount === 0) {
      console.log("[RoundSceneImage] Clearing cache and retrying...");
      clearImageCache();
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
      <Card className="p-4 mb-4 bg-card/50 border-dashed">
        <div className="flex flex-col items-center justify-center gap-3 py-6 text-center text-muted-foreground">
          <ImageIcon className="w-8 h-8 opacity-50" />
          <span className="max-w-md text-sm leading-relaxed">{error}</span>
          <Button
            variant="outline"
            size="sm"
            onClick={handleExplicitGenerationRetry}
            disabled={isLoading}
          >
            <RefreshCw className={cn("w-4 h-4 mr-2", isLoading && "animate-spin")} />
            重试生成场景插画
          </Button>
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
          <span className="text-sm">正在生成场景插画...</span>
        </div>
      </Card>
    );
  }

  // 无图片状态
  if (!sceneImage) {
    return (
      <Card className="p-4 mb-4 bg-card/50 border-dashed">
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
            variant="outline"
            size="sm"
            onClick={handleExplicitGenerationRetry}
            disabled={isLoading}
          >
            <RefreshCw className={cn("w-4 h-4 mr-2", isLoading && "animate-spin")} />
            {error ? "重试生成插画" : "生成场景插画"}
          </Button>
        </div>
      </Card>
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

        {/* 轮次标签 */}
        <div className="absolute top-2 left-2 px-2 py-1 rounded bg-black/50 text-white text-xs">
          第 {sceneImage.round_number} 轮
        </div>
        
        {/* ★ 图片加载错误提示 */}
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
      <div className="p-3">
        <p className="text-sm text-muted-foreground line-clamp-2">
          {sceneImage.scene_description}
        </p>

        {error && (
          <div className="mt-3 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            <p>{error}</p>
            <Button
              variant="outline"
              size="sm"
              className="mt-2 h-7 text-xs"
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

        {error && !isLoading && (
          <div className="mt-2 text-xs text-destructive" role="status" aria-live="polite">
            {error}
          </div>
        )}

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
            {label || "场景插画"}
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
                重新生成插画
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              className="h-7 text-xs"
              onClick={handleExplicitGenerationRetry}
              disabled={isLoading || isRegenerating}
            >
              <RefreshCw className={cn("w-3 h-3 mr-1", isLoading && "animate-spin")} />
              刷新
            </Button>
          </div>
        </div>
      </div>
    </Card>
  );
}
