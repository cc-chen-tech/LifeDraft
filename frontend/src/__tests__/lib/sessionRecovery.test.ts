import type { PlayerState, GameProgress, RoundInfo } from "@/lib/types";
import {
  resolveRecoveredGenerationFailure,
  resolveRecoveredStoryMeta,
  resolveRecoveredStoryText,
  resolveRecoveredView,
} from "@/lib/sessionRecovery";

const basePlayerState: PlayerState = {
  player_name: "Test Player",
  life_vision: "",
  energy: 10,
  mood: 20,
  knowledge: 30,
  wealth: 40,
  age: 18,
  week: 2,
  current_round: 2,
  rounds_per_week: 4,
  character_settings: {},
};

describe("sessionRecovery", () => {
  it("restores a persisted structured generation failure after refresh", () => {
    const playerState = {
      ...basePlayerState,
      resume_view: {
        phase: "failed" as const,
        error: "角色一致性失败",
        failure: {
          code: "REQUIRED_CAST_MISSING",
          summary: "角色一致性失败",
          detail: "陈晓雨没有登场。",
          retryable: true,
          attempts_used: 3,
          quality_level: "expert",
          operation_id: "op-persisted",
        },
      },
    };

    expect(resolveRecoveredGenerationFailure(playerState)).toEqual({
      message: "角色一致性失败",
      code: "REQUIRED_CAST_MISSING",
      summary: "角色一致性失败",
      detail: "陈晓雨没有登场。",
      retryable: true,
      attempts_used: 3,
      quality_level: "expert",
      operation_id: "op-persisted",
    });
  });

  it("restores a saved result view without treating the advanced round as a new event", () => {
    const playerState: PlayerState = {
      ...basePlayerState,
      week: 3,
      current_round: 1,
      resume_view: {
        phase: "result",
        story_text: "第4周周一原故事\n\n选择后的完整结果",
        round_summary: "本轮总结",
        summary_text: "",
        completed_week: 3,
        completed_round: 0,
      },
    };

    expect(resolveRecoveredStoryText({ playerState })).toBe(
      "第4周周一原故事\n\n选择后的完整结果"
    );
    expect(resolveRecoveredView({ playerState })).toEqual({
      phase: "result",
      story: "第4周周一原故事\n\n选择后的完整结果",
      roundSummary: "本轮总结",
      summaryText: "",
      error: "",
    });
  });

  it("restores options, generating, summary, and failed as distinct phases", () => {
    expect(
      resolveRecoveredView({
        eventStory: "待选择故事",
        eventOptions: [{ text: "选择一" }],
        playerState: basePlayerState,
      }).phase
    ).toBe("options");

    for (const phase of ["generating", "summary", "failed"] as const) {
      const playerState: PlayerState = {
        ...basePlayerState,
        resume_view: {
          phase,
          story_text: "保存时可见正文",
          round_summary: "",
          summary_text: phase === "summary" ? "保存时周总结" : "",
          error: phase === "failed" ? "生成中断" : "",
          completed_week: 2,
          completed_round: 1,
        },
      };
      expect(resolveRecoveredView({ playerState }).phase).toBe(phase);
    }
  });

  it("safely restores a legacy completed result that predates resume_view", () => {
    const playerState: PlayerState = {
      ...basePlayerState,
      week: 3,
      current_round: 1,
      rounds_per_week: 3,
      current_event_data: null,
      round_history: [
        {
          week: 3,
          round: 0,
          event_description: "旧存档周一事件",
          story_continuation: "旧存档选择结果",
          summary: "旧存档轮次总结",
        },
      ],
    };

    expect(resolveRecoveredView({ playerState })).toEqual({
      phase: "result",
      story: "旧存档周一事件\n\n旧存档选择结果",
      roundSummary: "旧存档轮次总结",
      summaryText: "",
      error: "",
    });
  });

  it("uses event story when it is available", () => {
    const playerState: PlayerState = {
      ...basePlayerState,
      last_round_full_story: "stale current round content",
      round_history: [{ week: 2, round: 2, event_description: "current event" }],
    };
    const progress: GameProgress = { week: 2, current_round: 2, rounds_per_week: 4 };
    const roundInfo: RoundInfo = { week: 2, current_round: 2 };

    const text = resolveRecoveredStoryText({
      eventStory: "active event text",
      playerState,
      progress,
      roundInfo,
    });

    expect(text).toBe("active event text");
  });

  it("prefers round_history entry matching current week/round", () => {
    const playerState: PlayerState = {
      ...basePlayerState,
      last_round_full_story: "old full round story",
      round_history: [
        { week: 2, round: 1, event_description: "round 2,1 story", story_continuation: "same round 2-1" },
        { week: 3, round: 2, event_description: "round 3,2 story", story_continuation: "current round text" },
      ],
      current_event_data: { event_description: "round context" },
    };
    const progress: GameProgress = { week: 3, current_round: 2, rounds_per_week: 4 };
    const roundInfo: RoundInfo = { week: 3, current_round: 2 };

    const { story, source } = resolveRecoveredStoryMeta({
      playerState,
      progress,
      roundInfo,
    });

    expect(source).toBe("round_history");
    expect(story).toContain("round 3,2 story");
    expect(story).toContain("current round text");
  });

  it("does not reuse stale round_history or last_round_full_story for wrong progression", () => {
    const playerState: PlayerState = {
      ...basePlayerState,
      last_round_full_story: "old full round story",
      round_history: [
        { week: 1, round: 1, event_description: "round 1 story", story_continuation: "stale" },
      ],
      current_event_data: { event_description: "still waiting current event" },
    };
    const progress: GameProgress = { week: 3, current_round: 2, rounds_per_week: 4 };
    const roundInfo: RoundInfo = { week: 3, current_round: 2 };

    const text = resolveRecoveredStoryText({
      eventStory: undefined,
      playerState,
      progress,
      roundInfo,
    });

    expect(text).toBe("");
  });

  it("allows last_round_full_story across week rollover for the first round of a new week", () => {
    const playerState: PlayerState = {
      ...basePlayerState,
      week: 4,
      current_round: 0,
      rounds_per_week: 3,
      last_round_full_story: "new week opening round story",
      round_history: [
        { week: 3, round: 2, event_description: "previous week final round", story_continuation: "finished" },
      ],
      current_event_data: { event_description: "new week opening round context" },
    };
    const progress: GameProgress = { week: 4, current_round: 0, rounds_per_week: 3 };
    const roundInfo: RoundInfo = { week: 4, current_round: 0 };

    const { story, source } = resolveRecoveredStoryMeta({
      eventStory: "",
      playerState,
      progress,
      roundInfo,
    });

    expect(source).toBe("last_round_full_story");
    expect(story).toBe("new week opening round story");
  });

  it("falls back to last_round_full_story when no current progression is available", () => {
    const playerState: PlayerState = {
      ...basePlayerState,
      week: 10,
      current_round: 4,
      last_round_full_story: "legacy last round fallback",
      round_history: [{ week: 1, round: 1, event_description: "old" }],
      current_event_data: { event_description: "legacy" },
    };

    const text = resolveRecoveredStoryText({
      eventStory: "",
      playerState,
    });

    expect(text).toBe("legacy last round fallback");
  });
});
