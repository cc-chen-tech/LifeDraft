"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { Send, Loader2, ChevronRight } from "lucide-react";
import { LengthIndicator } from "@/components/ui/length-indicator";
import { INPUT_LIMITS } from "@/types/input-limits.generated";

interface OptionCardsProps {
  options: { text: string; potential_effects?: Record<string, unknown> }[];
  onSelect: (index: number) => void | Promise<void>;
  onCustomChoice: (text: string) => void | Promise<void>;
  disabled?: boolean;
  className?: string;
}

/**
 * OptionCards — 选项卡片组 + 自定义输入框
 * - 左侧序号 + 左对齐文本，紧凑优雅
 * - 始终提供自定义输入
 * - 44px 最小触控区域
 */
export function OptionCards({
  options,
  onSelect,
  onCustomChoice,
  disabled = false,
  className,
}: OptionCardsProps) {
  const [customText, setCustomText] = useState("");
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const isSubmitting = selectedIndex !== null;
  const controlsDisabled = disabled || isSubmitting;

  const handleSelect = async (index: number) => {
    if (controlsDisabled) return;
    setSelectedIndex(index);
    try {
      const pendingSelection = onSelect(index);
      if (pendingSelection) await pendingSelection;
    } finally {
      setSelectedIndex(null);
    }
  };

  const handleCustomSubmit = async () => {
    if (
      !customText.trim() ||
      controlsDisabled ||
      Array.from(customText).length > INPUT_LIMITS.customAction
    ) return;
    const submittedText = customText.trim();
    setSelectedIndex(-1); // -1 = custom
    setCustomText("");
    try {
      const pendingSelection = onCustomChoice(submittedText);
      if (pendingSelection) await pendingSelection;
    } finally {
      setSelectedIndex(null);
    }
  };

  return (
    <div className={cn("space-y-2", className)}>
      {/* Section hint */}
      <p className="text-xs text-muted-foreground/70 mb-1 tracking-wide">
        你的选择
      </p>

      {/* Option cards */}
      {options.map((option, i) => (
        <button
          key={i}
          aria-label={`选择 ${i + 1}：${option.text}`}
          title={option.text}
          className={cn(
            "option-card group w-full text-left",
            "flex min-h-14 items-center gap-3 px-4 py-3 rounded-lg",
            "border border-border/60 bg-card/50",
            "transition-all duration-200 ease-out",
            "hover:bg-card hover:border-primary/40",
            "active:scale-[0.985]",
            controlsDisabled && selectedIndex !== i && "opacity-40",
            selectedIndex === i &&
              "border-primary/60 bg-primary/5 shadow-[0_0_16px_rgba(96,165,250,0.08)]"
          )}
          onClick={() => void handleSelect(i)}
          disabled={controlsDisabled}
        >
          {/* Ordinal number */}
          <span
            className={cn(
              "flex-shrink-0 w-5 h-5 mt-0.5 rounded text-[11px] font-medium",
              "flex items-center justify-center",
              "bg-primary/10 text-primary/70",
              "transition-colors duration-200",
              "group-hover:bg-primary/20 group-hover:text-primary",
              selectedIndex === i && "bg-primary/25 text-primary"
            )}
          >
            {i + 1}
          </span>

          {/* Option text */}
          <span
            data-testid={`option-text-${i}`}
            className="line-clamp-2 flex-1 text-sm text-foreground/85 leading-relaxed group-hover:text-foreground transition-colors duration-200"
          >
            {option.text}
          </span>

          {/* Action indicator */}
          {isSubmitting && selectedIndex === i ? (
            <span className="flex flex-shrink-0 items-center gap-1.5 text-xs text-primary" role="status">
              <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden="true" />
              <span aria-hidden="true">正在进入</span>
              <span className="sr-only">正在进入下一段人生</span>
            </span>
          ) : (
            <ChevronRight
              className={cn(
                "w-3.5 h-3.5 mt-0.5 flex-shrink-0",
                "text-muted-foreground/30 transition-all duration-200",
                "group-hover:text-primary/60 group-hover:translate-x-0.5"
              )}
            />
          )}
        </button>
      ))}

      {/* Custom input */}
      <div className="pt-3 mt-1">
        <div className="flex items-end gap-2">
          <div className="flex-1 relative">
            <Textarea
              value={customText}
              onChange={(e) => setCustomText(e.target.value)}
              placeholder="或者，描述你想做的事情..."
              className={cn(
                "min-h-[44px] max-h-[120px] pr-3",
                "bg-background/50 border-border/40 text-sm resize-none",
                "placeholder:text-muted-foreground/40",
                "focus:border-primary/40 focus:bg-background/80",
                "transition-colors duration-200"
              )}
              disabled={controlsDisabled}
              maxLength={INPUT_LIMITS.customAction}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void handleCustomSubmit();
                }
              }}
            />
            <LengthIndicator value={customText} limit={INPUT_LIMITS.customAction} />
          </div>
          <Button
            size="icon"
            variant="ghost"
            aria-label="提交自定义选择"
            className={cn(
              "h-10 w-10 rounded-lg flex-shrink-0",
              "text-muted-foreground/50 hover:text-primary hover:bg-primary/10",
              "transition-all duration-200",
              customText.trim() && "text-primary"
            )}
            disabled={controlsDisabled || !customText.trim()}
            onClick={() => void handleCustomSubmit()}
          >
            {isSubmitting && selectedIndex === -1 ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
