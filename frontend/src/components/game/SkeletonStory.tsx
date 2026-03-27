"use client";

import { memo } from "react";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { Loader2 } from "lucide-react";

interface SkeletonStoryProps {
  className?: string;
  message?: string;
  /** 已等待的秒数 */
  elapsedSeconds?: number;
}

/**
 * SkeletonStory — 故事加载骨架屏
 * - Shimmer 动画
 * - 居中显示加载提示（动态状态）
 * - 显示等待时间
 */
export const SkeletonStory = memo(function SkeletonStory({
  className,
  message = "正在构思故事...",
  elapsedSeconds,
}: SkeletonStoryProps) {
  // 格式化时间
  const formatTime = (seconds: number) => {
    if (seconds < 60) return `${seconds}秒`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}分${secs}秒`;
  };

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center space-y-6 py-12",
        className
      )}
    >
      <div className="flex flex-col items-center gap-2">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="w-4 h-4 animate-spin" />
          <span className="animate-pulse">{message}</span>
        </div>
        {elapsedSeconds !== undefined && elapsedSeconds > 0 && (
          <div className="text-xs text-muted-foreground/60">
            已等待 {formatTime(elapsedSeconds)}
          </div>
        )}
      </div>

      <div className="w-full space-y-4 px-4">
        <Skeleton className="h-4 w-full skeleton-shimmer" />
        <Skeleton className="h-4 w-[92%] skeleton-shimmer" />
        <Skeleton className="h-4 w-[85%] skeleton-shimmer" />
        <div className="h-4" />
        <Skeleton className="h-4 w-full skeleton-shimmer" />
        <Skeleton className="h-4 w-[88%] skeleton-shimmer" />
        <Skeleton className="h-4 w-[60%] skeleton-shimmer" />
      </div>
    </div>
  );
});

SkeletonStory.displayName = 'SkeletonStory';
