"use client";

import { useCallback, useEffect, useRef } from "react";
import { useGameStore } from "@/stores/useGameStore";
import { streamGameEvent } from "@/lib/sse";
import type { GenerationFailurePayload, StreamActivityKind } from "@/lib/sse";
import type { EventOption, StoryDeliveryNotice } from "@/lib/types";
import type { Phase, ConnectionStatus } from "./usePhaseManager";
import type {
  NarrativeLoadingOperation,
  NarrativeTransportState,
} from "@/components/narrative-loading/NarrativeLoadingState";
import { handleEventComplete, handleStatusUpdate, type EventHandlers } from "./eventUtils";
import { parseSSEError } from "./choiceUtils";
import {
  fetchGameplayStateSnapshot,
  fetchPersistedEventSnapshot,
  type PersistedEventSnapshot,
} from "./eventRecovery";
import {
  abortableSleep,
  beginGameplayRun,
  invalidateGameplayRun,
  isAbortError,
} from "./gameplayRun";
import type { DailyGenerationCommandState } from "./dailyGenerationCommand";

export const EVENT_INACTIVITY_TIMEOUT_MS = 45_000;
export const EVENT_POLL_INTERVAL_MS = 5_000;
export const EVENT_POLL_TIMEOUT_MS = 180_000;

interface UseEventGeneratorParams {
  gameId: number | null;
  phaseRef: React.MutableRefObject<Phase>;
  setPhase: (phase: Phase | ((prev: Phase) => Phase)) => void;
  setConnectionStatus: (status: ConnectionStatus) => void;
  setReconnectAttempt: (attempt: { current: number; max: number } | null) => void;
  setTransport: (transport: NarrativeTransportState) => void;
  setLoadingOperation: (operation: NarrativeLoadingOperation) => void;
  setLoadingIdentity: React.Dispatch<React.SetStateAction<number>>;
  setProcessing: (processing: boolean, message?: string) => void;
  setOptions: (options: EventOption[]) => void;
  setStoryText: (text: string) => void;
  appendStoryText: (text: string) => void;
  setCurrentEvent: (event: { story: string; options: EventOption[]; event_id?: string; revision?: number; story_date?: string; delivery_notice?: StoryDeliveryNotice } | null) => void;
  setGameOver: (gameOver: boolean) => void;
  setRoundSummary: (summary: string | null) => void;
  setRegenerationFailure?: (failure: GenerationFailurePayload | null) => void;
  setIsPrefetching: (prefetching: boolean) => void;
  runTokenRef: React.MutableRefObject<number>;
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
  setDailyGenerationCommand?: React.Dispatch<React.SetStateAction<DailyGenerationCommandState>>;
}

interface GenerateEventOptions {
  resume?: boolean;
  recoveryDepth?: 0 | 1;
  userInitiated?: boolean;
}

function isRecoverableEventStreamError(errorMessage: string): boolean {
  const normalized = errorMessage.toLowerCase();
  const httpStatus = Number.parseInt(normalized.match(/status:\s*(\d{3})/)?.[1] ?? "", 10);
  return (
    (Number.isFinite(httpStatus) && httpStatus >= 500) ||
    errorMessage === "Unknown error" ||
    errorMessage === "undefined" ||
    normalized.includes("timeout waiting for event generation") ||
    normalized.includes("network error") ||
    normalized.includes("failed to fetch") ||
    normalized.includes("empty_response") ||
    normalized.includes("incomplete_chunked_encoding") ||
    normalized.includes("terminated") ||
    normalized.includes("stream ended")
  );
}

