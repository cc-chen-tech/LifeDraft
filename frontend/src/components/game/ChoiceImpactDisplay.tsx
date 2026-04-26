"use client";

import { memo } from "react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { Zap, Heart, BookOpen, Coins, ArrowUp, ArrowDown } from "lucide-react";

interface ChoiceImpactDisplayProps {
  effects: Record<string, number> | null;
  className?: string;
  currencyName?: string;
}

interface ResourceDef {
  key: string;
  name: string;
  icon: React.ReactNode;
  color: string;
}

const RESOURCE_MAP: ResourceDef[] = [
  { key: "energy", name: "精力", icon: <Zap className="w-4 h-4" />, color: "text-emerald-500" },
  { key: "mood", name: "情绪", icon: <Heart className="w-4 h-4" />, color: "text-sky-500" },
  { key: "knowledge", name: "学识", icon: <BookOpen className="w-4 h-4" />, color: "text-violet-500" },
  { key: "wealth", name: "财富", icon: <Coins className="w-4 h-4" />, color: "text-amber-500" },
];

export const ChoiceImpactDisplay = memo(function ChoiceImpactDisplay({
  effects,
  className,
  currencyName = "货币",
}: ChoiceImpactDisplayProps) {
  if (!effects || Object.keys(effects).length === 0) return null;

  const entries = Object.entries(effects).filter(([, val]) => val !== 0);
  if (entries.length === 0) return null;

  return (
    <Card
      data-testid="choice-impact"
      className={cn("p-4 border-primary/20 bg-primary/5", className)}
    >
      <h4 className="text-sm font-medium text-primary mb-3">选择影响</h4>
      <div className="flex flex-wrap gap-3">
        {RESOURCE_MAP.map((res) => {
          const value = effects[res.key];
          if (value === undefined || value === 0) return null;
          const isPositive = value > 0;
          return (
            <div
              key={res.key}
              className={cn(
                "flex items-center gap-1.5 px-2.5 py-1 rounded-full text-sm font-medium",
                isPositive
                  ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                  : "bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300"
              )}
            >
              <span className={res.color}>{res.icon}</span>
              <span>{res.name}</span>
              {isPositive ? (
                <ArrowUp className="w-3 h-3" />
              ) : (
                <ArrowDown className="w-3 h-3" />
              )}
              <span>
                {res.key === "wealth"
                  ? `${Math.abs(value).toLocaleString()}${currencyName}`
                  : Math.abs(value)}
              </span>
            </div>
          );
        })}
      </div>
    </Card>
  );
});

ChoiceImpactDisplay.displayName = "ChoiceImpactDisplay";
