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
  /** 生成阶段提示 */
  phase?: string;
}

/**
 * SkeletonStory — 故事加载骨架屏
 * - Shimmer 动画
 * - 居中显示加载提示（动态状态）
 * - 显示等待时间
 * - 动态生成阶段提示
 */
export const SkeletonStory = memo(function SkeletonStory({
  className,
  message = "正在构思故事...",
  elapsedSeconds,
  phase,
}: SkeletonStoryProps) {
  // 格式化时间
  const formatTime = (seconds: number) => {
    if (seconds < 60) return `${seconds}秒`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}分${secs}秒`;
  };

  // 动态提示语，缓解等待焦虑
  const getTip = (seconds: number) => {
    if (seconds < 5) return "AI 正在分析你的选择...";
    if (seconds < 10) return "正在构建故事场景...";
    if (seconds < 20) return "正在为角色赋予情感...";
    if (seconds < 40) return "故事分支生成中，精彩即将呈现...";
    return "复杂情节推演中，请稍候...";
  };

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center space-y-6 py-12",
        className
      )}
    >
      <div className="flex flex-col items-center gap-3">
        {/* 主加载动画 */}
        <div className="relative w-12 h-12">
          <Loader2 className="w-12 h-12 animate-spin text-primary/60" />
        </div>

        {/* 主状态消息 */}
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="animate-pulse font-medium">{message}</span>
        </div>

        {/* 阶段提示 */}
        {phase && (
          <div className="text-xs text-primary/70 bg-primary/5 px-3 py-1 rounded-full">
            {phase}
          </div>
        )}

        {/* 动态提示语 */}
        {elapsedSeconds !== undefined && elapsedSeconds > 3 && (
          <div className="text-xs text-muted-foreground/60 max-w-xs text-center leading-relaxed">
            {getTip(elapsedSeconds)}
          </div>
        )}

        {/* 已等待时间 */}
        {elapsedSeconds !== undefined && elapsedSeconds > 0 && (
          <div className="text-xs text-muted-foreground/40 tabular-nums">
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