export function useEventGenerator({
  gameId,
  phaseRef,
  setPhase,
  setConnectionStatus,
  setReconnectAttempt,
  setTransport,
  setLoadingOperation,
  setLoadingIdentity,
  setProcessing,
  setOptions,
  setStoryText,
  appendStoryText,
  setCurrentEvent,
  setGameOver,
  setRoundSummary,
  setRegenerationFailure,
  setIsPrefetching,
  runTokenRef,
  abortRef,
  generatingRef,
  pollingRef,
  prefetchAbortRef,
  prefetchResultRef,
  prefetchingRef,
  isRetryingRef,
  setDailyGenerationCommand,
}: UseEventGeneratorParams) {
  const watchdogCleanupRef = useRef<(() => void) | null>(null);
  const eventCursorStorageKey = gameId === null ? null : `story101:event-cursor:${gameId}`;
  const eventStoryStorageKey = gameId === null ? null : `story101:event-story:${gameId}`;
  const lastEventIdRef = useRef<number | null>(null);

  const clearDurableResume = useCallback(() => {
    lastEventIdRef.current = null;
    if (eventCursorStorageKey) window.sessionStorage.removeItem(eventCursorStorageKey);
    if (eventStoryStorageKey) window.sessionStorage.removeItem(eventStoryStorageKey);
  }, [eventCursorStorageKey, eventStoryStorageKey]);

  useEffect(() => {
    if (!eventCursorStorageKey || !eventStoryStorageKey) {
      lastEventIdRef.current = null;
      return;
    }

    const storedCursor = window.sessionStorage.getItem(eventCursorStorageKey);
    const parsedCursor = storedCursor === null ? Number.NaN : Number.parseInt(storedCursor, 10);
    const storedStory = window.sessionStorage.getItem(eventStoryStorageKey) || "";
    if (Number.isFinite(parsedCursor) && storedStory) {
      lastEventIdRef.current = parsedCursor;
      if (!useGameStore.getState().storyText) setStoryText(storedStory);
      return;
    }

    lastEventIdRef.current = null;
    window.sessionStorage.removeItem(eventCursorStorageKey);
    window.sessionStorage.removeItem(eventStoryStorageKey);
  }, [eventCursorStorageKey, eventStoryStorageKey, setStoryText]);

  const generateEvent = useCallback(async (options?: GenerateEventOptions) => {
    const resume = Boolean(options?.resume);
    const userInitiated = Boolean(options?.userInitiated);
    const recoveryDepth: 0 | 1 = options?.recoveryDepth ?? (resume ? 1 : 0);
    const state = useGameStore.getState();

    if (!gameId) return;
    if (generatingRef.current && !resume) return;
    if (isRetryingRef.current && !resume) return;
    if (
      phaseRef.current !== "loading"
      && phaseRef.current !== "error"
      && !resume
      && !userInitiated
    ) return;

    if (!resume) {
      setDailyGenerationCommand?.({
        status: "starting",
        mode: "generate_missing",
        operationId: null,
        attempt: null,
        maxAttempts: null,
        failure: null,
      });
    }

    setLoadingOperation("event");
    watchdogCleanupRef.current?.();
    const run = beginGameplayRun(runTokenRef, abortRef);
    const { controller, isCurrent, isLive } = run;
    if (resume) {
      setTransport("reconnecting");
    } else {
      setLoadingIdentity((identity) => identity + 1);
      setTransport("active");
    }

    generatingRef.current = true;
    pollingRef.current = false;
    isRetryingRef.current = false;

    const currentPhase = phaseRef.current;
    const currentEvent = state.currentEvent;
    if (!resume) {
      clearDurableResume();
      if (
        userInitiated
        || currentPhase === "error"
        || !currentEvent?.options?.length
      ) setStoryText("");
    }

    setPhase("generating");
    setConnectionStatus(null);
    setReconnectAttempt(null);

    let inactivityTimer: ReturnType<typeof setTimeout> | null = null;
    let terminal = false;
    let errorHandlingPromise: Promise<void> | null = null;
    let errorHandled = false;
    const hadRetryRef = { current: false };

    const clearWatchdog = () => {
      if (inactivityTimer !== null) {
        clearTimeout(inactivityTimer);
        inactivityTimer = null;
      }
    };
    watchdogCleanupRef.current = clearWatchdog;
    controller.signal.addEventListener("abort", clearWatchdog, { once: true });

    const guard = <Args extends unknown[]>(callback: (...args: Args) => void) =>
      (...args: Args) => {
        if (!isLive()) return;
        callback(...args);
      };

    const finishAsFailed = (failure?: GenerationFailurePayload) => {
      if (!isLive()) return;
      terminal = true;
      clearWatchdog();
      generatingRef.current = false;
      pollingRef.current = false;
      isRetryingRef.current = false;
      setProcessing(false);
      setConnectionStatus("error");
      setReconnectAttempt(null);
      setRoundSummary(null);
      setTransport("failed");
      setPhase("error");
      setDailyGenerationCommand?.((current) => ({
        ...current,
        status: "failed",
        mode: "generate_missing",
        operationId: failure?.operation_id || current.operationId,
        failure: failure || {
          message: "故事生成未能完成",
          summary: "故事生成未能完成",
          retryable: true,
        },
      }));
    };

    const commitPersistedCompletion = (
      snapshot: PersistedEventSnapshot,
      completedStory?: string,
    ) => {
      if (!isLive()) return;
      const story = completedStory || snapshot.story;
      terminal = true;
      clearWatchdog();
      if (story.trim()) setStoryText(story);
      setOptions(snapshot.options);
      setCurrentEvent({
        story,
        options: snapshot.options,
        ...(snapshot.delivery_notice
          ? { delivery_notice: snapshot.delivery_notice }
          : {}),
      });
      setProcessing(false);
      setConnectionStatus(null);
      setReconnectAttempt(null);
      setRoundSummary(null);
      generatingRef.current = false;
      pollingRef.current = false;
      isRetryingRef.current = false;
      clearDurableResume();
      setTransport("active");
      setPhase("options");
      setDailyGenerationCommand?.((current) => ({
        ...current,
        status: "succeeded",
        mode: "generate_missing",
        failure: null,
      }));
    };

    const commitPersistedGameOver = () => {
      if (!isLive()) return;
      terminal = true;
      clearWatchdog();
      setProcessing(false);
      setConnectionStatus(null);
      setReconnectAttempt(null);
      setRoundSummary(null);
      generatingRef.current = false;
      pollingRef.current = false;
      isRetryingRef.current = false;
      clearDurableResume();
      setGameOver(true);
      setTransport("active");
      setPhase("ending");
    };

    const pollForCompletion = async (): Promise<void> => {
      if (!isLive()) return;
      terminal = true;
      clearWatchdog();
      pollingRef.current = true;
      setTransport("polling");
      setProcessing(true, "generating_story");
      setConnectionStatus(null);

      const deadline = Date.now() + EVENT_POLL_TIMEOUT_MS;
      let recoveredPartialStory = "";

      while (isLive()) {
        const remainingRequestTime = deadline - Date.now();
        if (remainingRequestTime <= 0) break;
        try {
          const snapshot = await fetchPersistedEventSnapshot(
            gameId,
            controller.signal,
            remainingRequestTime,
          );
          if (!isLive()) return;

          if (snapshot?.gameOver) {
            commitPersistedGameOver();
            return;
          }

          if (snapshot?.options.length) {
            const completedStory = snapshot.story.trim()
              ? snapshot.story
              : recoveredPartialStory || useGameStore.getState().storyText;
            if (completedStory.trim()) {
              commitPersistedCompletion(snapshot, completedStory);
              return;
            }
          }

          if (snapshot?.story.trim()) {
            recoveredPartialStory = snapshot.story;
            setStoryText(snapshot.story);
            setCurrentEvent({
              story: snapshot.story,
              options: [],
              ...(snapshot.delivery_notice
                ? { delivery_notice: snapshot.delivery_notice }
                : {}),
            });
          }
        } catch (pollError) {
          if (!isLive() || isAbortError(pollError)) return;
          console.warn("[generateEvent] Persisted-event polling failed:", pollError);
        }

        if (!isLive()) return;
        if (Date.now() >= deadline) break;
        const remaining = Math.max(0, deadline - Date.now());
        try {
          await abortableSleep(Math.min(EVENT_POLL_INTERVAL_MS, remaining), controller.signal);
        } catch (sleepError) {
          if (!isLive() || isAbortError(sleepError)) return;
          throw sleepError;
        }
        if (!isLive()) return;
      }

      if (!isLive()) return;
      if (recoveredPartialStory.trim()) {
        setStoryText(recoveredPartialStory);
        setCurrentEvent({ story: recoveredPartialStory, options: [] });
      }
      finishAsFailed();
    };

    const beginRecovery = () => {
      if (!isLive()) return;
      clearWatchdog();
      if (recoveryDepth === 0) {
        setTransport("reconnecting");
        void generateEvent({ resume: true, recoveryDepth: 1 });
        return;
      }
      void pollForCompletion();
    };

    const armWatchdog = () => {
      clearWatchdog();
      if (!isLive() || terminal) return;
      inactivityTimer = setTimeout(() => {
        inactivityTimer = null;
        if (!isLive() || terminal) return;
        beginRecovery();
      }, EVENT_INACTIVITY_TIMEOUT_MS);
    };

    const touchActivity = () => {
      if (!isLive() || terminal) return;
      setTransport("active");
      setReconnectAttempt(null);
      armWatchdog();
    };

    const handle404 = async (): Promise<void> => {
      if (!isLive()) return;
      try {
        setProcessing(true, "恢复游戏状态...");
        const snapshot = await fetchPersistedEventSnapshot(
          gameId,
          controller.signal,
          EVENT_INACTIVITY_TIMEOUT_MS,
        );
        if (!isLive()) return;
        if (snapshot?.gameOver) {
          commitPersistedGameOver();
          return;
        }
        if (snapshot?.options.length) {
          const completedStory = snapshot.story || useGameStore.getState().storyText;
          if (completedStory.trim()) {
            commitPersistedCompletion(snapshot, completedStory);
            return;
          }
        }
        setProcessing(false);
        generatingRef.current = false;
        phaseRef.current = "loading";
        setPhase("loading");
        await abortableSleep(100, controller.signal);
        if (!isLive()) return;
        void generateEvent({ resume: false, recoveryDepth: 0 });
      } catch (restoreError) {
        if (!isLive() || isAbortError(restoreError)) return;
        const restoreMessage = parseSSEError(restoreError).toLowerCase();
        if (restoreMessage.includes("404") || restoreMessage.includes("not found")) {
          finishAsFailed();
          return;
        }
        finishAsFailed();
      }
    };

    const handleStreamError = async (error: unknown): Promise<void> => {
      if (!isLive() || isAbortError(error)) return;
      clearWatchdog();
      const errorMessage = parseSSEError(error);
      if (errorMessage.includes("404") || errorMessage.includes("No active game session")) {
        await handle404();
        return;
      }
      if (isRecoverableEventStreamError(errorMessage)) {
        beginRecovery();
        return;
      }
      const failure = !(error instanceof Error) && error && typeof error === "object"
        ? error as GenerationFailurePayload
        : {
            message: errorMessage,
            summary: errorMessage,
            retryable: true,
          };
      finishAsFailed(failure);
    };

    const dispatchStreamError = (error: unknown): Promise<void> => {
      if (!isLive() || isAbortError(error)) return Promise.resolve();
      if (errorHandled) return errorHandlingPromise ?? Promise.resolve();
      errorHandled = true;
      terminal = true;
      clearWatchdog();
      errorHandlingPromise = handleStreamError(error);
      return errorHandlingPromise;
    };

    const eventHandlers: EventHandlers = {
      setStoryText: guard(setStoryText),
      setOptions: guard(setOptions),
      setCurrentEvent: guard(setCurrentEvent),
      setPhase: guard(setPhase as (phase: string) => void),
      setGameOver: guard(setGameOver),
      setRoundSummary: guard(setRoundSummary),
      setProcessing: guard(setProcessing),
      setConnectionStatus: guard(setConnectionStatus as (status: string | null) => void),
      appendStoryText: guard(appendStoryText),
      generatingRef,
      isRetryingRef,
      hadRetryRef,
      isCurrentRun: isCurrent,
      setTransport: guard(setTransport),
    };

    armWatchdog();
    try {
      await streamGameEvent(
        gameId,
        {
          onStory: (text) => {
            if (!isLive() || terminal) return;
            touchActivity();
            setDailyGenerationCommand?.((current) => ({
              ...current,
              status: "running",
              mode: "generate_missing",
              failure: null,
            }));
            appendStoryText(text);
          },
          onEventId: (eventId) => {
            if (!isLive() || terminal) return;
            lastEventIdRef.current = eventId;
            if (eventCursorStorageKey) {
              window.sessionStorage.setItem(eventCursorStorageKey, String(eventId));
            }
            if (eventStoryStorageKey) {
              window.sessionStorage.setItem(eventStoryStorageKey, useGameStore.getState().storyText);
            }
          },
          onStatus: (status) => {
            if (!isLive() || terminal) return;
            touchActivity();
            setDailyGenerationCommand?.((current) => ({
              ...current,
              status: "running",
              mode: status.resolved_mode === "replace_current"
                ? "replace_current"
                : "generate_missing",
              operationId: status.operation_id || current.operationId,
              attempt: typeof status.attempt === "number" ? status.attempt : current.attempt,
              maxAttempts: typeof status.max_attempts === "number"
                ? status.max_attempts
                : current.maxAttempts,
              failure: null,
            }));
            handleStatusUpdate(status, setProcessing, isRetryingRef, () => {
              hadRetryRef.current = true;
              clearDurableResume();
              setStoryText("");
            });
          },
          onActivity: (kind: StreamActivityKind) => {
            if (!isLive()) return;
            if (kind === "complete" || kind === "error") clearWatchdog();
          },
          onConnectionStatus: (status) => {
            if (!isLive() || terminal) return;
            setConnectionStatus(status);
            if (status === "reconnecting") setTransport("reconnecting");
            if (status !== "reconnecting") setReconnectAttempt(null);
          },
          onReconnecting: (attempt, maxRetries) => {
            if (!isLive() || terminal) return;
            setTransport("reconnecting");
            setReconnectAttempt({ current: attempt, max: maxRetries });
          },
          onComplete: (data) => {
            if (!isLive() || terminal) return;
            terminal = true;
            clearWatchdog();
            const valid = handleEventComplete(data, eventHandlers);
            if (valid && isCurrent()) {
              clearDurableResume();
              setDailyGenerationCommand?.((current) => ({
                ...current,
                status: "succeeded",
                mode: "generate_missing",
                failure: null,
              }));
            }
          },
          onError: (error) => {
            if (!(error instanceof Error) && error.code) {
              setRegenerationFailure?.(error);
            }
            void dispatchStreamError(error);
          },
        },
        {
          signal: controller.signal,
          lastEventId: resume ? lastEventIdRef.current ?? -1 : undefined,
        },
      );
      if (errorHandlingPromise) await errorHandlingPromise;
    } catch (error) {
      if (!isCurrent() || controller.signal.aborted || isAbortError(error)) return;
      await dispatchStreamError(error);
    }
  }, [
    abortRef,
    appendStoryText,
    clearDurableResume,
    eventCursorStorageKey,
    eventStoryStorageKey,
    gameId,
    generatingRef,
    isRetryingRef,
    phaseRef,
    pollingRef,
    runTokenRef,
    setConnectionStatus,
    setCurrentEvent,
    setGameOver,
    setLoadingIdentity,
    setOptions,
    setPhase,
    setProcessing,
    setReconnectAttempt,
    setRoundSummary,
    setRegenerationFailure,
    setStoryText,
    setTransport,
    setLoadingOperation,
    setDailyGenerationCommand,
  ]);

  const recoverEventGeneration = useCallback(async () => {
    watchdogCleanupRef.current?.();
    invalidateGameplayRun(runTokenRef, abortRef);
    prefetchAbortRef.current?.abort();
    generatingRef.current = false;
    pollingRef.current = false;
    prefetchingRef.current = false;
    isRetryingRef.current = false;
    prefetchResultRef.current = null;
    setIsPrefetching(false);
    setProcessing(false);
    setConnectionStatus(null);
    setReconnectAttempt(null);
    setTransport("reconnecting");
    phaseRef.current = "generating";
    setPhase("generating");
    await generateEvent({ resume: true, recoveryDepth: 1 });
  }, [
    abortRef,
    generateEvent,
    generatingRef,
    isRetryingRef,
    phaseRef,
    pollingRef,
    prefetchAbortRef,
    prefetchResultRef,
    prefetchingRef,
    runTokenRef,
    setConnectionStatus,
    setIsPrefetching,
    setPhase,
    setProcessing,
    setReconnectAttempt,
    setTransport,
  ]);

  const prefetchNextEvent = useCallback(async () => {
    if (!gameId || prefetchingRef.current) return;
    prefetchingRef.current = true;
    setIsPrefetching(true);
    prefetchResultRef.current = null;

    prefetchAbortRef.current?.abort();
    const controller = new AbortController();
    prefetchAbortRef.current = controller;
    const isCurrentPrefetch = () =>
      prefetchAbortRef.current === controller && !controller.signal.aborted;
    let prefetchedStory = "";

    try {
      // This probe is intentionally read-only. A superseded prefetch must not
      // write session/event stores before its captured signal is rechecked.
      await fetchGameplayStateSnapshot(
        gameId,
        controller.signal,
        EVENT_INACTIVITY_TIMEOUT_MS,
      );
      if (!isCurrentPrefetch()) return;
      await streamGameEvent(
        gameId,
        {
          onStory: (chunk) => {
            if (isCurrentPrefetch()) prefetchedStory += chunk;
          },
          onComplete: (data) => {
            if (!isCurrentPrefetch()) return;
            const prefetchedOptions = data.options as EventOption[] | undefined;
            if (prefetchedOptions?.length) {
              prefetchResultRef.current = {
                story: prefetchedStory,
                options: prefetchedOptions,
                event: { story: prefetchedStory, options: prefetchedOptions },
              };
            }
          },
          onError: () => {
            if (isCurrentPrefetch()) prefetchResultRef.current = null;
          },
        },
        { signal: controller.signal },
      );
    } catch (error) {
      if (isCurrentPrefetch() && !isAbortError(error)) {
        console.warn("[prefetch] Prefetch error:", error);
        prefetchResultRef.current = null;
      }
    } finally {
      if (prefetchAbortRef.current === controller) {
        prefetchAbortRef.current = null;
        prefetchingRef.current = false;
        setIsPrefetching(false);
      }
    }
  }, [gameId, prefetchAbortRef, prefetchResultRef, prefetchingRef, setIsPrefetching]);

  useEffect(() => {
    return () => {
      watchdogCleanupRef.current?.();
      invalidateGameplayRun(runTokenRef, abortRef);
      prefetchAbortRef.current?.abort();
      generatingRef.current = false;
      pollingRef.current = false;
      prefetchingRef.current = false;
      isRetryingRef.current = false;
    };
  }, [abortRef, gameId, generatingRef, isRetryingRef, pollingRef, prefetchAbortRef, prefetchingRef, runTokenRef]);

  return { generateEvent, recoverEventGeneration, prefetchNextEvent };
}
