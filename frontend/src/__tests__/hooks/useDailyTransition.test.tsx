import { act, renderHook } from "@testing-library/react";

import { useDailyTransition } from "@/hooks/game/useDailyTransition";
import type { PlayerState } from "@/lib/types";


function playerState(overrides: Partial<PlayerState> = {}): PlayerState {
  return {
    player_name: "林岚",
    life_vision: "开一间社区书店",
    energy: 50,
    mood: 50,
    knowledge: 50,
    age: 28,
    week: 0,
    current_round: 0,
    rounds_per_week: 3,
    character_settings: {},
    timeline: {
      version: 2,
      start_date: "2026-08-13",
      current_date: "2026-08-14",
      day_index: 1,
      day_number: 2,
      completed_days: 1,
      week_number: 1,
      weekday: 4,
      total_days: 365,
    },
    day_history: [],
    ...overrides,
  };
}


describe("useDailyTransition", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    act(() => jest.runOnlyPendingTimers());
    jest.useRealTimers();
  });

  it("keeps a fast next story hidden for the full one-second minimum", () => {
    const { result, rerender } = renderHook(
      ({ phase, storyText }) =>
        useDailyTransition({
          isDailyTimeline: true,
          phase,
          storyText,
          playerState: playerState(),
        }),
      { initialProps: { phase: "loading", storyText: "" } },
    );

    act(() => {
      window.dispatchEvent(new CustomEvent("story2:daily-settlement", {
        detail: {
          transitionText: "决定的余温仍在，时间却已把故事带向明日。",
          nextTimeline: playerState().timeline,
        },
      }));
    });
    rerender({ phase: "options", storyText: "第二天的完整故事。" });

    act(() => jest.advanceTimersByTime(999));
    expect(result.current.active?.transitionText).toContain("时间");

    act(() => jest.advanceTimersByTime(1));
    expect(result.current.active).toBeNull();
  });

  it("stays visible after one second while generation remains slow", () => {
    const { result, rerender } = renderHook(
      ({ phase, storyText }) =>
        useDailyTransition({
          isDailyTimeline: true,
          phase,
          storyText,
          playerState: playerState(),
        }),
      { initialProps: { phase: "loading", storyText: "" } },
    );

    act(() => {
      window.dispatchEvent(new CustomEvent("story2:daily-settlement", {
        detail: {
          transitionText: "这一刻渐渐安静，明日的光已落在前路。",
          nextTimeline: playerState().timeline,
        },
      }));
      jest.advanceTimersByTime(1200);
    });
    expect(result.current.active).not.toBeNull();

    rerender({ phase: "options", storyText: "第二天的完整故事。" });
    expect(result.current.active).toBeNull();
  });

  it("keeps the transition context on failure and exposes retry state", () => {
    const { result, rerender } = renderHook(
      ({ phase }) =>
        useDailyTransition({
          isDailyTimeline: true,
          phase,
          storyText: "",
          playerState: playerState(),
        }),
      { initialProps: { phase: "loading" } },
    );

    act(() => {
      window.dispatchEvent(new CustomEvent("story2:daily-settlement", {
        detail: {
          transitionText: "沉默收拢了这一刻，下一页正随天光展开。",
          nextTimeline: playerState().timeline,
        },
      }));
      jest.advanceTimersByTime(1000);
    });
    rerender({ phase: "error" });

    expect(result.current.active?.failed).toBe(true);
    expect(result.current.active?.nextDate).toBe("2026-08-14");
  });

  it("recovers the same persisted transition after refresh", () => {
    const state = playerState({
      day_history: [{
        event_id: "day-0",
        revision: 1,
        day_index: 0,
        story_date: "2026-08-13",
        event_description: "第一天故事",
        options: [{ text: "接受邀请" }],
        choice: "接受邀请",
        transition_text: "那份心意安静落定，时间随之走向新的一天。",
      }],
    });

    const { result } = renderHook(() =>
      useDailyTransition({
        isDailyTimeline: true,
        phase: "loading",
        storyText: "",
        playerState: state,
      }),
    );

    expect(result.current.active?.transitionText).toBe(
      "那份心意安静落定，时间随之走向新的一天。",
    );
  });

  it("uses a deterministic local fallback for an older archive", () => {
    const state = playerState({
      day_history: [{
        event_id: "day-0",
        revision: 1,
        day_index: 0,
        story_date: "2026-08-13",
        event_description: "第一天故事",
        options: [{ text: "接受邀请" }],
        choice: "接受邀请",
        choice_option_index: 0,
      }],
    });

    const first = renderHook(() =>
      useDailyTransition({
        isDailyTimeline: true,
        phase: "loading",
        storyText: "",
        playerState: state,
      }),
    );
    const second = renderHook(() =>
      useDailyTransition({
        isDailyTimeline: true,
        phase: "loading",
        storyText: "",
        playerState: state,
      }),
    );

    expect(first.result.current.active?.transitionText).toBeTruthy();
    expect(second.result.current.active?.transitionText).toBe(
      first.result.current.active?.transitionText,
    );
  });
});
