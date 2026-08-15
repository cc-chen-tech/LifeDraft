"use client";

import { memo, type ComponentProps, type ReactNode, type Ref } from "react";

import { PageEdgeBookmark, PageTransition, Surface } from "@/components/story101";
import { cn } from "@/lib/utils";

import { PlayTools, type PlayToolsProps } from "./PlayTools";
import { StatusBar } from "./StatusBar";

export interface PlayReadingFrameProps
  extends Omit<ComponentProps<typeof PageTransition>, "children"> {
  contentRef?: Ref<HTMLDivElement>;
  playerState: Record<string, unknown> | null;
  progress: Record<string, unknown> | null;
  isViewingHistory: boolean;
  toolsProps: Omit<PlayToolsProps, "className">;
  children: ReactNode;
}

/** Shared visual frame for the real play page and its deterministic fixture. */
export const PlayReadingFrame = memo(function PlayReadingFrame({
  className,
  contentRef,
  playerState,
  progress,
  isViewingHistory,
  toolsProps,
  children,
  ...pageProps
}: PlayReadingFrameProps) {
  return (
    <PageTransition
      className={cn(
        "play-reading-axis min-h-screen bg-[var(--surface-canvas)] px-4 pt-6 md:px-6 md:pt-10",
        className,
      )}
      {...pageProps}
    >
      <div className="mx-auto grid w-full max-w-5xl items-start gap-8 md:grid-cols-[minmax(0,44rem)_minmax(10rem,14rem)] md:gap-10">
        <Surface
          data-testid="play-reading-surface"
          variant="reading"
          className="min-w-0 px-5 py-6 sm:px-8 sm:py-8 md:px-10 md:py-10"
        >
          <div ref={contentRef} className="min-w-0">
            <header className="mb-8 border-b border-[var(--border-default)] pb-5">
              <p className="mb-2 text-xs text-[var(--text-secondary)]">
                story101 · 人生草稿本
              </p>
              <StatusBar
                playerState={playerState}
                progress={progress}
                compact
                appearance="narrative"
              />
            </header>
            {children}
          </div>
        </Surface>

        <div className="md:sticky md:top-8 md:self-start">
          <PageEdgeBookmark
            className="hidden md:static md:top-auto md:block"
            label="当前人生"
            detail={isViewingHistory ? "历史回顾 · 只读" : "故事与选择"}
          />
          <PlayTools className="mt-4" {...toolsProps} />
        </div>
      </div>
    </PageTransition>
  );
});
