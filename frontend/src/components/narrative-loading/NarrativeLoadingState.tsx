"use client";

import { cn } from "@/lib/utils";
import {
  resolveNarrativeLoadingCopy,
  type NarrativeLoadingContext,
  type NarrativeLoadingLayout,
  type NarrativeLoadingOperation,
  type NarrativeTransportState,
} from "./narrativeLoading";

export type {
  NarrativeLoadingContext,
  NarrativeLoadingLayout,
  NarrativeLoadingOperation,
  NarrativeTransportState,
} from "./narrativeLoading";
export { getNarrativeLoadingDelay, resolveNarrativeLoadingCopy } from "./narrativeLoading";

interface NarrativeLoadingStateProps {
  context: NarrativeLoadingContext;
  layout: NarrativeLoadingLayout;
  phase?: string | null;
  operation?: NarrativeLoadingOperation;
  stepLabel?: string;
  contextLabel?: string;
  delayed?: boolean;
  transport?: NarrativeTransportState;
  onAction?: () => void;
  className?: string;
}

export function NarrativeLoadingState({
  context,
  layout,
  phase,
  operation,
  stepLabel,
  contextLabel,
  delayed,
  transport,
  onAction,
  className,
}: NarrativeLoadingStateProps) {
  const copy = resolveNarrativeLoadingCopy({
    context,
    phase,
    operation,
    stepLabel,
    contextLabel,
    delayed,
    transport,
  });

  return (
    <section className={cn("narrative-loading", `narrative-loading--${layout}`, className)}>
      <div className="narrative-loading-copy" role="status" aria-live="polite">
        <h2 className="narrative-loading-title">{copy.title}</h2>
        {copy.status && <p className="narrative-loading-status">{copy.status}</p>}
        {copy.delayedCopy && <p className="narrative-loading-delayed">{copy.delayedCopy}</p>}
        <div className="narrative-loading-divider" aria-hidden="true" />
      </div>
      {copy.actionLabel && onAction && (
        <button className="narrative-loading-action" type="button" onClick={onAction}>
          {copy.actionLabel}
        </button>
      )}
    </section>
  );
}
