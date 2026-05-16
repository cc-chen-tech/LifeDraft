"use client";

import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";

interface AchievementBadgeProps {
  id: string;
  name: string;
  description: string;
  rarity: "common" | "rare" | "epic" | "legendary";
  unlockedAtWeek?: number;
  animate?: boolean;
  delay?: number;
}

const rarityConfig = {
  common: {
    bg: "bg-slate-100 dark:bg-slate-800",
    border: "border-slate-300 dark:border-slate-600",
    text: "text-slate-700 dark:text-slate-300",
    glow: "",
    label: "普通",
  },
  rare: {
    bg: "bg-sky-50 dark:bg-sky-950",
    border: "border-sky-300 dark:border-sky-700",
    text: "text-sky-700 dark:text-sky-300",
    glow: "shadow-sky-200 dark:shadow-sky-900",
    label: "稀有",
  },
  epic: {
    bg: "bg-violet-50 dark:bg-violet-950",
    border: "border-violet-300 dark:border-violet-700",
    text: "text-violet-700 dark:text-violet-300",
    glow: "shadow-violet-200 dark:shadow-violet-900 shadow-lg",
    label: "史诗",
  },
  legendary: {
    bg: "bg-amber-50 dark:bg-amber-950",
    border: "border-amber-300 dark:border-amber-600",
    text: "text-amber-700 dark:text-amber-300",
    glow: "shadow-amber-200 dark:shadow-amber-900 shadow-xl",
    label: "传说",
  },
};

export function AchievementBadge({
  name,
  description,
  rarity,
  unlockedAtWeek,
  animate = true,
  delay = 0,
}: AchievementBadgeProps) {
  const [visible, setVisible] = useState(!animate);
  const config = rarityConfig[rarity];

  useEffect(() => {
    if (animate) {
      const timer = setTimeout(() => setVisible(true), delay);
      return () => clearTimeout(timer);
    }
  }, [animate, delay]);

  return (
    <div
      data-testid="achievement-badge"
      className={cn(
        "relative rounded-lg border-2 p-3 transition-all duration-500",
        config.bg,
        config.border,
        config.glow,
        visible
          ? "opacity-100 translate-y-0 scale-100"
          : "opacity-0 translate-y-4 scale-90"
      )}
    >
      <div className="flex items-start gap-2">
        <span className={cn("text-xl", config.text)}>
          {rarity === "legendary"
            ? "👑"
            : rarity === "epic"
              ? "💎"
              : rarity === "rare"
                ? "⭐"
                : "🔹"}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={cn("font-semibold text-sm", config.text)}>
              {name}
            </span>
            <span
              className={cn(
                "text-xs px-1.5 py-0.5 rounded-full border",
                config.border,
                config.text
              )}
            >
              {config.label}
            </span>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
          {unlockedAtWeek !== undefined && (
            <p className="text-xs text-muted-foreground/70 mt-1">
              第 {unlockedAtWeek} 周解锁
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
