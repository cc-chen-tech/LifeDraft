"use client";

import { memo } from "react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { ArrowDown, ArrowUp } from "lucide-react";

interface ChoiceImpactDisplayProps {
  effects: Record<string, number> | null;
  className?: string;
  currencyName?: string;
}

const HIDDEN_RESOURCE_KEYS = new Set(["energy", "mood", "knowledge", "wealth"]);

export const ChoiceImpactDisplay = memo(function ChoiceImpactDisplay({
  effects,
  className,
  currencyName: _currencyName = "货币",
}: ChoiceImpactDisplayProps) {
  if (!effects || Object.keys(effects).length === 0) return null;

  const entries = Object.entries(effects).filter(
    ([key, val]) => val !== 0 && !HIDDEN_RESOURCE_KEYS.has(key)
  );
  if (entries.length === 0) return null;

  return (
    <Card
      data-testid="choice-impact"
      className={cn("p-4 border-primary/20 bg-primary/5", className)}
    >
      <h4 className="text-sm font-medium text-primary mb-3">选择影响</h4>
      <div className="flex flex-wrap gap-3">
        {entries.map(([key, value]) => {
          const isPositive = value > 0;
          return (
            <div
              key={key}
              className={cn(
                "flex items-center gap-1.5 px-2.5 py-1 rounded-full text-sm font-medium",
                isPositive
                  ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                  : "bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300"
              )}
            >
              <span>{key}</span>
              {isPositive ? (
                <ArrowUp className="w-3 h-3" />
              ) : (
                <ArrowDown className="w-3 h-3" />
              )}
              <span>{Math.abs(value)}</span>
            </div>
          );
        })}
      </div>
    </Card>
  );
});

ChoiceImpactDisplay.displayName = "ChoiceImpactDisplay";
