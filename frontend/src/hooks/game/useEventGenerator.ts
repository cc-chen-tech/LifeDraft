"use client";

import { useCallback, useEffect, useRef } from "react";
import { useGameStore } from "@/stores/useGameStore";
import { streamGameEvent } from "@/lib/sse";
import type { EventOption } from "@/lib/types";
import type { Phase, ConnectionStatus } from "./usePhaseManager";
import { handleEventComplete, handleStatusUpdate, type EventHandlers } from "./eventUtils";
import { parseSSEError } from "./choiceUtils";

interface UseEventGeneratorParams {
  gameId: number | null;
  phaseRef: React.MutableRefObject<Phase>;
  setPhase: (phase: Phase | ((prev: Phase) => Phase)) => void;
  setConnectionStatus: (status: ConnectionStatus) => void;
  setReconnectAttempt: (attempt: { current: number; max: number } | null) => void;
  setProcessing: (processing: boolean, message?: string) => void;
  setOptions: (options: EventOption[]) => void;
  setStoryText: (text: string) => void;
  appendStoryText: (text: string) => void;
  setCurrentEvent: (event: { story: string; options: EventOption[] } | null) => void;
  setGameOver: (gameOver: boolean) => void;
  setRoundSummary: (summary: string | null) => void;
  isGameOver: boolean;
  setIsPrefetching: (prefetching: boolean) => void;
  // Refs passed from parent
  abortRef: React.MutableRefObject<AbortController | null>;
  generatingRef: React.MutableRefObject<boolean>;
  pollingRef: React.MutableRefObject<boolean>;
  prefetchAbortRef: React.MutableRefObject<AbortController | null>;
  prefetchResultRef: React.MutableRefObject<{
    story: string;
    options: EventOption[];
    event: { story: string; options: EventOption[] } | null;
  } | null>;
  prefetchingRef: React.MutableRefObject<boolean>;
  isRetryingRef: React.MutableRefObject<boolean>;
}

/**
 * Hook for generating game events via SSE.
 * Handles event generation, prefetching, and error recovery.
 */
