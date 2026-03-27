"use client";

import { memo } from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { Heart, Brain, Coins, Users, TrendingUp } from "lucide-react";

interface StatusBarProps {
  playerState: Record<string, unknown> | null;
  progress: Record<string, unknown> | null;
  className?: string;
  compact?: boolean;
}

function getIcon(key: string) {
  switch (key) {
    case "health":
      return <Heart className="w-3 h-3" />;
    case "intelligence":
      return <Brain className="w-3 h-3" />;
    case "charisma":
      return <Users className="w-3 h-3" />;
    case "wealth":
      return <Coins className="w-3 h-3" />;
    default:
      return <TrendingUp className="w-3 h-3" />;
  }
}

function getAttributeColor(value: number, maxValue: number): string {
  const ratio = value / maxValue;
  if (ratio > 0.7) return "text-success";
  if (ratio > 0.3) return "text-warning";
  return "text-destructive";
}

/**
 * StatusBar — 游戏进度 & 属性展示
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

  const attributes = (playerState.attributes || {}) as Record<
    string,
    { name: string; value: number; max_value: number }
  >;
  const age = (playerState.age as number) || 0;
  const week = ((playerState.week as number) || 0) + 1;  // ★ week 从0开始，显示时+1
  const currentRound = progress
    ? Number(progress.current_round) || 0
    : 0;
  const totalRounds = progress
    ? Number(progress.total_rounds) || 1
    : 1;
  const hasProgress = !!progress && currentRound > 0;
  const wealthLevel = playerState.wealth_level ? String(playerState.wealth_level) : null;

  if (compact) {
    return (
      <div className={cn("flex items-center gap-2 flex-wrap", className)}>
        <Badge variant="secondary" className="text-xs">
          {age}岁 第{week}周
        </Badge>
        {hasProgress && (
          <Badge variant="outline" className="text-xs">
            <TrendingUp className="w-3 h-3 mr-1" />
            {currentRound}/{totalRounds}
          </Badge>
        )}
        {Object.entries(attributes)
          .slice(0, 4)
          .map(([key, attr]) => (
            <Badge
              key={key}
              variant="outline"
              className={cn(
                "text-xs",
                getAttributeColor(attr.value, attr.max_value)
              )}
            >
              {getIcon(key)}
              <span className="ml-1">
                {attr.name}: {attr.value}
              </span>
            </Badge>
          ))}
      </div>
    );
  }

  // Full mode
  return (
    <div className={cn("space-y-3", className)}>
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

      {/* Attributes */}
      <div className="space-y-2">
        {Object.entries(attributes).map(([key, attr]) => (
          <div key={key} className="flex items-center gap-2">
            <span className="text-muted-foreground w-4">
              {getIcon(key)}
            </span>
            <span className="text-xs text-muted-foreground w-16 truncate">
              {attr.name}
            </span>
            <div className="flex-1 h-1.5 bg-secondary rounded-full overflow-hidden">
              <div
                className={cn(
                  "h-full rounded-full transition-all duration-500",
                  attr.value / attr.max_value > 0.7
                    ? "bg-success"
                    : attr.value / attr.max_value > 0.3
                    ? "bg-warning"
                    : "bg-destructive"
                )}
                style={{
                  width: `${(attr.value / attr.max_value) * 100}%`,
                }}
              />
            </div>
            <span
              className={cn(
                "text-xs font-mono w-8 text-right",
                getAttributeColor(attr.value, attr.max_value)
              )}
            >
              {attr.value}
            </span>
          </div>
        ))}
      </div>

      {/* Wealth */}
      {wealthLevel && (
        <div className="flex items-center gap-2 text-sm">
          <Coins className="w-3 h-3 text-warning" />
          <span className="text-muted-foreground">
            财富: {wealthLevel}
          </span>
        </div>
      )}
    </div>
  );
});

StatusBar.displayName = 'StatusBar';
