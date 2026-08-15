"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import {
  deterministicDailyTransition,
  transitionForHistoryEntry,
} from "@/lib/dailyTransition";
import type { DailyTimeline, PlayerState } from "@/lib/types";
import type { Phase } from "./usePhaseManager";


const MINIMUM_TRANSITION_MS = 1000;

type DailySettlementDetail = {
  transitionText?: string;
  nextTimeline?: Partial<DailyTimeline>;
};

type ActiveDailyTransition = {
  transitionText: string;
  nextDate: string;
};

export type DailyTransitionView = ActiveDailyTransition & {
  failed: boolean;
};


export function useDailyTransition({
  isDailyTimeline,
  phase,
  storyText,
  playerState,
}: {
  isDailyTimeline: boolean;
  phase: Phase;
  storyText: string;
  playerState: PlayerState | null;
}): { active: DailyTransitionView | null } {
  const [active, setActive] = useState<ActiveDailyTransition | null>(null);
  const [minimumElapsed, setMinimumElapsed] = useState(false);
  const timerRef = useRef<number | null>(null);

  const beginTransition = useCallback((next: ActiveDailyTransition) => {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    setActive(next);
    setMinimumElapsed(false);
    timerRef.current = window.setTimeout(() => {
      timerRef.current = null;
      setMinimumElapsed(true);
    }, MINIMUM_TRANSITION_MS);
  }, []);

  useEffect(() => {
    const handleSettlement = (event: Event) => {
      const detail = (event as CustomEvent<DailySettlementDetail>).detail || {};
      const timeline = detail.nextTimeline;
      const nextDate = typeof timeline?.current_date === "string"
        ? timeline.current_date
        : playerState?.timeline?.current_date || "";
      const nextDayIndex = typeof timeline?.day_index === "number"
        ? timeline.day_index
        : playerState?.timeline?.day_index ?? 1;
      const transitionText = typeof detail.transitionText === "string"
        && detail.transitionText.trim()
        ? detail.transitionText.trim()
        : deterministicDailyTransition(Math.max(0, nextDayIndex - 1));
      beginTransition({ transitionText, nextDate });
    };
    window.addEventListener("story2:daily-settlement", handleSettlement);
    return () => window.removeEventListener("story2:daily-settlement", handleSettlement);
  }, [beginTransition, playerState?.timeline?.current_date, playerState?.timeline?.day_index]);

  useEffect(() => {
    if (!isDailyTimeline) {
      setActive(null);
      return;
    }
    if (active || !["loading", "generating", "error"].includes(phase)) return;
    const timeline = playerState?.timeline;
    const history = playerState?.day_history || [];
    const latest = history.at(-1);
    if (
      !timeline
      || !latest
      || playerState?.current_event_data
      || timeline.day_index !== latest.day_index + 1
    ) return;
    beginTransition({
      transitionText: transitionForHistoryEntry(latest, history),
      nextDate: timeline.current_date,
    });
  }, [active, beginTransition, isDailyTimeline, phase, playerState]);

  useEffect(() => {
    if (!active || !minimumElapsed) return;
    if (phase === "options" && storyText.trim()) setActive(null);
  }, [active, minimumElapsed, phase, storyText]);

  useEffect(() => () => {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
  }, []);

  return {
    active: active ? { ...active, failed: phase === "error" } : null,
  };
}
