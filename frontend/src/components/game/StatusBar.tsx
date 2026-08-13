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
  appearance?: "badges" | "narrative";
}

const ROUND_NAMES = ["周一", "周中", "周末"];

function getNonNegativeInteger(value: unknown, fallback = 0): number {
  const numberValue = Number(value);
  return Number.isInteger(numberValue) && numberValue >= 0
    ? numberValue
    : fallback;
}

function getCompletedViewPosition(playerState: Record<string, unknown>) {
  const resumeView = playerState.resume_view;
  if (!resumeView || typeof resumeView !== "object") return null;

  const { phase, completed_week: completedWeek, completed_round: completedRound } = resumeView as Record<string, unknown>;
  if (
    !["result", "summary", "ending"].includes(String(phase)) ||
    !Number.isInteger(Number(completedWeek)) ||
    !Number.isInteger(Number(completedRound)) ||
    Number(completedWeek) < 0 ||
    Number(completedRound) < 0
  ) {
    return null;
  }

  return {
    week: Number(completedWeek),
    round: Number(completedRound),
  };
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
  appearance = "badges",
}: StatusBarProps) {
  if (!playerState) return null;

  const age = getNonNegativeInteger(playerState.age);
  const completedViewPosition = getCompletedViewPosition(playerState);
  const currentWeek = completedViewPosition?.week ?? getNonNegativeInteger(playerState.week);
  const currentRound = completedViewPosition?.round ?? getNonNegativeInteger(playerState.current_round);
  const totalRounds = getNonNegativeInteger(playerState.rounds_per_week);
  const hasRoundProgress = totalRounds > 0;
  const week = currentWeek + 1;
  const roundLabel = `第${currentRound + 1}轮/${totalRounds}`;

  if (compact) {
    if (appearance === "narrative") {
      const roundName = ROUND_NAMES[currentRound] ?? `第${currentRound + 1}轮`;

      return (
        <div
          data-testid="status-bar"
          data-appearance="narrative"
          className={cn("flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-1", className)}
        >
          <p className="text-sm font-medium text-[var(--text-primary)]">
            {age}岁 · 第{week}周
          </p>
          {hasRoundProgress && (
            <p className="text-xs text-[var(--text-secondary)]">
              {roundName} · {roundLabel}
            </p>
          )}
        </div>
      );
    }

    return (
      <div data-testid="status-bar" data-appearance="badges" className={cn("flex items-center gap-2 flex-wrap", className)}>
        <Badge variant="secondary" className="text-xs">
          {age}岁 第{week}周
        </Badge>
        {hasRoundProgress && (
          <Badge variant="outline" className="text-xs">
            <TrendingUp className="w-3 h-3 mr-1" />
            {roundLabel}
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
        {hasRoundProgress && (
          <span>
            进度 {roundLabel}
          </span>
        )}
      </div>

      {/* Progress bar */}
      {hasRoundProgress && (
        <div className="w-full h-1.5 bg-secondary rounded-full overflow-hidden">
          <div
            className="h-full bg-primary rounded-full transition-all duration-500"
            style={{
              width: `${((currentRound + 1) / totalRounds) * 100}%`,
            }}
          />
        </div>
      )}
    </div>
  );
});

StatusBar.displayName = "StatusBar";
