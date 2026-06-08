"use client";

import { memo } from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { Heart, Brain, BookOpen, Coins, TrendingUp, Zap } from "lucide-react";

interface StatusBarProps {
  playerState: Record<string, unknown> | null;
  progress: Record<string, unknown> | null;
  className?: string;
  compact?: boolean;
}

interface ResourceDef {
  key: string;
  name: string;
  icon: React.ReactNode;
  max: number;
}

const RESOURCES: ResourceDef[] = [
  { key: "energy", name: "精力", icon: <Zap className="w-3 h-3" />, max: 100 },
  { key: "mood", name: "情绪", icon: <Heart className="w-3 h-3" />, max: 100 },
  { key: "knowledge", name: "学识", icon: <BookOpen className="w-3 h-3" />, max: 100 },
  { key: "wealth", name: "财富", icon: <Coins className="w-3 h-3" />, max: 100000 },
];

function getAttributeColor(value: number, maxValue: number): string {
  const ratio = value / maxValue;
  if (ratio > 0.7) return "text-success";
  if (ratio > 0.3) return "text-warning";
  return "text-destructive";
}

function getResourceValue(playerState: Record<string, unknown>, key: string): number | null {
  const val = playerState[key];
  if (typeof val === "number") return val;
  return null;
}

function formatWealth(value: number, wealthSettings: Record<string, unknown> | undefined): string {
  const amount = value.toLocaleString();
  const currencySymbol = typeof wealthSettings?.currency === "string"
    ? wealthSettings.currency.trim()
    : "";
  if (currencySymbol) {
    return `${currencySymbol}${amount}`;
  }

  const currencyName = typeof wealthSettings?.currency_name === "string"
    ? wealthSettings.currency_name.trim()
    : "";
  return currencyName ? `${amount}${currencyName}` : `${amount}货币`;
}

/**
 * StatusBar — 游戏进度 & 4D 资源展示
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

  // ★ 从 character_settings 提取动态货币单位
  const characterSettings = playerState.character_settings as Record<string, unknown> | undefined;
  const wealthSettings = characterSettings?.wealth as Record<string, unknown> | undefined;

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
        {RESOURCES.map((res) => {
          const value = getResourceValue(playerState, res.key);
          if (value === null) return null;
          const displayValue = res.key === "wealth" ? formatWealth(value, wealthSettings) : value;
          return (
            <Badge
              key={res.key}
              variant="outline"
              className={cn("text-xs", getAttributeColor(value, res.max))}
            >
              {res.icon}
              <span className="ml-1">
                {res.name}: {displayValue}
              </span>
            </Badge>
          );
        })}
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

      {/* 4D Resources */}
      <div className="space-y-2">
        {RESOURCES.map((res) => {
          const value = getResourceValue(playerState, res.key);
          if (value === null) return null;
          const ratio = Math.min(value / res.max, 1);
          const displayValue = res.key === "wealth" ? formatWealth(value, wealthSettings) : value;
          return (
            <div key={res.key} className="flex items-center gap-2">
              <span className="text-muted-foreground w-4">{res.icon}</span>
              <span className="text-xs text-muted-foreground w-12 truncate">{res.name}</span>
              <div className="flex-1 h-1.5 bg-secondary rounded-full overflow-hidden">
                <div
                  className={cn(
                    "h-full rounded-full transition-all duration-500",
                    ratio > 0.7 ? "bg-success" : ratio > 0.3 ? "bg-warning" : "bg-destructive"
                  )}
                  style={{
                    width: `${ratio * 100}%`,
                  }}
                />
              </div>
              <span
                className={cn(
                  "text-xs font-mono w-10 text-right",
                  getAttributeColor(value, res.max)
                )}
              >
                {displayValue}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
});

StatusBar.displayName = "StatusBar";
