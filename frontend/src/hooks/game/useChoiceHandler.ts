"use client";

import { useEffect, useRef } from "react";
import { useGameStore, useSessionStore } from "@/stores/useGameStore";
import { streamChoice, streamCustomChoice } from "@/lib/sse";
import type { StreamActivityKind } from "@/lib/sse";
import type { EventOption } from "@/lib/types";
import type { Phase, ConnectionStatus } from "./usePhaseManager";
import type { NarrativeTransportState } from "@/components/narrative-loading/NarrativeLoadingState";
import {
  handleChoiceComplete,
  handleChoiceError,
  isRecoverableChoiceStreamError,
  parseSSEError,
  type ChoiceHandlers,
} from "./choiceUtils";
import { fetchGameplayStateSnapshot } from "./eventRecovery";
import {
  abortableSleep,
  beginGameplayRun,
  invalidateGameplayRun,
  isAbortError,
} from "./gameplayRun";

export const CHOICE_INACTIVITY_TIMEOUT_MS = 45_000;
export const CHOICE_RECOVERY_POLL_INTERVAL_MS = 5_000;
export const CHOICE_RECOVERY_TIMEOUT_MS = 180_000;

interface UseChoiceHandlerParams {
  gameId: number | null;
  runTokenRef: React.MutableRefObject<number>;
  abortRef: React.MutableRefObject<AbortController | null>;
  generatingRef: React.MutableRefObject<boolean>;
  setPhase: (phase: Phase | ((prev: Phase) => Phase)) => void;
  setConnectionStatus: (status: ConnectionStatus) => void;
  setReconnectAttempt: (attempt: { current: number; max: number } | null) => void;
  setTransport: (transport: NarrativeTransportState) => void;
  setLoadingIdentity: React.Dispatch<React.SetStateAction<number>>;
  setProcessing: (processing: boolean, message?: string) => void;
  appendStoryText: (text: string) => void;
  setCurrentEvent: (event: { story: string; options: EventOption[] } | null) => void;
  setGameOver: (gameOver: boolean) => void;
  setSummaryText: (text: string) => void;
  setRoundSummary: (summary: string | null) => void;
  setOptions: (options: EventOption[]) => void;
  setStoryText: (text: string) => void;
}

type ChoiceOperation =
  | { kind: "normal"; optionIndex: number; isRetry: boolean }
  | { kind: "custom"; customText: string };

interface StartChoiceOptions {
  baseStory?: string;
  sessionRetry?: boolean;
}

interface ChoiceRecoveryTarget {
  operation: ChoiceOperation;
  baseStory: string;
  choiceText: string;
}

/**
 * Handles normal and custom choice streams. Event generation and choice streams
 * receive the same runTokenRef from usePlayGame, so a newer operation owns every
 * callback, timer, and fallback commit regardless of which hook created it.
 */
