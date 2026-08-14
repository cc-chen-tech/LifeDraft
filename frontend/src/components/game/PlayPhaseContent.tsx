"use client";

import type { ReactNode } from "react";
import { ArrowRight, CheckCircle2, Loader2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import {
  NarrativeLoadingState,
  type NarrativeLoadingOperation,
  type NarrativeTransportState,
} from "@/components/narrative-loading/NarrativeLoadingState";
import { FeedbackNotice } from "@/components/story101";
import { Button } from "@/components/ui/button";
import type { EventOption } from "@/lib/types";

import { OptionCards } from "./OptionCards";
import { StreamingText } from "./StreamingText";

export type PlayVisualPhase =
  | "loading"
  | "generating"
  | "options"
  | "choosing"
  | "result"
  | "summary"
  | "error";

export interface GameplayLoadingPresentation {
  visible: boolean;
  phase?: string | null;
  operation?: NarrativeLoadingOperation;
  delayed?: boolean;
  transport: NarrativeTransportState;
  onAction: () => void;
}

export interface PlayPhaseContentProps {
  phase: PlayVisualPhase;
  isViewingHistory: boolean;
  displayText: string;
  storyStreaming?: boolean;
  historyPosition: { week: number; round: number } | null;
  onBackToCurrent: () => void;
  loading: GameplayLoadingPresentation;
  media?: ReactNode;
  roundSummary?: string | null;
  options: EventOption[];
  onSelectChoice: (index: number) => void | Promise<void>;
  onCustomChoice?: (text: string) => void | Promise<void>;
  isDailyTimeline?: boolean;
  result: {
    currentRound: number;
    roundsPerWeek: number;
    isPrefetching: boolean;
    onContinue: () => void;
  };
  weeklySummary: {
    text: string;
    onContinue: () => void;
  };
  inlineError: {
    visible: boolean;
    onRetry: () => void;
  };
}

function GameplayLoading({
  layout,
  loading,
}: {
  layout: "section" | "inline";
  loading: GameplayLoadingPresentation;
}) {
  const sharedProps = {
    context: "gameplay" as const,
    layout,
    phase: loading.phase,
    operation: loading.operation,
    delayed: loading.delayed,
  };

  if (loading.transport === "active") {
    return <NarrativeLoadingState {...sharedProps} />;
  }

  return (
    <NarrativeLoadingState
      {...sharedProps}
      transport={loading.transport}
      onAction={loading.onAction}
    />
  );
}

/** Shared story and phase presentation; business orchestration stays in PlayPage. */
export function PlayPhaseContent({
  phase,
  isViewingHistory,
  displayText,
  storyStreaming = phase === "generating" || phase === "choosing",
  historyPosition,
  onBackToCurrent,
  loading,
  media,
  roundSummary,
  options,
  onSelectChoice,
  onCustomChoice,
  isDailyTimeline = false,
  result,
  weeklySummary,
  inlineError,
}: PlayPhaseContentProps) {
  const currentRound = result.currentRound || 0;
  const roundsPerWeek = result.roundsPerWeek || 3;
  const roundNames = ["周一", "周中", "周末"];
  const isLastRound = currentRound >= roundsPerWeek;
  const nextName = roundNames[currentRound] || `第${currentRound + 1}轮`;

  return (
    <>
      {isViewingHistory && (
        <p className="mb-6 border-l-2 border-[var(--border-interactive)] pl-3 text-sm text-[var(--text-secondary)]">
          正在查看历史轮次（只读模式）
        </p>
      )}

      {!isViewingHistory && loading.visible && !displayText && (
        <GameplayLoading layout="section" loading={loading} />
      )}

      {displayText &&
        (isViewingHistory ? (
          <section
            data-slot="play-story"
            data-testid="history-reading-surface"
            className="mb-8 border-y border-[var(--border-default)] py-6"
          >
            <div className="mb-4 flex items-center justify-between gap-3">
              <div>
                <p className="text-xs text-[var(--text-secondary)]">
                  历史回顾
                </p>
                <h2 className="text-base font-medium text-[var(--text-primary)]">
                  第 {(historyPosition?.week ?? 0) + 1} 周 · 第{
                    (historyPosition?.round ?? 0) + 1
                  } 轮
                </h2>
              </div>
              <Button
                type="button"
                variant="narrative"
                size="touch"
                onClick={onBackToCurrent}
              >
                返回当前
              </Button>
            </div>
            <StreamingText
              text={displayText}
              isStreaming={false}
              narrative
              className="mb-0"
            />
          </section>
        ) : (
          <article data-slot="play-story">
            <StreamingText
              text={displayText}
              isStreaming={storyStreaming}
              narrative
              className="mb-6"
            />
            {loading.visible && (
              <GameplayLoading layout="inline" loading={loading} />
            )}
          </article>
        ))}

      {media}

      {!isViewingHistory && roundSummary && phase === "result" && (
        <section
          data-testid="round-summary"
          className="my-8 border-y border-[var(--border-default)] py-5"
        >
          <h2 className="mb-3 text-sm font-medium text-[var(--text-primary)]">
            刚才的选择，留下的变化
          </h2>
          <div className="prose-story text-sm text-[var(--text-secondary)]">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {roundSummary}
            </ReactMarkdown>
          </div>
        </section>
      )}

      {!isViewingHistory && phase === "options" && options.length > 0 && (
        <section
          data-testid="play-options"
          className="mt-10 border-t border-[var(--border-default)] pt-7"
        >
          <OptionCards
            options={options}
            onSelect={onSelectChoice}
            onCustomChoice={onCustomChoice}
            allowCustomChoice={!isDailyTimeline}
            disabled={false}
          />
        </section>
      )}

      {!isDailyTimeline && !isViewingHistory && phase === "result" && (
        <section
          data-testid="play-result-actions"
          className="mt-8 space-y-4 border-t border-[var(--border-default)] pt-7"
        >
          <Button
            type="button"
            variant="narrative"
            size="touch"
            className="w-full"
            onClick={result.onContinue}
          >
            {isLastRound ? (
              <>
                <CheckCircle2 className="mr-2 h-4 w-4" />
                确认并继续
              </>
            ) : (
              <>
                <ArrowRight className="mr-2 h-4 w-4" />
                进入{nextName}
              </>
            )}
          </Button>
          {result.isPrefetching && (
            <p className="flex items-center justify-center gap-1 text-center text-xs text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" />
              正在预加载下一段故事...
            </p>
          )}
        </section>
      )}

      {!isDailyTimeline && !isViewingHistory && phase === "summary" && (
        <section
          data-testid="play-week-summary"
          className="mt-8 space-y-7 border-t border-[var(--border-default)] pt-7"
        >
          <h2 className="mb-4 text-lg font-medium text-[var(--text-primary)]">
            周总结
          </h2>
          <div className="prose-story text-base">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {weeklySummary.text}
            </ReactMarkdown>
          </div>
          <Button
            type="button"
            variant="narrative"
            size="touch"
            className="w-full"
            onClick={weeklySummary.onContinue}
          >
            继续人生旅途
          </Button>
        </section>
      )}

      {!isViewingHistory && inlineError.visible && (
        <FeedbackNotice
          tone="danger"
          title="这一段暂时没有写完"
          className="my-8"
          action={
            <Button
              type="button"
              variant="narrative"
              size="touch"
              onClick={inlineError.onRetry}
            >
              重试
            </Button>
          }
        >
          请重试当前故事。
        </FeedbackNotice>
      )}
    </>
  );
}
