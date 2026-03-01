"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { Send, Loader2, ChevronRight } from "lucide-react";

interface OptionCardsProps {
  options: { text: string; potential_effects?: Record<string, unknown> }[];
  onSelect: (index: number) => void;
  onCustomChoice: (text: string) => void;
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

  const handleSelect = (index: number) => {
    if (disabled) return;
    setSelectedIndex(index);
    onSelect(index);
  };

  const handleCustomSubmit = () => {
    if (!customText.trim() || disabled) return;
    setSelectedIndex(-1); // -1 = custom
    onCustomChoice(customText.trim());
    setCustomText("");
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
          className={cn(
            "option-card group w-full text-left",
            "flex items-start gap-3 px-4 py-3.5 rounded-lg",
            "border border-border/60 bg-card/50",
            "transition-all duration-200 ease-out",
            "hover:bg-card hover:border-primary/40",
            "active:scale-[0.985]",
            disabled && "opacity-40 pointer-events-none",
            selectedIndex === i &&
              "border-primary/60 bg-primary/5 shadow-[0_0_16px_rgba(96,165,250,0.08)]"
          )}
          onClick={() => handleSelect(i)}
          disabled={disabled}
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
          <span className="flex-1 text-sm text-foreground/85 leading-relaxed group-hover:text-foreground transition-colors duration-200">
            {option.text}
          </span>

          {/* Action indicator */}
          {disabled && selectedIndex === i ? (
            <Loader2 className="w-3.5 h-3.5 mt-0.5 animate-spin text-primary flex-shrink-0" />
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
              disabled={disabled}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleCustomSubmit();
                }
              }}
            />
          </div>
          <Button
            size="icon"
            variant="ghost"
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
      </div>
    </div>
  );
}
