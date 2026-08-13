"use client";

import { Loader2, Play } from "lucide-react";
import { Button } from "@/components/ui/button";

interface OpeningCompletionGateProps {
  backendComplete: boolean;
  visibleComplete: boolean;
  pending?: boolean;
  onStart: () => void;
}

export function OpeningCompletionGate({
  backendComplete,
  visibleComplete,
  pending = false,
  onStart,
}: OpeningCompletionGateProps) {
  const ready = backendComplete && visibleComplete && !pending;
  const waitingMessage = pending
    ? "正在保存人生起点..."
    : backendComplete
      ? "正在显示完整故事..."
      : "故事正在展开...";
  const buttonLabel = pending ? "正在进入" : "开始我的人生";

  return (
    <div className="flex flex-col items-center gap-2">
      <Button
        type="button"
        variant="narrative"
        size="touch"
        className="min-h-14 px-8 text-base disabled:bg-[var(--surface-raised)] disabled:text-[var(--text-secondary)] disabled:opacity-100 disabled:cursor-not-allowed disabled:hover:bg-[var(--surface-raised)]"
        onClick={ready ? onStart : undefined}
        disabled={!ready}
        aria-busy={!ready}
        aria-describedby={!ready ? "opening-start-status" : undefined}
        aria-disabled={!ready}
        aria-label={buttonLabel}
        title={buttonLabel}
      >
        {pending ? (
          <Loader2 className="w-5 h-5 mr-2 animate-spin" />
        ) : (
          <Play className="w-5 h-5 mr-2" />
        )}
        {buttonLabel}
      </Button>
      {!ready && (
        <p
          className="text-sm text-[var(--text-secondary)]"
          id="opening-start-status"
          role="status"
          aria-live="polite"
        >
          {waitingMessage}
        </p>
      )}
    </div>
  );
}
