"use client";

import { Play } from "lucide-react";
import { Button } from "@/components/ui/button";

interface OpeningCompletionGateProps {
  backendComplete: boolean;
  visibleComplete: boolean;
  onStart: () => void;
}

export function OpeningCompletionGate({
  backendComplete,
  visibleComplete,
  onStart,
}: OpeningCompletionGateProps) {
  const ready = backendComplete && visibleComplete;
  const waitingMessage = backendComplete ? "正在显示完整故事..." : "故事正在展开...";

  return (
    <div className="flex flex-col items-center gap-2">
      <Button
        size="lg"
        className="h-14 px-8 text-base touch-target animate-fade-in-word disabled:bg-muted disabled:text-muted-foreground disabled:opacity-100 disabled:cursor-not-allowed disabled:hover:bg-muted"
        onClick={ready ? onStart : undefined}
        disabled={!ready}
        aria-busy={!ready}
        aria-describedby={!ready ? "opening-start-status" : undefined}
        aria-disabled={!ready}
        aria-label="开始我的人生"
        title="开始我的人生"
      >
        <Play className="w-5 h-5 mr-2" />
        开始我的人生
      </Button>
      {!ready && (
        <p
          className="text-sm text-muted-foreground animate-pulse"
          id="opening-start-status"
          role="status"
        >
          {waitingMessage}
        </p>
      )}
    </div>
  );
}
