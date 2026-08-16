import type { EventOption, PlayerState, GameProgress, RoundInfo } from "@/lib/types";
import type { GenerationFailurePayload } from "@/lib/sse";

export interface RecoveryContext {
  eventStory?: string | null;
  eventOptions?: EventOption[] | null;
  playerState?: PlayerState | null;
  progress?: GameProgress | Partial<GameProgress> | null;
  roundInfo?: RoundInfo | Partial<RoundInfo> | null;
}

export interface RecoveredView {
  phase: "loading" | "options" | "result" | "summary" | "ending" | "generating" | "failed";
  story: string;
  roundSummary: string;
  summaryText: string;
  error: string;
}

export function resolveRecoveredGenerationFailure(
  playerState?: PlayerState | null,
): GenerationFailurePayload | null {
  const failure = playerState?.resume_view?.failure;
  if (!failure || !failure.code) return null;
  const summary = failure.summary || playerState?.resume_view?.error || "故事生成未能完成";
  return {
    message: summary,
    ...failure,
    summary,
  };
}

export function resolveRecoveredView({
  eventStory,
  eventOptions,
  playerState,
  progress,
  roundInfo,
}: RecoveryContext): RecoveredView {
  if (eventOptions?.length) {
    return {
      phase: "options",
      story: eventStory || "",
      roundSummary: "",
      summaryText: "",
      error: "",
    };
  }

  const saved = playerState?.resume_view;
  if (saved?.phase) {
    return {
      phase: saved.phase,
      story: saved.story_text || "",
      roundSummary: saved.round_summary || "",
      summaryText: saved.summary_text || "",
      error: saved.error || "",
    };
  }

  if (playerState) {
    const roundState =
      getCurrentRoundState(progress, roundInfo) || getPlayerRoundState(playerState);
    const previous = findImmediatePreviousRound(playerState, roundState);
    if (previous?.story) {
      return {
        phase: "result",
        story: previous.story,
        roundSummary: previous.summary,
        summaryText: "",
        error: "",
      };
    }
  }

  return {
    phase: "loading",
    story: eventStory || "",
    roundSummary: "",
    summaryText: "",
    error: "",
  };
}

export interface StoryRecoveryOptions {
  story: string;
  source: "event" | "round_history" | "last_round_full_story" | "fallback";
}

interface RoundState {
  week: number;
  round: number;
  roundsPerWeek: number | null;
}

function toNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function getCurrentRoundState(
  progress?: GameProgress | Partial<GameProgress> | null,
  roundInfo?: RoundInfo | Partial<RoundInfo> | null
): RoundState | null {
  const progressWeek = toNumber(progress?.week);
  const progressRound = toNumber(progress?.current_round);
  const progressRoundsPerWeek = toNumber(progress?.rounds_per_week);
  const roundInfoWeek = toNumber(roundInfo?.week);
  const roundInfoRound = toNumber(roundInfo?.current_round);
  const roundInfoRoundsPerWeek = toNumber((roundInfo as Record<string, unknown> | undefined)?.rounds_per_week);

  const hasProgressPair = progressWeek !== null && progressRound !== null;
  const hasRoundInfoPair = roundInfoWeek !== null && roundInfoRound !== null;

  if (hasProgressPair) {
    return { week: progressWeek, round: progressRound, roundsPerWeek: progressRoundsPerWeek };
  }

  if (hasRoundInfoPair) {
    return { week: roundInfoWeek, round: roundInfoRound, roundsPerWeek: roundInfoRoundsPerWeek };
  }

  return null;
}

function buildHistoryText(entry: { event_description?: unknown; story_continuation?: unknown }): string {
  const eventDescription = typeof entry.event_description === "string" ? entry.event_description : "";
  const storyContinuation = typeof entry.story_continuation === "string" ? entry.story_continuation : "";

  return eventDescription + (storyContinuation ? `\n\n${storyContinuation}` : "");
}

function findCurrentRoundHistoryText(
  playerState: PlayerState,
  currentRoundState: RoundState
): string | null {
  const entries = playerState.round_history;
  if (!Array.isArray(entries) || entries.length === 0) {
    return null;
  }

  for (let i = entries.length - 1; i >= 0; i--) {
    const entry = entries[i] as {
      week?: unknown;
      round?: unknown;
      event_description?: unknown;
      story_continuation?: unknown;
    };

    if (toNumber(entry.week) === currentRoundState.week && toNumber(entry.round) === currentRoundState.round) {
      return buildHistoryText(entry);
    }
  }

  return null;
}

function getLastRoundHistoryText(playerState: PlayerState): string | null {
  const entries = playerState.round_history;
  if (!Array.isArray(entries) || entries.length === 0) return null;

  const lastEntry = entries[entries.length - 1] as {
    event_description?: unknown;
    story_continuation?: unknown;
  };

  const historyText = buildHistoryText(lastEntry);
  return historyText || null;
}

function getPlayerRoundState(playerState: PlayerState): RoundState {
  return {
    week: toNumber(playerState.week) ?? 0,
    round: toNumber(playerState.current_round) ?? 0,
    roundsPerWeek: toNumber(playerState.rounds_per_week),
  };
}

