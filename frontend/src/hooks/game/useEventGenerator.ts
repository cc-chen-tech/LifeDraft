"use client";

import { useCallback, useEffect } from "react";
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
}: UseEventGeneratorParams) {
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
  };

  // Generate event function
  const generateEvent = useCallback(async () => {
    const caller = new Error().stack?.split('\n')[2]?.trim() || 'unknown';
    const state = useGameStore.getState();
    const storyLen = state?.storyText?.length ?? 0;
    console.log(`[generateEvent] Called from: ${caller}`);
    console.log(`[generateEvent] Current state: gameId=${gameId}, phase=${phaseRef.current}, storyLen=${storyLen}, generating=${generatingRef.current}`);

    if (!gameId) {
      console.warn("[generateEvent] Blocked: no gameId");
      return;
    }
    if (generatingRef.current) {
      console.warn("[generateEvent] Blocked: already generating");
      return;
    }

    const currentPhase = phaseRef.current;
    if (currentPhase !== "loading" && currentPhase !== "error") {
      console.warn(`[generateEvent] Blocked: current phase is ${currentPhase}`);
      return;
    }

    generatingRef.current = true;
    console.log(`[generateEvent] Starting generation for gameId: ${gameId}`);

    abortRef.current?.abort();
    // ★ 不无条件清空故事：如果已有故事内容，保留并继续流式追加；只有为空时才清空
    const existingStory = useGameStore.getState()?.storyText;
    if (existingStory && existingStory.length > 0) {
      console.log(`[generateEvent] Preserving existing story (${existingStory.length} chars), will append new content`);
    } else {
      setStoryText("");
    }
    setPhase("generating");
    setConnectionStatus(null);
    setReconnectAttempt(null);
    abortRef.current = new AbortController();

    try {
      await streamGameEvent(
      gameId,
      {
        onStory: appendStoryText,
        onStatus: (status) => handleStatusUpdate(status, setProcessing),
        onConnectionStatus: (status) => {
          setConnectionStatus(status);
          if (status !== "reconnecting") {
            setReconnectAttempt(null);
          }
        },
        onReconnecting: (attempt, maxRetries) => {
          setReconnectAttempt({ current: attempt, max: maxRetries });
        },
        onComplete: (data) => handleEventComplete(data, eventHandlers),
        onError: async (err) => {
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

          if (!errorMsg.includes("404") && errorMsg !== "undefined" && errorMsg !== "Unknown error") {
            console.error("SSE final error:", err);
          } else if (errorMsg === "Unknown error" || errorMsg === "undefined") {
            console.warn("[generateEvent] SSE connection interrupted, will start polling...");
          }

          if (pollingRef.current) {
            console.warn("[Polling] Blocked: already polling");
            return;
          }
          pollingRef.current = true;

          console.log("SSE failed, starting polling...");
          setProcessing(true, "generating_story");
          setConnectionStatus(null);

          const maxPollingTime = 120000;
          const pollInterval = 10000;
          const startTime = Date.now();

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

          console.error("Polling timeout");
          setProcessing(false);
          setConnectionStatus("error");
          generatingRef.current = false;
          pollingRef.current = false;
          setPhase("error");
        },
      },
      { signal: abortRef.current.signal }
    );
    } catch (err) {
      // Ignore AbortError - it's expected when component unmounts or user navigates away
      if (err instanceof Error && err.name === 'AbortError') {
        console.log("[generateEvent] Generation aborted (expected)");
      } else {
        throw err; // Re-throw other errors
      }
    }
  }, [gameId, setStoryText, appendStoryText, setProcessing, setCurrentEvent, setGameOver, setPhase, phaseRef, setConnectionStatus, setReconnectAttempt, setOptions, setRoundSummary]);

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
    };
  }, []);

  return {
    generateEvent,
    prefetchNextEvent,
  };
}
