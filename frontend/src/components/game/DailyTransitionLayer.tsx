"use client";

import { RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { formatDailyDate } from "@/lib/dailyTransition";


export function DailyTransitionLayer({
  transitionText,
  nextDate,
  failed,
  onRetry,
}: {
  transitionText: string;
  nextDate: string;
  failed: boolean;
  onRetry: () => void;
}) {
  return (
    <section
      role="status"
      aria-live="polite"
      aria-busy={!failed}
      className="mx-auto flex min-h-[62vh] w-full max-w-3xl flex-col items-center justify-center px-5 py-16 text-center transition-opacity duration-700 motion-reduce:transition-none"
      data-testid="daily-transition-layer"
    >
      <div className="mb-9 flex w-full max-w-md items-center gap-4" aria-hidden="true">
        <span className="h-px flex-1 bg-gradient-to-r from-transparent to-[var(--border-default)]" />
        <span className="h-1.5 w-1.5 rotate-45 border border-[var(--text-secondary)]" />
        <span className="h-px flex-1 bg-gradient-to-l from-transparent to-[var(--border-default)]" />
      </div>

      <p className="max-w-2xl font-serif text-[clamp(1.5rem,4vw,2.35rem)] font-medium leading-[1.65] tracking-[0.06em] text-[var(--text-primary)]">
        {transitionText}
      </p>

      <div className="mt-10 flex flex-col items-center gap-3">
        <p className="text-[0.68rem] font-medium uppercase tracking-[0.28em] text-[var(--text-secondary)]">
          即将到来
        </p>
        <p className="font-serif text-sm tracking-[0.12em] text-[var(--text-primary)]/80">
          {formatDailyDate(nextDate)}
        </p>
      </div>

      {failed ? (
        <div className="mt-9 flex flex-col items-center gap-4">
          <p className="text-sm text-[var(--text-secondary)]">下一日故事暂未生成</p>
          <Button variant="outline" size="sm" onClick={onRetry}>
            <RefreshCw className="mr-2 h-3.5 w-3.5" />
            重试生成
          </Button>
        </div>
      ) : (
        <div className="mt-9 flex items-center gap-2 text-xs tracking-[0.16em] text-[var(--text-secondary)]">
          <span className="h-1 w-1 animate-pulse rounded-full bg-current motion-reduce:animate-none" />
          下一日正在展开
        </div>
      )}
    </section>
  );
}
