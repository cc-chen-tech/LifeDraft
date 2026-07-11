"use client";

import { useEffect } from "react";
import type { ReadingContext } from "@/lib/types";
import { useMusicStore } from "@/stores/useMusicStore";
import { useStoryVoiceStore } from "@/stores/useStoryVoiceStore";

interface CompletedStoryMediaGateProps {
  text: string;
  context: ReadingContext | null;
  storyReady: boolean;
  storyBusy: boolean;
  isViewingHistory: boolean;
}

export function CompletedStoryMediaGate({
  text,
  context,
  storyReady,
  storyBusy,
  isViewingHistory,
}: CompletedStoryMediaGateProps) {
  const setActiveStoryText = useMusicStore((state) => state.setActiveStoryText);
  const setActiveReadingTarget = useStoryVoiceStore((state) => state.setActiveReadingTarget);
  const clearActiveReadingTarget = useStoryVoiceStore((state) => state.clearActiveReadingTarget);
  const stopReading = useStoryVoiceStore((state) => state.stopReading);

  useEffect(() => {
    const finalText = text.trim();

    if (isViewingHistory) {
      setActiveStoryText(null);
      if (context && finalText) {
        setActiveReadingTarget({
          context: { ...context, text: finalText },
          autoReadText: finalText,
          autoReadReady: false,
        });
      } else {
        clearActiveReadingTarget();
      }
      return;
    }

    if (storyBusy) {
      setActiveStoryText(null);
      const voiceState = useStoryVoiceStore.getState();
      const staleCurrentStory =
        voiceState.currentSource === "current_story" ||
        voiceState.activeReadingContext?.source_type === "current_story";
      clearActiveReadingTarget();
      if (staleCurrentStory && voiceState.readingState !== "idle") {
        stopReading();
      }
      return;
    }

    if (storyReady && context && finalText) {
      setActiveStoryText(finalText);
      setActiveReadingTarget({
        context: { ...context, text: finalText },
        autoReadText: finalText,
        autoReadReady: true,
      });
      return;
    }

    setActiveStoryText(null);
    clearActiveReadingTarget();
  }, [
    clearActiveReadingTarget,
    context,
    isViewingHistory,
    setActiveReadingTarget,
    setActiveStoryText,
    stopReading,
    storyBusy,
    storyReady,
    text,
  ]);

  return null;
}
