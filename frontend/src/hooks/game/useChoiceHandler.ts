"use client";

import { useGameStore } from "@/stores/useGameStore";
import { streamChoice, streamCustomChoice } from "@/lib/sse";
import type { EventOption } from "@/lib/types";
import type { Phase, ConnectionStatus } from "./usePhaseManager";
import { handleChoiceComplete, handleChoiceError, ChoiceHandlers } from "./choiceUtils";
import { markRetry } from "./eventUtils";

interface UseChoiceHandlerParams {
  gameId: number | null;
  abortRef: React.MutableRefObject<AbortController | null>;
  generatingRef: React.MutableRefObject<boolean>;
  setPhase: (phase: Phase | ((prev: Phase) => Phase)) => void;
  setConnectionStatus: (status: ConnectionStatus) => void;
  setReconnectAttempt: (attempt: { current: number; max: number } | null) => void;
  setProcessing: (processing: boolean, message?: string) => void;
  appendStoryText: (text: string) => void;
  setCurrentEvent: (event: { story: string; options: EventOption[] } | null) => void;
  setGameOver: (gameOver: boolean) => void;
  setSummaryText: (text: string) => void;
  setRoundSummary: (summary: string | null) => void;
  setOptions: (options: EventOption[]) => void;
  setStoryText: (text: string) => void;
}

/**
 * Hook for handling player choices (normal and custom).
 * Manages SSE-based choice processing with fallback to sync API.
 */
export function useChoiceHandler({
  gameId,
  abortRef,
  generatingRef,
  setPhase,
  setConnectionStatus,
  setReconnectAttempt,
  setProcessing,
  appendStoryText,
  setCurrentEvent,
  setGameOver,
  setSummaryText,
  setRoundSummary,
  setOptions,
  setStoryText,
}: UseChoiceHandlerParams) {

  // Shared handlers object
  const handlers: ChoiceHandlers = {
    setProcessing,
    setConnectionStatus,
    setReconnectAttempt,
    setRoundSummary,
    setSummaryText,
    setCurrentEvent,
    setGameOver,
    setOptions,
    setStoryText,
    setPhase,
    generatingRef,
  };

  // Common SSE callbacks factory
  const createSSECallbacks = (logPrefix: string) => ({
    onStory: (text: string) => {
      appendStoryText(text);
    },
    onStatus: (status: { phase: string }) => {
      setProcessing(true, status.phase);
    },
    onConnectionStatus: (status: ConnectionStatus) => {
      setConnectionStatus(status);
      if (status !== "reconnecting") {
        setReconnectAttempt(null);
      }
    },
    onReconnecting: (attempt: number, maxRetries: number) => {
      setReconnectAttempt({ current: attempt, max: maxRetries });
    },
    onComplete: (data: Record<string, unknown>) => {
      handleChoiceComplete(data, handlers);
    },
  });

  // Handle choice selection
  const handleChoice = async (optionIndex: number, isRetry = false) => {
    if (!gameId) return;
    abortRef.current?.abort();
    generatingRef.current = false;

    setPhase("choosing");
    setConnectionStatus(null);
    abortRef.current = new AbortController();

    let sseSucceeded = false;

    const callbacks = {
      ...createSSECallbacks("handleChoice"),
      onStory: (text: string) => {
        sseSucceeded = true;
        appendStoryText(text);
      },
      onStatus: (status: { phase: string }) => {
        sseSucceeded = true;
        // ★ 处理 retry 状态：清空旧故事，标记重试
        if (status.phase === "retry") {
          console.log("[handleChoice] Retry event received, clearing story for new content");
          markRetry();
          useGameStore.setState({ storyText: "" });
          setProcessing(true, "retrying");
          return;
        }
        if (status.phase === "retrying") {
          console.log("[handleChoice] Retrying detected, story will be regenerated");
          setProcessing(true, "retrying");
          return;
        }
        setProcessing(true, status.phase);
      },
      onError: async (err: unknown) => {
        await handleChoiceError(err, gameId, handlers, {
          optionIndex,
          isRetry,
          sseSucceeded,
          retryChoice: () => handleChoice(optionIndex, true),
        }, "handleChoice");
      },
    };

    await streamChoice(gameId, optionIndex, callbacks, { signal: abortRef.current.signal });
  };

  // Handle custom choice
  const handleCustomChoice = async (customText: string) => {
    if (!gameId) return;
    abortRef.current?.abort();
    generatingRef.current = false;

    setPhase("choosing");
    setConnectionStatus(null);
    abortRef.current = new AbortController();

    let sseSucceeded = false;

    const callbacks = {
      ...createSSECallbacks("handleCustomChoice"),
      onStory: (text: string) => {
        sseSucceeded = true;
        appendStoryText(text);
      },
      onStatus: (status: { phase: string }) => {
        sseSucceeded = true;
        // ★ 处理 retry 状态：清空旧故事，标记重试
        if (status.phase === "retry") {
          console.log("[handleCustomChoice] Retry event received, clearing story for new content");
          markRetry();
          useGameStore.setState({ storyText: "" });
          setProcessing(true, "retrying");
          return;
        }
        if (status.phase === "retrying") {
          console.log("[handleCustomChoice] Retrying detected, story will be regenerated");
          setProcessing(true, "retrying");
          return;
        }
        setProcessing(true, status.phase);
      },
      onError: async (err: unknown) => {
        await handleChoiceError(err, gameId, handlers, {
          customText,
          isRetry: false,
          sseSucceeded,
        }, "handleCustomChoice");
      },
    };

    await streamCustomChoice(gameId, customText, callbacks, { signal: abortRef.current.signal });
  };

  return {
    handleChoice,
    handleCustomChoice,
  };
}
