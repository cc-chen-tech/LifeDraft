"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { FileText, Loader2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { FeedbackNotice, Surface } from "@/components/story101";
import { cn } from "@/lib/utils";

export interface LifeSummaryData {
  text: string;
  startWeek: number;
  endWeek: number;
}

interface LifeSummaryPanelProps {
  summary: LifeSummaryData | null;
  isLoading: boolean;
  error: string | null;
  onClose: () => void;
  className?: string;
}

function getSummaryWeekLabel(startWeek: number, endWeek: number): string {
  return startWeek === endWeek ? `第${startWeek}周` : `第${startWeek}-${endWeek}周`;
}

export function LifeSummaryPanel({
  summary,
  isLoading,
  error,
  onClose,
  className,
}: LifeSummaryPanelProps) {
  return (
    <Surface asChild variant="overlay">
    <section
      role="dialog"
      data-testid="life-summary-panel"
      aria-label="人生总结"
      onKeyDown={(event) => {
        if (event.key === "Escape") onClose();
      }}
      className={cn(
        "play-chat-surface fixed left-4 right-4 z-[70] max-w-md p-4 safe-area-pb sm:left-auto sm:w-[min(28rem,calc(100vw-2rem))]",
        className,
      )}
    >
      <div className="mb-4 flex items-center gap-2 border-b border-[var(--border-default)] pb-3">
        <FileText className="h-4 w-4 text-[var(--text-secondary)]" />
        <h2 className="text-sm font-medium text-[var(--text-primary)]">人生总结</h2>
        <div className="flex-1" />
        <Button
          type="button"
          size="icon-touch"
          variant="quiet"
          autoFocus
          onClick={onClose}
          aria-label="关闭人生总结"
          title="关闭人生总结"
        >
          <X className="w-4 h-4" />
        </Button>
      </div>
      <div className="max-h-[min(22rem,55dvh)] overflow-y-auto text-sm text-[var(--text-secondary)]">
        {isLoading ? (
          <FeedbackNotice tone="info">
            <span className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              正在生成总结...
            </span>
          </FeedbackNotice>
        ) : error ? (
          <FeedbackNotice tone="danger">{error}</FeedbackNotice>
        ) : summary ? (
          <div className="space-y-2">
            <p className="text-xs text-[var(--text-secondary)]">
              {getSummaryWeekLabel(summary.startWeek, summary.endWeek)}
            </p>
            <div className="prose-story max-w-none text-sm text-[var(--text-secondary)]">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{summary.text}</ReactMarkdown>
            </div>
          </div>
        ) : (
          <p className="border-y border-[var(--border-default)] py-3">暂无总结内容</p>
        )}
      </div>
    </section>
    </Surface>
  );
}
