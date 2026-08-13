"use client";

import { useRef } from "react";
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
  setCurrentEvent: (event: { story: string; options: EventOption[]; event_id?: string; revision?: number; story_date?: string } | null) => void;
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
  const choiceBaseStoryRef = useRef("");

  const applyCompleteOnlyStoryFallback = (data: Record<string, unknown>) => {
    const completeStory =
      typeof data.event_description === "string"
        ? data.event_description.trim()
        : typeof data.story_continuation === "string"
          ? data.story_continuation.trim()
          : "";
    if (!completeStory) return;

    const baseStory = choiceBaseStoryRef.current.trim();
    setStoryText(baseStory ? `${baseStory}\n\n${completeStory}` : completeStory);
  };

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
    console.log(`[handleChoice] Called with gameId=${gameId}, optionIndex=${optionIndex}`);
    if (!gameId) {
      console.error("[handleChoice] No gameId available");
      return;
    }
    abortRef.current?.abort();
    generatingRef.current = false;
    choiceBaseStoryRef.current = useGameStore.getState().storyText || "";

    setPhase("choosing");
    setConnectionStatus(null);
    abortRef.current = new AbortController();

    let sseSucceeded = false;
    let choiceCompleted = false;
    let errorHandled = false;
    let storyChunkReceived = false;

    const callbacks = {
      ...createSSECallbacks("handleChoice"),
      onStory: (text: string) => {
        sseSucceeded = true;
        storyChunkReceived = true;
        appendStoryText(text);
      },
      onStatus: (status: { phase: string }) => {
        sseSucceeded = true;
        // ★ 处理 retry 状态：清空旧故事，标记重试
        if (status.phase === "retry") {
          console.log("[handleChoice] Retry event received, restoring base story for replacement content");
          markRetry();
          setStoryText(choiceBaseStoryRef.current);
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
      onComplete: (data: Record<string, unknown>) => {
        sseSucceeded = true;
        choiceCompleted = true;
        if (!storyChunkReceived) {
          applyCompleteOnlyStoryFallback(data);
        }
        handleChoiceComplete(data, handlers);
      },
      onError: async (err: unknown) => {
        if (choiceCompleted) {
          console.warn("[handleChoice] Ignoring late SSE error after complete");
          return;
        }
        errorHandled = true;
        await handleChoiceError(err, gameId, handlers, {
          optionIndex,
          isRetry,
          sseSucceeded,
          baseStoryText: choiceBaseStoryRef.current,
          retryChoice: () => handleChoice(optionIndex, true),
        }, "handleChoice");
      },
    };

    try {
      const currentEvent = useGameStore.getState().currentEvent;
      await streamChoice(gameId, optionIndex, callbacks, {
        signal: abortRef.current.signal,
        eventId: currentEvent?.event_id,
        revision: currentEvent?.revision,
      });
    } catch (err) {
      if (abortRef.current?.signal.aborted) {
        return;
      }
      if (choiceCompleted) {
        return;
      }
      if (!errorHandled) {
        errorHandled = true;
        await handleChoiceError(err, gameId, handlers, {
          optionIndex,
          isRetry,
          sseSucceeded,
          baseStoryText: choiceBaseStoryRef.current,
          retryChoice: () => handleChoice(optionIndex, true),
        }, "handleChoice");
        return;
      }
      console.warn("[handleChoice] streamChoice rejected after onError handling");
    }
  };

  // Handle custom choice
  const handleCustomChoice = async (customText: string) => {
    if (!gameId) return;
    abortRef.current?.abort();
    generatingRef.current = false;
    choiceBaseStoryRef.current = useGameStore.getState().storyText || "";

    setPhase("choosing");
    setConnectionStatus(null);
    abortRef.current = new AbortController();

    let sseSucceeded = false;
    let choiceCompleted = false;
    let errorHandled = false;
    let storyChunkReceived = false;

    const callbacks = {
      ...createSSECallbacks("handleCustomChoice"),
      onStory: (text: string) => {
        sseSucceeded = true;
        storyChunkReceived = true;
        appendStoryText(text);
      },
      onStatus: (status: { phase: string }) => {
        sseSucceeded = true;
        // ★ 处理 retry 状态：清空旧故事，标记重试
        if (status.phase === "retry") {
          console.log("[handleCustomChoice] Retry event received, restoring base story for replacement content");
          markRetry();
          setStoryText(choiceBaseStoryRef.current);
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
      onComplete: (data: Record<string, unknown>) => {
        sseSucceeded = true;
        choiceCompleted = true;
        if (!storyChunkReceived) {
          applyCompleteOnlyStoryFallback(data);
        }
        handleChoiceComplete(data, handlers);
      },
      onError: async (err: unknown) => {
        if (choiceCompleted) {
          console.warn("[handleCustomChoice] Ignoring late SSE error after complete");
          return;
        }
        errorHandled = true;
        await handleChoiceError(err, gameId, handlers, {
          customText,
          isRetry: false,
          sseSucceeded,
          baseStoryText: choiceBaseStoryRef.current,
        }, "handleCustomChoice");
      },
    };

    try {
      await streamCustomChoice(gameId, customText, callbacks, { signal: abortRef.current.signal });
    } catch (err) {
      if (abortRef.current?.signal.aborted) {
        return;
      }
      if (choiceCompleted) {
        return;
      }
      if (!errorHandled) {
        errorHandled = true;
        await handleChoiceError(err, gameId, handlers, {
          customText,
          isRetry: false,
          sseSucceeded,
          baseStoryText: choiceBaseStoryRef.current,
        }, "handleCustomChoice");
        return;
      }
      console.warn("[handleCustomChoice] streamCustomChoice rejected after onError handling");
    }
  };

  return {
    handleChoice,
    handleCustomChoice,
  };
}
