"use client";

import { useId, useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { FormField } from "@/components/story101";
import { cn } from "@/lib/utils";
import { Send, Loader2, ChevronRight } from "lucide-react";
import { LengthIndicator } from "@/components/ui/length-indicator";
import { INPUT_LIMITS } from "@/types/input-limits.generated";
import { isWithinInputLimit } from "@/lib/inputLimits";

interface OptionCardsProps {
  options: { text: string; potential_effects?: Record<string, unknown> }[];
  onSelect: (index: number) => void;
  onCustomChoice?: (text: string) => void;
  allowCustomChoice?: boolean;
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
  allowCustomChoice = true,
  disabled = false,
  className,
}: OptionCardsProps) {
  const [customText, setCustomText] = useState("");
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const customChoiceId = useId();
  const customChoiceCountId = `${customChoiceId}-count`;
  const isSubmitting = selectedIndex !== null;
  const controlsDisabled = disabled || isSubmitting;
  const customChoiceWithinLimit = isWithinInputLimit(
    customText,
    INPUT_LIMITS.customAction,
  );

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
      !isWithinInputLimit(customText, INPUT_LIMITS.customAction)
    ) return;
    const submittedText = customText.trim();
    setSelectedIndex(-1); // -1 = custom
    onCustomChoice?.(customText.trim());
    setCustomText("");
    try {
      const pendingSelection = onCustomChoice(submittedText);
      if (pendingSelection) await pendingSelection;
    } finally {
      setSelectedIndex(null);
    }
  };

  return (
    <div className={cn("grid gap-0", className)}>
      {/* Section hint */}
      <p className="mb-2 text-xs tracking-[0.16em] text-[var(--text-secondary)]">
        你的选择
      </p>

      {/* Story branches */}
      {options.map((option, i) => (
        <button
          key={i}
          data-slot="choice-branch-row"
          aria-label={`选择 ${i + 1}：${option.text}`}
          title={option.text}
          className={cn(
            "group flex min-h-14 w-full items-center gap-3 px-0 py-3 text-left",
            "rounded-none border-x-0 border-t-0 border-b border-[var(--border-default)] bg-transparent shadow-none",
            "transition-colors duration-200 ease-out",
            "hover:border-[var(--border-strong)]",
            "focus-visible:relative focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--surface-reading)]",
            controlsDisabled && selectedIndex !== i && "opacity-40",
            selectedIndex === i &&
              "border-[var(--border-strong)]"
          )}
          onClick={() => void handleSelect(i)}
          disabled={controlsDisabled}
        >
          {/* Ordinal number */}
          <span
            data-testid={`option-ordinal-${i}`}
            aria-hidden="true"
            className={cn(
              "w-7 flex-shrink-0 font-mono text-xs font-medium tabular-nums tracking-[0.14em]",
              "text-[var(--text-secondary)]",
              "transition-colors duration-200",
              "group-hover:text-[var(--text-primary)]",
              selectedIndex === i && "text-[var(--text-primary)]"
            )}
          >
            {i + 1}
          </span>

          {/* Option text */}
          <span
            data-testid={`option-text-${i}`}
            className="min-w-0 flex-1 whitespace-normal break-words text-sm leading-7 text-[var(--text-primary)]"
          >
            {option.text}
          </span>

          {/* Action indicator */}
          {isSubmitting && selectedIndex === i ? (
            <span className="flex flex-shrink-0 items-center gap-1.5 text-sm text-[var(--text-secondary)]" role="status">
              <Loader2 className="w-3.5 h-3.5 animate-spin" aria-hidden="true" />
              <span aria-hidden="true">正在进入</span>
              <span className="sr-only">正在进入下一段人生</span>
            </span>
          ) : (
            <ChevronRight
              className={cn(
                "w-3.5 h-3.5 mt-0.5 flex-shrink-0",
                "text-[var(--text-secondary)] transition-transform duration-200",
                "group-hover:translate-x-0.5"
              )}
            />
          )}
        </button>
      ))}

      {/* Custom input is legacy-only. Daily timeline accepts generated options. */}
      {allowCustomChoice && onCustomChoice && <div className="pt-3 mt-1">
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
              disabled={disabled}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleCustomSubmit();
                }
                onClick={() => void handleCustomSubmit()}
              >
                {isSubmitting && selectedIndex === -1 ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
              </Button>
            </div>
            <LengthIndicator
              id={customChoiceCountId}
              value={customText}
              limit={INPUT_LIMITS.customAction}
              announce={!customChoiceWithinLimit}
              className="mt-0"
            />
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
            disabled={disabled || !customText.trim()}
            onClick={handleCustomSubmit}
          >
            {disabled && selectedIndex === -1 ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </Button>
        </div>
      </div>}
    </div>
  );
}
