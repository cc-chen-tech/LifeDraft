import type { PlayerState, GameProgress, RoundInfo } from "@/lib/types";
import { resolveRecoveredStoryMeta, resolveRecoveredStoryText } from "@/lib/sessionRecovery";

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