export function useEventGenerator({
  gameId,
  phaseRef,
  setPhase,
  setConnectionStatus,
  setReconnectAttempt,
  setProcessing,
  setOptions,
  setStoryText,
  appendStoryText,
  setCurrentEvent,
  setGameOver,
  setRoundSummary,
  isGameOver,
  setIsPrefetching,
  abortRef,
  generatingRef,
  pollingRef,
  prefetchAbortRef,
  prefetchResultRef,
  prefetchingRef,
  isRetryingRef,
}: UseEventGeneratorParams) {
  const retryStatusTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearRetryStatusTimer = useCallback(() => {
    if (retryStatusTimerRef.current) {
      clearTimeout(retryStatusTimerRef.current);
      retryStatusTimerRef.current = null;
    }
  }, []);

  const armRetryStatusTimeout = useCallback(() => {
    clearRetryStatusTimer();
    retryStatusTimerRef.current = setTimeout(() => {
      if (!isRetryingRef.current) return;
      console.warn("[generateEvent] Retry status timed out, clearing retry guard");
      isRetryingRef.current = false;
      generatingRef.current = false;
      pollingRef.current = false;
      setProcessing(false);
      setConnectionStatus("error");
      setReconnectAttempt(null);
      setRoundSummary(null);
      setPhase("error");
      retryStatusTimerRef.current = null;
    }, 60000);
  }, [
    clearRetryStatusTimer,
    generatingRef,
    isRetryingRef,
    pollingRef,
    setConnectionStatus,
    setPhase,
    setProcessing,
    setReconnectAttempt,
    setRoundSummary,
  ]);

  // Event handlers object for utility functions
  const eventHandlers: EventHandlers = {
    setStoryText,
    setOptions,
    setCurrentEvent,
    setPhase: setPhase as (phase: string) => void,
    setGameOver,
    setRoundSummary,
    setProcessing,
    setConnectionStatus: setConnectionStatus as (status: string | null) => void,
    appendStoryText,
    generatingRef,
    isRetryingRef,
  };

  // Generate event function
  const generateEvent = useCallback(async (options?: { force?: boolean }) => {
    const force = Boolean(options?.force);
    const caller = new Error().stack?.split('\n')[2]?.trim() || 'unknown';
    const state = useGameStore.getState();
    const storyLen = state?.storyText?.length ?? 0;
    console.log(`[generateEvent] Called from: ${caller}`);
    console.log(`[generateEvent] Current state: gameId=${gameId}, phase=${phaseRef.current}, storyLen=${storyLen}, generating=${generatingRef.current}`);

    if (!gameId) {
      console.warn("[generateEvent] Blocked: no gameId");
      return;
    }
    if (generatingRef.current && !force) {
      console.warn("[generateEvent] Blocked: already generating");
      return;
    }
    if (isRetryingRef.current && !force) {
      console.warn("[generateEvent] Blocked: retry in progress within existing SSE stream");
      return;
    }

    const currentPhase = phaseRef.current;
    if (currentPhase !== "loading" && currentPhase !== "error" && !force) {
      console.warn(`[generateEvent] Blocked: current phase is ${currentPhase}`);
      return;
    }

    generatingRef.current = true;
    console.log(`[generateEvent] Starting generation for gameId: ${gameId}`);

    abortRef.current?.abort();
    const storeState = useGameStore.getState();
    const existingStory = storeState?.storyText;
    const currentEvent = storeState?.currentEvent;
    const shouldClearExistingStory = force ||
      currentPhase === "error" ||
      (!currentEvent?.options?.length);

    if (shouldClearExistingStory) {
      console.log("[generateEvent] Clearing existing story for retry/recovery flow");
      setStoryText("");
    } else if (existingStory && existingStory.length > 0) {
      console.log(`[generateEvent] Preserving existing story (${existingStory.length} chars), will append new content`);
    } else {
      setStoryText("");
    }
    setPhase("generating");
    setConnectionStatus(null);
    setReconnectAttempt(null);
    abortRef.current = new AbortController();
    let streamErrorHandled = false;

    try {
      await streamGameEvent(
      gameId,
      {
        onStory: appendStoryText,
        onStatus: (status) => {
          handleStatusUpdate(status, setProcessing, isRetryingRef);
          if (status.phase === "retry" || status.phase === "retrying") {
            armRetryStatusTimeout();
          } else {
            clearRetryStatusTimer();
          }
        },
        onConnectionStatus: (status) => {
          setConnectionStatus(status);
          if (status !== "reconnecting") {
            setReconnectAttempt(null);
          }
        },
        onReconnecting: (attempt, maxRetries) => {
          setReconnectAttempt({ current: attempt, max: maxRetries });
        },
        onComplete: (data) => {
          clearRetryStatusTimer();
          handleEventComplete(data, eventHandlers);
        },
        onError: async (err) => {
          streamErrorHandled = true;
          clearRetryStatusTimer();
          const errorMsg = parseSSEError(err);
          console.log(`[generateEvent] SSE error: msg="${errorMsg}"`);

          if (errorMsg.includes("404") || errorMsg.includes("No active game session")) {
            console.log("[generateEvent] Session expired, restoring and regenerating...");
            try {
              setProcessing(true, "恢复游戏状态...");
              await useGameStore.getState()?.syncPlayerState?.();
              generatingRef.current = false;
              setProcessing(false);
              setPhase("loading");
              setTimeout(() => generateEvent(), 100);
              return;
            } catch (restoreErr) {
              const restoreErrorMsg = String((restoreErr as Error)?.message || restoreErr);
              console.error("[generateEvent] Failed to restore session:", restoreErr);

              if (restoreErrorMsg.includes("not found") || restoreErrorMsg.includes("404")) {
                console.warn("[generateEvent] Game no longer exists, redirecting to home...");
                setProcessing(false);
                setPhase("error");
                return;
              }
            }
          }

          const isTimeout = errorMsg.includes("Timeout waiting for event generation");
          const isRecoverable = errorMsg === "Unknown error" || errorMsg === "undefined" || isTimeout;

          if (!errorMsg.includes("404") && !isRecoverable) {
            console.error("SSE final error:", err);
          } else if (isRecoverable) {
            console.warn("[generateEvent] SSE connection interrupted or timed out, will start polling...");
          }

          if (pollingRef.current) {
            console.warn("[Polling] Blocked: already polling");
            return;
          }
          pollingRef.current = true;

          console.log("SSE failed, starting polling...");
          setProcessing(true, "generating_story");
          setConnectionStatus(null);

          const maxPollingTime = 180000;  // 3分钟，改善用户体验
          const pollInterval = 5000;      // 5秒，更快检测完成状态
          const startTime = Date.now();
          let recoveredPartialStory = "";

          const pollForCompletion = async (): Promise<boolean> => {
            try {
              await useGameStore.getState()?.syncState?.();
              const state = useGameStore.getState();

              if (state?.currentEvent?.options?.length) {
                setOptions(state.currentEvent.options);
                setCurrentEvent({
                  ...state.currentEvent,
                  story: useGameStore.getState()?.storyText || state.currentEvent.story,
                });
                setPhase("options");
                setProcessing(false);
                generatingRef.current = false;
                pollingRef.current = false;
                setRoundSummary(null);
                return true;
              }

              const partialStory =
                state?.currentEvent?.story ||
                state?.storyText ||
                "";
              if (partialStory.trim()) {
                recoveredPartialStory = partialStory;
                setStoryText(partialStory);
                setCurrentEvent({
                  story: partialStory,
                  options: [],
                });
              }
              return false;
            } catch (pollErr) {
              console.error("Polling error:", pollErr);
              return false;
            }
          };

          if (await pollForCompletion()) return;

          while (Date.now() - startTime < maxPollingTime) {
            await new Promise(resolve => setTimeout(resolve, pollInterval));
            if (await pollForCompletion()) return;
            console.log(`Polling... (${Math.round((Date.now() - startTime) / 1000)}s elapsed)`);
          }

          console.warn("Polling timeout after 3 minutes, entering error state");
          setProcessing(false);
          setConnectionStatus("error");
          generatingRef.current = false;
          pollingRef.current = false;
          isRetryingRef.current = false;
          if (recoveredPartialStory.trim()) {
            setStoryText(recoveredPartialStory);
            setCurrentEvent({
              story: recoveredPartialStory,
              options: [],
            });
          }
          setPhase("error");
        },
      },
      { signal: abortRef.current.signal }
    );
    } catch (err) {
      // Ignore AbortError - it's expected when component unmounts or user navigates away
      if (err instanceof Error && err.name === 'AbortError') {
        console.log("[generateEvent] Generation aborted (expected)");
      } else if (streamErrorHandled || pollingRef.current) {
        console.warn("[generateEvent] streamGameEvent rejection already handled by polling recovery");
      } else {
        throw err; // Re-throw other errors
      }
    }
  }, [gameId, setStoryText, appendStoryText, setProcessing, setCurrentEvent, setGameOver, setPhase, phaseRef, setConnectionStatus, setReconnectAttempt, setOptions, setRoundSummary, armRetryStatusTimeout, clearRetryStatusTimer]);

  const recoverEventGeneration = useCallback(async () => {
    abortRef.current?.abort();
    prefetchAbortRef.current?.abort();
    generatingRef.current = false;
    pollingRef.current = false;
    prefetchingRef.current = false;
    isRetryingRef.current = false;
    clearRetryStatusTimer();
    prefetchResultRef.current = null;
    setIsPrefetching(false);
    setProcessing(false);
    setConnectionStatus(null);
    setReconnectAttempt(null);
    setOptions([]);
    phaseRef.current = "loading";
    setPhase("loading");
    await generateEvent({ force: true });
  }, [
    abortRef,
    prefetchAbortRef,
    generatingRef,
    pollingRef,
    prefetchingRef,
    isRetryingRef,
    prefetchResultRef,
    setIsPrefetching,
    setProcessing,
    setConnectionStatus,
    setReconnectAttempt,
    setOptions,
    phaseRef,
    setPhase,
    clearRetryStatusTimer,
    generateEvent,
  ]);

  // Prefetch next event (background generation)
  const prefetchNextEvent = useCallback(async () => {
    if (!gameId) return;
    if (prefetchingRef.current) {
      console.log("[prefetch] Already prefetching, skip");
      return;
    }

    console.log("[prefetch] Starting prefetch for next event...");
    prefetchingRef.current = true;
    setIsPrefetching(true);
    prefetchResultRef.current = null;

    prefetchAbortRef.current?.abort();
    prefetchAbortRef.current = new AbortController();

    let prefetchedStory = "";
    let prefetchedOptions: EventOption[] = [];

    try {
      await useGameStore.getState()?.syncPlayerState?.();

      await streamGameEvent(
        gameId,
        {
          onStory: (chunk) => {
            prefetchedStory += chunk;
          },
          onComplete: (data) => {
            const receivedOptions = data.options as EventOption[] | undefined;
            if (receivedOptions?.length) {
              prefetchedOptions = receivedOptions;
              prefetchResultRef.current = {
                story: prefetchedStory,
                options: prefetchedOptions,
                event: { story: prefetchedStory, options: prefetchedOptions },
              };
              console.log(`[prefetch] Prefetch complete! story=${prefetchedStory.length} chars, options=${prefetchedOptions.length}`);
            }
          },
          onError: (err) => {
            console.warn("[prefetch] Prefetch failed:", err.message);
            prefetchResultRef.current = null;
          },
        },
        { signal: prefetchAbortRef.current.signal }
      );
    } catch (err) {
      // Ignore AbortError - it's expected when component unmounts or effect re-runs
      if (err instanceof Error && err.name === 'AbortError') {
        console.log("[prefetch] Prefetch aborted (expected)");
      } else {
        console.warn("[prefetch] Prefetch error:", err);
      }
      prefetchResultRef.current = null;
    } finally {
      prefetchingRef.current = false;
      setIsPrefetching(false);
    }
  }, [gameId, setIsPrefetching]);

  // Effect: prefetch when entering result phase
  useEffect(() => {
    if (phaseRef.current === "result" && !isGameOver && gameId) {
      console.log("[prefetch] Entered result phase, starting prefetch...");
      const timer = setTimeout(() => {
        prefetchNextEvent();
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [phaseRef, isGameOver, gameId, prefetchNextEvent]);

  // Cleanup effect
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      prefetchAbortRef.current?.abort();
      generatingRef.current = false;
      pollingRef.current = false;
      prefetchingRef.current = false;
      isRetryingRef.current = false;
      clearRetryStatusTimer();
    };
  }, [abortRef, prefetchAbortRef, generatingRef, pollingRef, prefetchingRef, isRetryingRef, clearRetryStatusTimer]);

  return {
    generateEvent,
    recoverEventGeneration,
    prefetchNextEvent,
  };
}