export function useChoiceHandler({
  gameId,
  runTokenRef,
  abortRef,
  generatingRef,
  setPhase,
  setConnectionStatus,
  setReconnectAttempt,
  setTransport,
  setLoadingIdentity,
  setProcessing,
  appendStoryText,
  setCurrentEvent,
  setGameOver,
  setSummaryText,
  setRoundSummary,
  setOptions,
  setStoryText,
}: UseChoiceHandlerParams) {
  const watchdogCleanupRef = useRef<(() => void) | null>(null);
  const recoveryTargetRef = useRef<ChoiceRecoveryTarget | null>(null);

  useEffect(() => () => {
    watchdogCleanupRef.current?.();
    invalidateGameplayRun(runTokenRef, abortRef);
  }, [abortRef, gameId, runTokenRef]);

  const commitSessionFields = (
    snapshot: Awaited<ReturnType<typeof fetchGameplayStateSnapshot>>,
    isLive: () => boolean,
  ) => {
    if (!isLive()) return;
    if (snapshot.playerState) {
      useSessionStore.setState({ playerState: snapshot.playerState });
      useGameStore.setState({ playerState: snapshot.playerState });
    }
    if (snapshot.progress) {
      useSessionStore.setState({ progress: snapshot.progress });
      useGameStore.setState({ progress: snapshot.progress });
    }
    if (snapshot.roundInfo) {
      useSessionStore.setState({ roundInfo: snapshot.roundInfo });
      useGameStore.setState({ roundInfo: snapshot.roundInfo });
    }
  };

  const reconcileChoiceTarget = async (
    target: ChoiceRecoveryTarget,
    run: {
      controller: AbortController;
      isCurrent: () => boolean;
      isLive: () => boolean;
    },
  ): Promise<void> => {
    if (!gameId || !run.isLive()) return;
    const { controller, isLive } = run;
    const deadline = Date.now() + CHOICE_RECOVERY_TIMEOUT_MS;

    const finishFailed = () => {
      if (!isLive()) return;
      generatingRef.current = false;
      setProcessing(false);
      setConnectionStatus("error");
      setReconnectAttempt(null);
      setTransport("failed");
      setPhase("error");
    };

    const commitRecoveredSnapshot = (
      snapshot: Awaited<ReturnType<typeof fetchGameplayStateSnapshot>>,
    ): "complete" | "failed" | "pending" => {
      if (!isLive()) return "pending";
      const playerState = snapshot.playerState as Record<string, unknown> | null;
      const resumeView = playerState?.resume_view;
      const resume = resumeView && typeof resumeView === "object"
        ? resumeView as Record<string, unknown>
        : null;
      const resumePhase = typeof resume?.phase === "string" ? resume.phase : "";
      if (resumePhase === "failed") return "failed";

      const history = Array.isArray(playerState?.round_history)
        ? playerState.round_history.filter(
            (entry): entry is Record<string, unknown> => Boolean(entry) && typeof entry === "object",
          )
        : [];
      const normalizeChoice = (value: unknown) =>
        typeof value === "string" ? value.trim().replace(/\s+/g, " ") : "";
      const expectedChoice = normalizeChoice(target.choiceText);
      const entriesWithChoice = history.filter((entry) => normalizeChoice(entry.choice));
      const historyEntry = entriesWithChoice.length > 0
        ? [...entriesWithChoice].reverse().find(
            (entry) => normalizeChoice(entry.choice) === expectedChoice,
          )
        : history[history.length - 1];
      const continuation = typeof historyEntry?.story_continuation === "string"
        ? historyEntry.story_continuation.trim()
        : "";
      const resumeStory = typeof resume?.story_text === "string"
        ? resume.story_text.trim()
        : "";
      const visibleResume = resumePhase === "result" || resumePhase === "summary" || resumePhase === "ending";
      if (!continuation && !resumeStory && !visibleResume && !snapshot.gameOver) {
        return "pending";
      }

      const recoveredStory = resumeStory || (
        continuation
          ? `${target.baseStory}\n\n--- 主角选择了：${target.choiceText} ---\n\n${continuation}`
          : target.baseStory
      );
      commitSessionFields(snapshot, isLive);
      if (!isLive()) return "pending";
      if (recoveredStory.trim()) setStoryText(recoveredStory);
      setOptions([]);
      setCurrentEvent(null);
      setProcessing(false);
      setConnectionStatus(null);
      setReconnectAttempt(null);
      generatingRef.current = false;
      setRoundSummary(
        typeof resume?.round_summary === "string" && resume.round_summary.trim()
          ? resume.round_summary
          : null,
      );

      if (snapshot.gameOver || resumePhase === "ending") {
        setGameOver(true);
        setPhase("ending");
      } else if (resumePhase === "summary") {
        setSummaryText(typeof resume?.summary_text === "string" ? resume.summary_text : "");
        setPhase("summary");
      } else {
        setPhase("result");
      }
      setTransport("active");
      return "complete";
    };

    setTransport("polling");
    setProcessing(true, "fallback");
    setConnectionStatus(null);
    setReconnectAttempt(null);

    while (isLive()) {
      const remainingRequestTime = deadline - Date.now();
      if (remainingRequestTime <= 0) break;
      try {
        const snapshot = await fetchGameplayStateSnapshot(
          gameId,
          controller.signal,
          remainingRequestTime,
        );
        if (!isLive()) return;
        const result = commitRecoveredSnapshot(snapshot);
        if (result === "complete") return;
        if (result === "failed") {
          finishFailed();
          return;
        }
      } catch (error) {
        if (!isLive() || isAbortError(error)) return;
        const status = (error as { status?: unknown })?.status;
        if (status === 404) {
          finishFailed();
          return;
        }
        console.warn("[choiceRecovery] Read-only snapshot failed:", error);
      }

      if (!isLive()) return;
      const remaining = Math.max(0, deadline - Date.now());
      if (remaining <= 0) break;
      try {
        await abortableSleep(
          Math.min(CHOICE_RECOVERY_POLL_INTERVAL_MS, remaining),
          controller.signal,
        );
      } catch (error) {
        if (!isLive() || isAbortError(error)) return;
        throw error;
      }
    }

    finishFailed();
  };

  const startChoice = async (
    operation: ChoiceOperation,
    startOptions: StartChoiceOptions = {},
  ): Promise<void> => {
    if (!gameId) return;

    watchdogCleanupRef.current?.();
    const run = beginGameplayRun(runTokenRef, abortRef);
    const { controller, isCurrent, isLive } = run;
    const baseStory = startOptions.baseStory ?? useGameStore.getState().storyText ?? "";
    const choiceText = operation.kind === "custom"
      ? operation.customText
      : useGameStore.getState().currentEvent?.options?.[operation.optionIndex]?.text ?? "";
    const recoveryTarget = { operation, baseStory, choiceText };
    if (!startOptions.sessionRetry) recoveryTargetRef.current = recoveryTarget;
    const logPrefix = operation.kind === "normal" ? "handleChoice" : "handleCustomChoice";

    if (!startOptions.sessionRetry) {
      setLoadingIdentity((identity) => identity + 1);
      setTransport("active");
    } else {
      setTransport("reconnecting");
    }
    generatingRef.current = true;
    setPhase("choosing");
    setConnectionStatus(null);
    setReconnectAttempt(null);

    let inactivityTimer: ReturnType<typeof setTimeout> | null = null;
    let terminal = false;
    let streamCompleted = false;
    let errorHandled = false;
    let errorHandlingPromise: Promise<void> | null = null;
    let sseSucceeded = false;
    let storyChunkReceived = false;
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

    const handlers: ChoiceHandlers = {
      setProcessing: guard(setProcessing),
      setConnectionStatus: guard(setConnectionStatus as (status: ConnectionStatus) => void),
      setReconnectAttempt: guard(setReconnectAttempt),
      setRoundSummary: guard(setRoundSummary),
      setSummaryText: guard(setSummaryText),
      setCurrentEvent: guard(setCurrentEvent),
      setGameOver: guard(setGameOver),
      setOptions: guard(setOptions),
      setStoryText: guard(setStoryText),
      setPhase: guard(setPhase),
      generatingRef,
      hadRetryRef,
      isCurrentRun: isCurrent,
      setTransport: guard(setTransport),
      gameId,
      signal: controller.signal,
    };

    const recover = async (error: unknown): Promise<void> => {
      if (!isLive() || isAbortError(error)) return;
      clearWatchdog();

      const errorMessage = parseSSEError(error);
      const isSessionExpired = errorMessage.includes("404") ||
        errorMessage.includes("No active game session");
      const shouldReconcileReadOnly = !isSessionExpired && (
        errorMessage.includes("choice_already_processed") ||
        errorMessage.includes("No current event") ||
        isRecoverableChoiceStreamError(errorMessage)
      );
      if (shouldReconcileReadOnly) {
        await reconcileChoiceTarget(recoveryTarget, run);
        return;
      }

      await handleChoiceError(
        error,
        gameId,
        handlers,
        {
          ...(operation.kind === "normal"
            ? { optionIndex: operation.optionIndex }
            : { customText: operation.customText }),
          isRetry: operation.kind === "normal" ? operation.isRetry : false,
          sseSucceeded,
          baseStoryText: baseStory,
          signal: controller.signal,
          allowSyncFallback: false,
          retryChoice: !startOptions.sessionRetry
            ? () => startChoice(operation, { baseStory, sessionRetry: true })
            : undefined,
        },
        logPrefix,
      );
    };

    const dispatchError = (error: unknown): Promise<void> => {
      if (!isLive() || isAbortError(error)) return Promise.resolve();
      if (errorHandled) return errorHandlingPromise ?? Promise.resolve();
      errorHandled = true;
      terminal = true;
      clearWatchdog();
      errorHandlingPromise = recover(error);
      return errorHandlingPromise;
    };

    const armWatchdog = () => {
      clearWatchdog();
      if (!isLive() || terminal) return;
      inactivityTimer = setTimeout(() => {
        inactivityTimer = null;
        if (!isLive() || terminal) return;
        void dispatchError(new Error("Timeout waiting for choice stream activity"));
      }, CHOICE_INACTIVITY_TIMEOUT_MS);
    };

    const touchActivity = () => {
      if (!isLive() || terminal) return;
      setTransport("active");
      setReconnectAttempt(null);
      armWatchdog();
    };

    const applyCompleteOnlyStoryFallback = (data: Record<string, unknown>) => {
      if (!isLive()) return;
      const completeStory =
        typeof data.event_description === "string"
          ? data.event_description.trim()
          : typeof data.story_continuation === "string"
            ? data.story_continuation.trim()
            : "";
      if (!completeStory) return;
      const trimmedBaseStory = baseStory.trim();
      setStoryText(trimmedBaseStory ? `${trimmedBaseStory}\n\n${completeStory}` : completeStory);
    };

    const refreshCompletedSession = async () => {
      try {
        const snapshot = await fetchGameplayStateSnapshot(gameId, controller.signal);
        if (!isLive()) return;
        commitSessionFields(snapshot, isLive);
      } catch (error) {
        if (!isLive() || isAbortError(error)) return;
        console.warn("[choiceComplete] Read-only state refresh failed:", error);
      }
    };

    const callbacks = {
      onActivity: (kind: StreamActivityKind) => {
        if (!isLive()) return;
        if (kind === "complete" || kind === "error") {
          clearWatchdog();
          return;
        }
        touchActivity();
      },
      onStory: (text: string) => {
        if (!isLive() || terminal) return;
        sseSucceeded = true;
        storyChunkReceived = true;
        touchActivity();
        appendStoryText(text);
      },
      onStatus: (status: { phase: string }) => {
        if (!isLive() || terminal) return;
        sseSucceeded = true;
        touchActivity();
        if (status.phase === "retry") {
          hadRetryRef.current = true;
          setStoryText(baseStory);
          setProcessing(true, "retrying");
          return;
        }
        setProcessing(true, status.phase === "retrying" ? "retrying" : status.phase);
      },
      onConnectionStatus: (status: ConnectionStatus) => {
        if (!isLive() || terminal) return;
        setConnectionStatus(status);
        if (status === "reconnecting") {
          setTransport("reconnecting");
          return;
        }
        setReconnectAttempt(null);
      },
      onReconnecting: (attempt: number, maxRetries: number) => {
        if (!isLive() || terminal) return;
        setTransport("reconnecting");
        setReconnectAttempt({ current: attempt, max: maxRetries });
      },
      onComplete: (data: Record<string, unknown>) => {
        if (!isLive() || terminal) return;
        terminal = true;
        streamCompleted = true;
        sseSucceeded = true;
        clearWatchdog();
        if (!storyChunkReceived) applyCompleteOnlyStoryFallback(data);
        if (handleChoiceComplete(data, handlers)) {
          void refreshCompletedSession();
        }
      },
      onError: (error: unknown) => {
        if (!isLive() || streamCompleted || isAbortError(error)) return;
        clearWatchdog();
        void dispatchError(error);
      },
    };

    armWatchdog();
    try {
      if (operation.kind === "normal") {
        await streamChoice(gameId, operation.optionIndex, callbacks, { signal: controller.signal });
      } else {
        await streamCustomChoice(gameId, operation.customText, callbacks, { signal: controller.signal });
      }
      if (!isLive()) return;
      if (errorHandlingPromise) await errorHandlingPromise;
      if (!isLive() || streamCompleted || errorHandled) return;
      await dispatchError(new Error("Choice stream ended without complete event"));
    } catch (error) {
      if (!isLive() || isAbortError(error) || streamCompleted) return;
      await dispatchError(error);
    }
  };

  const handleChoice = (optionIndex: number, isRetry = false) =>
    startChoice({ kind: "normal", optionIndex, isRetry });

  const handleCustomChoice = (customText: string) =>
    startChoice({ kind: "custom", customText });

  const recoverChoiceGeneration = async (): Promise<void> => {
    if (!gameId || !recoveryTargetRef.current) return;
    watchdogCleanupRef.current?.();
    const run = beginGameplayRun(runTokenRef, abortRef);
    generatingRef.current = true;
    setPhase("choosing");
    await reconcileChoiceTarget(recoveryTargetRef.current, run);
  };

  return { handleChoice, handleCustomChoice, recoverChoiceGeneration };
}
