"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { FileText, Loader2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
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
    <section
      role="dialog"
      data-testid="life-summary-panel"
      aria-label="人生总结"
      className={cn(
        "fixed bottom-20 left-4 right-4 sm:left-auto sm:w-[min(28rem,calc(100vw-2rem))] max-w-md z-50",
        "bg-card/95 backdrop-blur-sm border border-border shadow-xl rounded-lg",
        "p-4 safe-area-pb",
        className,
      )}
    >
      <div className="flex items-center gap-2 mb-3">
        <FileText className="w-4 h-4 text-primary" />
        <h2 className="text-sm font-semibold text-foreground">人生总结</h2>
        <div className="flex-1" />
        <Button
          size="icon"
          variant="ghost"
          className="h-8 w-8"
          onClick={onClose}
          aria-label="关闭人生总结"
          title="关闭人生总结"
        >
          <X className="w-4 h-4" />
        </Button>
      </div>
      <div className="max-h-[320px] overflow-y-auto text-sm text-muted-foreground">
        {isLoading ? (
          <div className="flex items-center gap-2 rounded-lg bg-secondary px-3 py-2">
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
            正在生成总结...
          </div>
        ) : error ? (
          <div className="rounded-lg bg-destructive/10 px-3 py-2 text-destructive">{error}</div>
        ) : summary ? (
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground">
              {getSummaryWeekLabel(summary.startWeek, summary.endWeek)}
            </p>
            <div className="prose prose-sm prose-invert max-w-none text-muted-foreground">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{summary.text}</ReactMarkdown>
            </div>
          </div>
        ) : (
          <div className="rounded-lg bg-secondary px-3 py-2">暂无总结内容</div>
        )}
      </div>
    </section>
  );
}
