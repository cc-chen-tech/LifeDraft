"use client";

import { cn } from "@/lib/utils";

interface AchievementBadgeProps {
  id: string;
  name: string;
  description: string;
  rarity: "common" | "rare" | "epic" | "legendary";
  unlockedAtWeek?: number;
}

const rarityConfig = {
  common: {
    text: "text-[var(--text-secondary)]",
    label: "普通",
  },
  rare: {
    text: "text-[var(--info-foreground)]",
    label: "稀有",
  },
  epic: {
    text: "text-[var(--warning-foreground)]",
    label: "史诗",
  },
  legendary: {
    text: "text-[var(--warning-foreground)]",
    label: "传说",
  },
};

export function AchievementBadge({
  name,
  description,
  rarity,
  unlockedAtWeek,
}: AchievementBadgeProps) {
  const config = rarityConfig[rarity];

  return (
    <div
      data-testid="achievement-badge"
      data-rarity={rarity}
      className="relative min-w-0 border-l-2 border-[var(--border-default)] py-3 pl-3"
    >
      <div className="flex min-w-0 items-start gap-3">
        <span
          aria-hidden="true"
          className={cn("mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-current", config.text)}
        />
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <span className="min-w-0 break-words text-sm font-semibold text-[var(--text-primary)]">
              {name}
            </span>
            <span
              className={cn(
                "shrink-0 rounded-[var(--radius-pill)] border border-[var(--border-default)] px-2 py-0.5 text-xs",
                config.text
              )}
            >
              {config.label}
            </span>
          </div>
          {description.trim().length > 0 && (
            <p className="mt-1 break-words text-xs leading-5 text-[var(--text-secondary)]">
              {description}
            </p>
          )}
          {unlockedAtWeek !== undefined && (
            <p className="mt-1 text-xs leading-5 text-[var(--text-subtle)]">
              第 {unlockedAtWeek} 周解锁
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
