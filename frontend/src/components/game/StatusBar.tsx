"use client";

import { memo } from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { TrendingUp } from "lucide-react";

interface StatusBarProps {
  playerState: Record<string, unknown> | null;
  progress: Record<string, unknown> | null;
  className?: string;
  compact?: boolean;
}

/**
 * StatusBar — 游戏进度展示
 * - 紧凑模式用于游戏主页顶部
 * - 完整模式用于侧边栏
 */
export const StatusBar = memo(function StatusBar({
  playerState,
  progress,
  className,
  compact = true,
}: StatusBarProps) {
  if (!playerState) return null;

  const age = (playerState.age as number) || 0;
  const week = ((playerState.week as number) || 0) + 1; // ★ week 从0开始，显示时+1
  const currentRound = progress ? Number(progress.current_round) || 0 : 0;
  const totalRounds = progress ? Number(progress.total_rounds) || 1 : 1;
  const hasProgress = !!progress && currentRound > 0;

  if (compact) {
    return (
      <div data-testid="status-bar" className={cn("flex items-center gap-2 flex-wrap", className)}>
        <Badge variant="secondary" className="text-xs">
          {age}岁 第{week}周
        </Badge>
        {hasProgress && (
          <Badge variant="outline" className="text-xs">
            <TrendingUp className="w-3 h-3 mr-1" />
            {currentRound}/{totalRounds}
          </Badge>
        )}
      </div>
    );
  }

  // Full mode
  return (
    <div data-testid="status-bar" className={cn("space-y-3", className)}>
      <div className="flex justify-between text-sm text-muted-foreground">
        <span>
          {age}岁 第{week}周
        </span>
        {hasProgress && (
          <span>
            进度 {currentRound}/{totalRounds}
          </span>
        )}
      </div>

      {/* Progress bar */}
      {hasProgress && (
        <div className="w-full h-1.5 bg-secondary rounded-full overflow-hidden">
          <div
            className="h-full bg-primary rounded-full transition-all duration-500"
            style={{
              width: `${(currentRound / totalRounds) * 100}%`,
            }}
          />
        </div>
      )}
    </div>
  );
});

StatusBar.displayName = "StatusBar";