function findImmediatePreviousRound(
  playerState: PlayerState,
  currentRoundState: RoundState
): { story: string; summary: string } | null {
  const entries = playerState.round_history;
  if (!Array.isArray(entries) || entries.length === 0) return null;

  const lastEntry = entries[entries.length - 1] as {
    week?: unknown;
    round?: unknown;
    summary?: unknown;
    event_description?: unknown;
    story_continuation?: unknown;
  };
  const lastWeek = toNumber(lastEntry.week);
  const lastRound = toNumber(lastEntry.round);
  const roundsPerWeek = currentRoundState.roundsPerWeek ?? toNumber(playerState.rounds_per_week);
  const isPreviousRound =
    (currentRoundState.round > 0 &&
      lastWeek === currentRoundState.week &&
      lastRound === currentRoundState.round - 1) ||
    (currentRoundState.round === 0 &&
      roundsPerWeek !== null &&
      lastWeek === currentRoundState.week - 1 &&
      lastRound === roundsPerWeek - 1);

  if (!isPreviousRound) return null;
  return {
    story: buildHistoryText(lastEntry),
    summary: typeof lastEntry.summary === "string" ? lastEntry.summary : "",
  };
}

function canUseLastRoundFullStory(playerState: PlayerState, currentRoundState: RoundState): boolean {
  const entries = playerState.round_history;
  const hasCurrentEventData = Boolean((playerState as Record<string, unknown>).current_event_data);
  if (!hasCurrentEventData) {
    return false;
  }

  if (!Array.isArray(entries) || entries.length === 0) {
    return currentRoundState.round === 0;
  }

  const lastEntry = entries[entries.length - 1] as {
    week?: unknown;
    round?: unknown;
  };
  const lastEntryWeek = toNumber(lastEntry.week);
  const lastEntryRound = toNumber(lastEntry.round);
  const roundsPerWeek = currentRoundState.roundsPerWeek ?? toNumber(playerState.rounds_per_week);

  if (lastEntryWeek === currentRoundState.week && lastEntryRound === currentRoundState.round - 1) {
    return true;
  }

  return (
    currentRoundState.round === 0 &&
    roundsPerWeek !== null &&
    lastEntryWeek === currentRoundState.week - 1 &&
    lastEntryRound === roundsPerWeek - 1
  );
}

export function resolveRecoveredStoryText({
  eventStory,
  playerState,
  progress,
  roundInfo,
}: RecoveryContext): string {
  const eventText = (eventStory || "").trim();
  if (eventText) {
    return eventStory || "";
  }

  if (!playerState) {
    return "";
  }

  const savedStory = playerState.resume_view?.story_text;
  if (savedStory?.trim()) {
    return savedStory;
  }

  const currentRoundState = getCurrentRoundState(progress, roundInfo);
  const inferenceRoundState = currentRoundState || getPlayerRoundState(playerState);

  const previous = findImmediatePreviousRound(playerState, inferenceRoundState);
  if (previous?.story && !playerState.current_event_data) {
    return previous.story;
  }

  if (currentRoundState) {
    const currentRoundHistoryText = findCurrentRoundHistoryText(playerState, currentRoundState);
    if (currentRoundHistoryText) {
      return currentRoundHistoryText;
    }

    const lastRoundFullStory =
      typeof playerState.last_round_full_story === "string" ? playerState.last_round_full_story : "";

    if (canUseLastRoundFullStory(playerState, currentRoundState) && lastRoundFullStory) {
      return lastRoundFullStory;
    }

    return "";
  }

  const lastRoundFullStory =
    typeof playerState.last_round_full_story === "string" ? playerState.last_round_full_story : "";
  if (lastRoundFullStory.trim()) {
    return lastRoundFullStory;
  }

  return getLastRoundHistoryText(playerState) || "";
}

export function resolveRecoveredStoryMeta({
  eventStory,
  playerState,
  progress,
  roundInfo,
}: RecoveryContext): StoryRecoveryOptions {
  const eventText = (eventStory || "").trim();
  if (eventText) {
    return {
      story: eventStory || "",
      source: "event",
    };
  }

  if (!playerState) {
    return { story: "", source: "fallback" };
  }

  const savedStory = playerState.resume_view?.story_text;
  if (savedStory?.trim()) {
    return { story: savedStory, source: "fallback" };
  }

  const currentRoundState = getCurrentRoundState(progress, roundInfo);
  const inferenceRoundState = currentRoundState || getPlayerRoundState(playerState);

  const previous = findImmediatePreviousRound(playerState, inferenceRoundState);
  if (previous?.story && !playerState.current_event_data) {
    return { story: previous.story, source: "round_history" };
  }

  if (currentRoundState) {
    const currentRoundHistoryText = findCurrentRoundHistoryText(playerState, currentRoundState);
    if (currentRoundHistoryText) {
      return { story: currentRoundHistoryText, source: "round_history" };
    }

    const lastRoundFullStory =
      typeof playerState.last_round_full_story === "string" ? playerState.last_round_full_story : "";
    if (canUseLastRoundFullStory(playerState, currentRoundState) && lastRoundFullStory) {
      return { story: lastRoundFullStory, source: "last_round_full_story" };
    }

    return { story: "", source: "fallback" };
  }

  const lastRoundFullStory =
    typeof playerState.last_round_full_story === "string" ? playerState.last_round_full_story : "";
  if (lastRoundFullStory.trim()) {
    return { story: lastRoundFullStory, source: "last_round_full_story" };
  }

  return { story: getLastRoundHistoryText(playerState) || "", source: "fallback" };
}
